---
classes: wide
layout: single
title:  "glibc 堆内存分配学习笔记"
date:   2020-08-15 12:15:38 +0800
diary: "前段时间项目组换了一个新来的产品经理;这位大佬还未熟悉产品, 别人问到啥问题都要找测试回答, 连客户演示、销售之类的问题都要来找测试, 晕😵, 到底我是产品还是你是产品？"
categories: 
  - glibc
---

记录一下学习glibc的堆内存分配源代码[malloc.c](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#_int_malloc)的学习过程. 

## Macros

| Name | Value in x86 | Value in X86_64 | Definition | Notes
| --- | --- | --- | --- | --- |
| SIZE_SZ | 4 | 8 | `sizeof(size_t)` | 定义不在 malloc.c
| MALLOC_ALIGNMENT | 8 | 16 | | 定义不在 malloc.c
| MALLOC_ALIGN_MASK | 0x7 | 0xf | `MALLOC_ALIGNMENT - 1` | 定义不在 malloc.c
| MINSIZE | 16 | 32 |  | 定义不在 malloc.c
| MAX_FAST_SIZE | 80 | 160 | `80 * SIZE_SZ / 4` | 通过 `mallopt()`函数能够设置的最大FASTBIN的大小 |
| DEFAULT_MXFAST | 64 | 128| `64 * SIZE_SZ / 4` |

## Data structure
每个堆都存在一个 `malloc_state` 结构; 主线程的第一个堆对应的 `malloc_state` 结构又称为 `main_arena`. 

### CHUNKS and BINS

按照[结构体的定义](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#malloc_chunk), glibc 管理动态内存的最小单位是CHUNK, 大小按照**8/16字节**对齐(`MALLOC_ALIGNMENT`)。"对齐"的意思是说, 所有的CHUNK大小都是8/16的整数倍。除了用户数据以外CHUNK还存储一些让用于管理堆内存的元数据, 因此最小的CHUNK大小为16/32字节(`MINSIZE`), 能够存储12(8+4)/24（16+8）字节的用户数据. 

CHUNK的组成结构如下图所示. 比较重要的一点是两个指针`fd`和`bk`: 在 CHUNK 空闲时, 这一/两个变量能够为 CHUNK 组成单向/双向链表, 在 CHUNK 被占用时又能存储用户数据. 除此之外的细节可参见[CTF wiki](https://ctf-wiki.github.io/ctf-wiki/pwn/linux/glibc-heap/heap_structure-zh/#malloc_chunk), 在此不再赘述:
```
chunk-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             .mchunk_prev_size , if unallocated (P clear)      |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             .mchunk_size , in bytes                     |A|M|P|
  mem-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             User data starts here...                          .
        .             .fd, .bk, .fd_nextsize, .bk_nextsize              .
        .             (malloc_usable_size() bytes)                      .
next    .                                                               |
chunk-> +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             (size of chunk, but used for application data)    |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             Size of next chunk, in bytes                |A|0|1|
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

glibc 使用链表来管理CHUNK, 这些链表称为 BINS. BINS分为四类, 其中 UNSORTED, SMALL & LARGE BINS 使用数组`malloc_state::bins`存放在结构体 [malloc_state](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#malloc_state), CHUNK被标记为空闲状态; 而FAST BINS单独存放在`malloc_state::fastbinsY`, CHUNK **一直处于占用状态**。在x86_64系统中: 

- FAST BINS: 
  - 通过`fd`组成**单向链表**, 从头部存取（后进先出）;
  - 链表内的CHUNK大小一致. 最小为32字节（和 `MINSIZE`一致）, 对应的索引为0; 最大为 `global_max_fast`, 这个值可以通过 `__libc_mallopt(M_MXFAST, value)` 改变, 默认值为128字节, 最大值为`(160 + SIZE_SZ) & ~MALLOC_ALIGN_MASK)`, 即176字节; 
  - 因此最多一共有10=(176-32)//16+1类不同大小的链表: 32, 48, 64, ..., 176.
  - 和其它 BINS 不同, FAST BIN 内的 CHUNK 一直处于**占用**状态. 
- UNSORTED BIN: 
  - 只有一个通过`fd`和`bk`组成的**双向链表**, 从头部放入、从尾部读取（先进先出）; 
  - 链表中的CHUNK大小可以不一致; 
- SMALL BINS:
  - 双向链表, 从头部放入、从尾部取出（先进先出）;
  - 链表内的CHUNK大小一致, 最小为32字节, 最大为1008字节;
  - 因此一共有62=(1008-32)//16+1类不同大小的链表: 32, 48, 64, ..., 1008.
- LARGE BINS:
  - 双向链表, 从头部放入、从尾部取出（先进先出）;
  - 在 `malloc_state::bins` 中, 除去 UNSORTED 和62个 SMALL 以外的都是 LARGE ;
  - 链表内 CHUNK 大小控制在一定的公差范围内, 不要求严格一致;
  - 链表内 CHUNK 额外使用两个指针组成另一个跳表(skip list), 在这个跳表内按照大小递增排列;
  - 链表之间按照公差分成六组, x86 和 x86_64 的划分方式一致(摘自源码):
    - 32 bins of size      64
    - 16 bins of size     512
    - 8 bins of size    4096
    - 4 bins of size   32768
    - 2 bins of size  262144
    - 1 bin  of size what's left

### binmap

`malloc_state::binmap`是用来标记 SMALL/LARGE BINS中的链表是否为空的位图数据结构, 本质上是一个包含4个32bit整数的数组, 其用途是快速检查对应比特位的 BIN 是否为空, 而不需要直接去遍历BINS. 

## Implementation

### malloc_consolidate

通过清空 FAST BINS 整理内存碎片

#### Prototype 

```c
static void malloc_consolidate(mstate av)
```

#### Details
遍历并清空 FAST 单链表: 
1. 尝试对 CHUNK 和其前一个、后一个的非 TOP 、空闲 CHUNK 进行合并;
2. 把 CHUNK 放入 UNSORTED;
3. 如果有前后 CHUNK 因此被合并, 要将 CHUNK 从对应的 SMALL/LARGE BIN中拆出, 即发生 `UNLINK`. 

### _int_malloc

#### Prototype

```c
static void * _int_malloc(mstate av, size_t bytes)
```

#### Details

1. 如果传入的av指针为NULL, 调用`sysmalloc`向操作系统申请内存 -> DONE;
2. 将 sz(用户申请的大小) 转换为 nb(CHUNK的大小);
3. *EXACT FIT*: 如果 nb < `global_max_fast`, 尝试从 FAST BINS 中找大小为 nb 的 BIN, 找到就返回; 
4. *EXACT FIT*: 如果 nb 是 SMALL 申请 nb < `MIN_LARGE_SIZE` (1024B), 尝试从 SMALL BINS 中找到大小为 nb 的 BIN, 找到就发生UNLINK并返回; 
5. 如果这是一个 LARGE 申请. 先执行一次 `malloc_consolidate`: 
6. 走到了这里, 要么原因是 *EXACT FIT* 失败, 或者因为这是 LARGE 申请, 接着: 
   1. 从后往前（先进先出）遍历 UNSORTED 
      1. *BEST FIT*: 如果满足以下条件, 就可以从 `av->last_remainder` 切一块出来, 剩余部分赋值给last_remainder及放回UNSORTED, 然后返回:
         1. UNSORTED 只有一个 CHUNK, 这个 CHUNK 刚好是 `av->last_remainder`;
         2. nb 是 SMALL 申请;
         3. 剩余部分大于 `MINSIZE`(32);
      2. *EXACT FIT*: 如果 CHUNK 大小刚好等于 nb就返回;
      3. 否则, 把 CHUNK 按照大小放到对应的 SMALL/LARGE BINS. 根据源代码的注释显示, 这是**唯一一处把 CHUNK 放入到 SMALL/LARGE BINS 的代码**;
      4. 在一次 `_int_malloc` （不限于一次遍历 UNSORTED）过程中, 最多循环 10000 次然后退出. 
   2. *BEST/EXACT FIT*: 如果这是一个 LARGE 申请, 尝试从 LARGE BINS 找到满足 nb 的最小 CHUNK, 找到就返回:
      1. 发生 UNLINK
      2. 如果切出 nb 大小后剩下部分的长度大于 `MINSIZE`, 则将剩下部分放入 UNSORTED;
   3. *BEST FIT*: 到这里为止, nb 对应的 SMALL/LARGE BIN 没有 CHUNK 了. 
      1. 尝试从nb开始, 按照大小逐个扫描位图 binmap, 期望找到包含 CHUNK 的 BIN, 找到就返回;
      2. 发生 `UNLINK`;
      3. 如果切出 nb 大小后剩下部分的长度大于 `MINSIZE`, 则将剩下部分放入 UNSORTED. 
         1. 这是 6.1.1 中 last_remainder 出现在 UNSORTED 的原因;
      4. 如果 nb 是一个 SMALL 申请, 还会将剩下部分设为 `av->last_remainder`;
   4. 如果逐个扫描位图也不能找到 CHUNK, 但 TOP 可以满足, 则从 TOP 的低地址方向切一块并返回;
   5. 如果 TOP 仍不能满足但 FAST 中仍存在 CHUNK, 则再次发生 `malloc_consolidate`, 然后回到6继续循环;
      1. 猜测可能是要照顾多线程程序？
   6. 否则, 使用 `sysmalloc` 向操作系统申请 nb 大小的内存, 不管成功与否直接返回; 
7. 回到 6.

多说一句, 从_int_malloc 分配得的CHUNK块的内容一般不会清空, 上次使用时写入的数据能够保留. 如果事先通过 _libc_mallopt(M_PERTURB, c) 将字符 perturb_byte 设置为c, CHUNK块的所有字节会被memset设置为 c^0Xff（和0xff异或的结果）. 

### sysmalloc

To be continued...

### _int_free

#### Prototype

```c
static void _int_free(mstate av, mchunkptr p, int have_lock)
```

#### Details

`free()` 的逻辑相对简单得多: 

1. 如果 size < `global_max_fast` 则放入对应大小的 FAST BIN 的头部 -> DONE;
   1. 注意[这里](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#4261)glibc会检查相邻的下一个chunk的大小（`.mchunk_size`）是否合理, 即在满足 `(2 * SIZE_SZ, av->system_mem)`, 否则abort;
2. 如果不是 `mmap` 申请得来的, 尝试合并前后的空闲 CHUNK:
   1. 如果有前后 CHUNK 因此被合并, 要将 CHUNK 从对应的 SMALL/LARGE BIN中拆出, 即发生 `UNLINK`; 
   2. 如果后一个 CHUNK 是 TOP, 不会对 TOP 进行 UNLINK; 而是直接修改 `av->top`
   3. 否则把 CHUNK 放入 UNSORTED; 
   4. 如果合并后的size 大于阈值 `FASTBIN_CONSOLIDATION_THRESHOLD`(65536) , glibc 认为堆中可能存在较多碎片, 因此会调用 `malloc_consolidate`; 
3. 否则这个 CHUNK 是 `mmap` 申请得来的, 就调用 `munmap_chunk` 返还给操作系统. 

## Reference

1. [CTF wiki 堆利用](https://ctf-wiki.github.io/ctf-wiki/pwn/linux/glibc-heap/introduction-zh/)
2. [glibc source malloc.c](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html)