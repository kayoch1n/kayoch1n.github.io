---
layout: post
title:  "glibc 堆内存分配学习笔记"
date:   2020-08-15 12:15:38 +0800
diary: "前段时间项目组换了一个新来的产品经理;这位大佬还未熟悉产品，别人问到啥问题都要找测试回答，连客户演示、销售之类的问题都要来找测试，晕😵，到底我是产品还是你是产品？"
---

# Preface

记录一下学习glibc的堆内存分配函数[void *_int_malloc(mstate av, size_t bytes)](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#_int_malloc)的学习过程，以下行文内容都是基于 **x86_64** 操作系统，暂不考虑tcache。

# Content

## Data structure

每个堆都存在一个 `malloc_state` 结构；主线程的第一个堆对应的 `malloc_state` 结构又称为 `main_arena`。在这个结构中：

### CHUNKS and BINS

glibc 管理动态内存的最小单位是CHUNK，其大小按照**16字节**对齐(`MALLOC_ALIGNMENT`)，最小的CHUNK大小为32字节(`MINSIZE`)。CHUNK的组成结构如下图所示。比较重要的一点是两个指针`fd`和`bk`: 在 CHUNK 空闲时，这一/两个变量能够为 CHUNK 组成单向/双向链表，在 CHUNK 被占用时又能存储用户数据。除此之外的细节可参见[CTF wiki](https://ctf-wiki.github.io/ctf-wiki/pwn/linux/glibc-heap/heap_structure-zh/#malloc_chunk)，在此不再赘述:
```
chunk-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             Size of previous chunk, if unallocated (P clear)  |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             Size of chunk, in bytes                     |A|M|P|
  mem-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             User data starts here...                          .
        .                                                               .
        .             (malloc_usable_size() bytes)                      .
next    .                                                               |
chunk-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             (size of chunk, but used for application data)    |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             Size of next chunk, in bytes                |A|0|1|
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

`free()`释放后的CHUNK不会直接返回给操作系统;glibc 使用链表来管理CHUNK，这些链表称为 BINS。BINS分为四类，其中 UNSORTED, SMALL & LARGE BINS 使用数组`malloc_state::bins`存放在一起，而FAST BINS单独存放在`malloc_state::fastbinsY`:

- FAST BINS: 
  - 每个 BIN 内的CHUNK通过`fd`组成单向链表;
  - 每个 BIN 采取和栈一致、后进先出(LIFO)的存取方式，从头部存入/取出;
  - 按照CHUNK大小分类，最小的BINS为32字节，和 `MINSIZE` 保持一致，对应的索引为0;最大的BINS大小为160字节，对应的索引为8;
  - 因此一共有9=(160-32)//16+1类不同大小的 BINS: 32, 48, 64, ..., 160.
  - 和其它 BINS 不同，FAST BIN 内的 CHUNK 一直处于占用状态。
- UNSORTED BIN: 只有一个 BIN ，而且是双向链表;
- SMALL BINS:
  - 每个 BIN 都是双向链表;
  - 每个 BIN 采取和队列一致、先进先出(FIFO)的存取方式，从头部放入、从尾部取出;
  - 按照CHUNK大小分类，最小的BINS为32字节，最大为1008字节;
  - 因此一共有62=(1008-32)//16+1类不同大小的 BINS: 32, 48, 64, ..., 1008.
- LARGE BINS:
  - 每个 BIN 都是双向链表;
  - 每个 BIN 采取和队列一致、先进先出(FIFO)的存取方式，从头部放入、从尾部取出;
  - 在 `malloc_state::bins` 中除去 UNSORTED 和62个 SMALL 以外的都是 LARGE ;
  - 每个 BIN 内的 CHUNK 大小控制在一定的公差范围内，不要求严格一致;
  - 每个 BIN 内的 CHUNK 额外使用两个指针组成另一个双链表，在这个链表内按照大小递增排列;和BIN本身形成一个跳表(skip list);
  - BINS按照公差分成六组，32bit和64bit系统的划分方式一致(摘自源码):
    - 32 bins of size      64
    - 16 bins of size     512
    - 8 bins of size    4096
    - 4 bins of size   32768
    - 2 bins of size  262144
    - 1 bin  of size what's left

### binmap

这是用来标记 SMALL/LARGE BINS 是否包含 CHUNK 的位图数据结构，本质上是一个包含4个32bit整数的数组；存放位置是 `malloc_state::binmap`

## Implementation

### _int_malloc

#### Prototype

```c
static void * _int_malloc(mstate av, size_t bytes)
```

#### Steps

1. 如果传入的av指针为NULL，调用`sysmalloc`向操作系统申请内存 -> DONE;
2. 将 sz(用户申请的大小) 转换为 nb(CHUNK的大小);
3. 如果 nb < `global_max_fast` (176B):
   1. *EXACT FIT*: 从 FAST BINS 中找到大小为 nb 的 BIN，从**头部**取出 -> DONE;
4. 如果 nb 是 SMALL 申请 nb < `MIN_LARGE_SIZE` (1024B):
   1. *EXACT FIT*: 从 SMALL BINS 中找到大小为 nb 的 BIN，从**尾部**取出，UNLINK -> DONE;
5. 否则这是一个 LARGE 申请。先执行一次 `malloc_consolidate`:
   1. 遍历并清空 FAST 单链表;
   2. 尝试对 CHUNK 和其前一个、后一个的非 TOP 、空闲的 CHUNK 进行合并;
   3. 把 CHUNK 放入 UNSORTED;
   4. 如果有前后 CHUNK 因此被合并，要将 CHUNK 从对应的 SMALL/LARGE BIN中拆出，即发生 `UNLINK`。
6. 接着在 *EXACT FIT* 失败，或者 nb 是 LARGE 申请的情况下，
   1. 从后往前遍历 UNSORTED 
      1. *BEST FIT*: 如果满足以下条件，就可以从 `av->last_remainder` 切一块出来 -> DONE:
         1. UNSORTED 只有一个 CHUNK ;
         2. 这个 CHUNK 刚好是 `av->last_remainder`;
         3. nb 是 SMALL 申请;
         4. 切了一块之后剩余部分大于 `MINSIZE`(32);
      2. *EXACT FIT*: 如果 CHUNK 大小刚好等于 nb -> DONE;
      3. 否则，把 CHUNK 按照大小放到对应的 SMALL/LARGE BINS。按照注释，这是**唯一一处把 CHUNK 放入到 SMALL/LARGE BINS 的代码**;
      4. 在一次 `_int_malloc` （不限于一次遍历 UNSORTED）过程中，最多循环 10000 次然后退出。
   2. *BEST/EXACT FIT*: 如果这是一个 LARGE 申请，尝试从 LARGE BINS 找到满足 nb 的最小 CHUNK -> DONE:
      1. 发生 UNLINK
      2. 如果 CHUNK 剩下部分的长度大于 `MINSIZE`，则将剩下部分放入 UNSORTED;
   3. *BEST FIT*: 到这里为止，nb 对应的 SMALL/LARGE BIN 没有 CHUNK 了。
      1. 尝试从nb开始，按照大小逐个扫描位图 binmap，期望找到包含 CHUNK 的 BIN -> DONE;
      2. 发生 `UNLINK`;
      3. 如果 CHUNK 剩下部分的长度大于 `MINSIZE`，则将剩下部分放入 UNSORTED;
      4. 如果 nb 是一个 SMALL 申请，还会将剩下部分设为 `av->last_remainder`;
   4. 如果逐个扫描位图也不能找到 CHUNK，但 TOP 可以满足，则从 TOP 的低地址方向切一块 -> DONE;
   5. 如果 TOP 仍不能满足但 FAST 中仍存在 CHUNK，则再次发生 `malloc_consolidate`;
      1. 猜测可能是要照顾多线程程序？
   6. 否则，使用 `sysmalloc` 向操作系统申请内存 -> DONE
7. 回到 6.

### sysmalloc

To be continued...

### _int_free

To be continued...

# Reference

1. [CTF wiki 堆利用](https://ctf-wiki.github.io/ctf-wiki/pwn/linux/glibc-heap/introduction-zh/)
2. [glibc source malloc.c](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html)