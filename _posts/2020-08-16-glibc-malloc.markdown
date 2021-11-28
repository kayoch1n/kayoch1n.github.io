---
layout: "post"
subtitle: "本文是关于glibc的堆内存分配源代码malloc.c的学习笔记."
title:  "glibc 堆内存分配学习笔记"
date:   2020-08-15 12:15:38 +0800
header-img: "img/sz-transmission-tower-2.jpg"
categories: 
  - blog
tags:
  - glibc
  - pwn
---

前段时间项目组换了一个新来的产品经理;这位大佬还未熟悉产品, 别人问到啥问题都要找测试回答, 连客户演示、销售之类的问题都要来找测试, 晕😵, 到底我是产品还是你是产品？

## 宏定义

| 名称 | 32bit取值 | 64bit取值 | 定义 | 备注
| --- | --- | --- | --- | --- |
| SIZE_SZ | 4 | 8 | `size_t`的长度 | `sizeof(size_t)`
| MALLOC_ALIGNMENT | 16 | 16 | min(sizeof(long double), 2*SIZE_SZ) | 
| MALLOC_ALIGN_MASK | 0xf | 0xf | | `MALLOC_ALIGNMENT - 1` 
| MINSIZE | 16 | 32 | chunk的最小长度 | `4*SIZE_SZ`
| MAX_FAST_SIZE | 80 | 160 | 通过 `mallopt()`函数能够设置的最大fastBIN的长度 | `80 * SIZE_SZ / 4` |
| DEFAULT_MXFAST | 64 | 128| fast bin的默认最大长度 | `64 * SIZE_SZ / 4` |
| NSMALLBINS | 64 | 64 | small bins的数量? | |
| SMALLBIN_WIDTH | 16 | 16 | 暂时不明 | `MALLOC_ALIGNMENT`
| SMALLBIN_CORRECTION | 1 | 0 | 暂时不明 | `(MALLOC_ALIGNMENT > 2 * SIZE_SZ)` |
| MIN_LARGE_SIZE | 1008 | 1024 | 最小的 large bin 长度 | `((NSMALLBINS - SMALLBIN_CORRECTION) * SMALLBIN_WIDTH)`

<!-- Comment -->

<!-- | csize2tidx(x) | max_64(x)=528 | max_64(x)=1056 | 返回tcache中的索引 | `(((x) - MINSIZE + MALLOC_ALIGNMENT - 1) / MALLOC_ALIGNMENT)` |  -->

## 数据结构

每个堆都有一个用来管理堆内存的 `malloc_state` 结构, 主线程的第一个堆对应的 `malloc_state` 结构又称为 `main_arena`. 

### chunks 和 bins

按照[结构体的定义](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#malloc_chunk), glibc 管理动态内存的最小单位是chunk, 长度按照 2xSIZE_SZ 对齐, 所有的chunk的长度都是 2xSIZE_SZ 的整数倍. 

- 元数据部分
   - .mchunk_prev_size 当P位置0时, 表示前一个chunk的长度; 否则存储用户数据
   - .mchunk_size 当前chunk的长度. 由于chunk的长度对齐特性, 低位的三个比特存储了额外的信息
      - A: 1表示不属于main_arena, 0表示属于main_area
      - M: 1表示由mmap函数分配得来
      - P: 前一个chunk是否正在使用
- 用户数据部分
   - .fd, .bk, .fd_nextsize, .bk_nextsize  在chunk空闲时用作存储链表指针, 与其他chunk组成单链表/双循环链表/跳表

一个chunk存储了两部分数据, 分别是供glibc管理chunk的元数据, 以及返回给调用者的用户数据.chunk的组成结构如下图所示, 一些控制结构和用户数据发生了混合, 我猜作者在设计chunk的时候一定是希望能充分利用内存空间. 更多细节可参见[CTF wiki](https://ctf-wiki.org/pwn/linux/glibc-heap/heap_structure/):
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

glibc 使用链表来管理chunk, 这些链表称为 bins. bins分为四类, 其中 unsorted, small 以及 large 存放在结构体 [`malloc_state`](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#malloc_state) 的数组`malloc_state::bins`, bins中的所有chunk均被标记为空闲状态（即下一个chunk的P为置0）; 而 fast bins单独存放在数组`malloc_state::fastbinsY`, 所有chunk**一直处于使用状态**（即下一个chunk的P为置1）. 以64bi为例子: 

- fast bins: 
  - 通过`fd`组成**单向链表**, 从头部存取（后进先出）;
  - 链表内chunk长度一致. 最小为32字节（`MINSIZE`）, 对索引为0; 最大为 `global_max_fast`, 这个值可以通过函数 `__libc_mallopt(M_MXFAST, value)` 改变, 默认值为128字节, 最大值为`(160 + SIZE_SZ) & ~MALLOC_ALIGN_MASK)`, 即176字节; 
  - 因此最多一共有10=(176-32)//16+1类不同长度的链表: 32, 48, 64, ..., 176.
  -chunk一直处于**占用**状态. 
- unsorted bin: 
  - 通过`fd`和`bk`组成的**双向链表**, 只有一个, 从头部放入、从尾部读取（先进先出）; 
  - 链表内 chunk 长度可以不一致; 
- small bins:
  - 双向链表, 从头部放入、从尾部取出（先进先出）;
  - 同一个链表内 chunk 长度一致, 最小为32字节, 最大为1008字节;
  - 一共有62=(1008-32)//16+1类不同长度的链表: 32, 48, 64, ..., 1008, 数量和 `NSMALLBINS` 不同; 
- large bins:
  - 双向链表, 从头部放入、从尾部取出（先进先出）;
  - 在 `malloc_state::bins` 中, 除去 unsorted 和62个 small 以外的都是 large ;
  - 同一个链表内 chunk 长度控制在一定的公差范围内, 不要求严格一致;
  - 同一个链表内 chunk 额外使用两个指针组成另一个跳表(skip list), 在这个跳表内按照长度递增排列;
  - 链表之间按照公差分成六组, 32bit 和 64bit 的划分方式一致(摘自源码):
    - 32 bins of size      64
    - 16 bins of size     512
    - 8 bins of size    4096
    - 4 bins of size   32768
    - 2 bins of size  262144
    - 1 bin  of size what's left

### binmap

`malloc_state::binmap`是用来标记 small/large bins中的链表是否为空的位图数据结构, 本质上是一个包含4个32bit整数的数组, 其用途是快速检查对应比特位的 bin 是否为空, 而不需要直接去遍历bins. 

### tcache

glibc-2.27ubuntu1.2的堆有一个叫做tcache的功能, 网上的资料称该功能的目的是为了给每个线程加快分配内存的速度; 在没有tcache的情况下, 多线程需要通过原子操作从fast bin取得chunk. 不过我看代码通过一个名为tcache的全局变量操作tcache, 所以对于加快多线程分配内存这一个说法时将信将疑的. malloc第一次分配内存时会执行tcache的初始化操作, tcache涉及两个数据结构：

```cpp
typedef struct tcache_entry
{
  struct tcache_entry *next; // 下一个tcache的chunk
} tcache_entry;

typedef struct tcache_perthread_struct
{
  char counts[TCACHE_MAX_BINS];  // 每个链表的长度
  tcache_entry *entries[TCACHE_MAX_BINS];    // 64个链表数组
} tcache_perthread_struct;
```

`tcache_perthread_struct::entries`和 `malloc_state::fastbinsY` 类似, 也是后进先出的单链表数组, 每个链表所包含的chunk的长度固定; 不同点在于, 正常情况下tcache的单链表长度不能超过7, 而且指针指向了用户数据部分, 而不是chunk的开始部分. 从glibc-2.27ubuntu1.4开始, `tcache_entry`还多了一个结构, 用来检测double free风险：

```cpp
typedef struct tcache_entry
{
  struct tcache_entry *next;
  /* This field exists to detect double frees.  */
  struct tcache_perthread_struct *key;
} tcache_entry;
```

## 函数实现

### malloc_consolidate

这个函数通过清空 fast bins 实现整理内存碎片, 其函数签名为：

```c
static void malloc_consolidate(mstate av)
```

通过遍历并清空 fast 单链表: 
1. 尝试对 chunk 和其前一个、后一个的非 TOP 、空闲 chunk 进行合并;
2. 把 chunk 放入 unsorted;
3. 如果有前后 chunk 因此被合并, 要将 chunk 从对应的 small/large bin中拆出, 即发生 `UNLINK`. 

### _int_malloc

从堆中分配内存. 函数签名为：

```c
static void * _int_malloc(mstate av, size_t bytes)
```

函数逻辑：

1. 如果传入的av指针为NULL, 调用`sysmalloc`向操作系统申请内存, 然后返回;
2. 将 sz(用户申请的长度) 转换为 nb( chunk 的长度);
3. 如果 nb < `global_max_fast`, 尝试从长度为 nb 的 fast bin 中精确查找. 如果找到就从单链表中拆除并返回; 
4. 如果 nb < `MIN_LARGE_SIZE` (1024B), 尝试从长度为 nb 的 small bin 中精确查找.  如果找到就发生UNLINK并返回; 
5. 如果这是一个 large 申请. 先执行一次 `malloc_consolidate`; 
6. 接着因为精确查找失败, 或者这是 large 申请, 执行: 
   1. 从后往前（先进先出）遍历 unsorted 
      1. 如果是 small 申请, unsorted 只有一个 chunk, 而且这个chunk刚好是 `av->last_remainder`, 那么从 `av->last_remainder` 切一块出来, 剩余部分赋值给last_remainder**并同时**放回unsorted, 然后返回; 
      2. 如果chunk长度刚好等于 nb 就返回;
      3. 否则, 把chunk按照长度放到对应的 small/large bins. 根据源代码的注释显示, 这是**唯一一处把 chunk 放入到 small/large bins 的代码**;
      4. 在一次 `_int_malloc` （不限于一次遍历 unsorted）过程中, 最多循环 10000 次然后退出. 
   2. 如果这是一个 large 申请, 尝试从 large bins 找到满足 nb 的最小 chunk, 找到就返回:
      1. 发生 UNLINK
      2. 如果切出 nb 长度后剩下部分的长度大于 `MINSIZE`, 则将剩下部分放入 unsorted;
   3. 到这里为止, nb 对应的 small/large bin 没有 chunk 了. 
      1. 尝试从nb开始, 按照长度逐个扫描位图 binmap, 期望找到不为空的 bin;
      2. 从BIN中取出发生 `UNLINK`;
      3. 如果切出 nb 长度后剩下部分的长度大于 `MINSIZE`, 则将剩下部分放入 unsorted. 
         1. 这是 6.1.1 中 last_remainder 出现在 unsorted 的原因;
      4. 如果 nb 是一个 small 申请, 还会将剩下部分设为 `av->last_remainder`;
   4. 如果逐个扫描位图也不能找到 chunk, 但 TOP 可以满足, 则从 TOP 的低地址方向切一块并返回;
   5. 如果 TOP 仍不能满足但 fast 中仍存在 chunk, 则再次发生 `malloc_consolidate`, 然后回到6继续循环;
      1. 猜测可能是要照顾多线程程序？
   6. 否则, 使用 `sysmalloc` 向操作系统申请 nb 长度的内存, 不管成功与否直接返回; 
7. 回到 6.

多说一句, 从_int_malloc 分配得的 chunk 块的内容一般不会清空, 上次使用时写入的数据能够保留. 如果事先通过 _libc_mallopt(M_PERTURB, c) 将字符 perturb_byte 设置为c,  chunk 块的所有字节会被memset设置为 c^0Xff（和0xff异或的结果）. 


### _int_free

释放从堆中申请的内存. 函数签名为：

```c
static void _int_free(mstate av, mchunkptr p, int have_lock)
```

`free()` 的逻辑相对简单得多: 

1. 如果 size < `global_max_fast` 则放入对应长度的 fast bin 的头部并返回;
   1. [这里](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html#4261)glibc会检查相邻的下一个chunk的长度（`.mchunk_size`）是否合理, 即在区间 `(2 * SIZE_SZ, av->system_mem)`;
2. 如果不是 `mmap` 申请得来的, 尝试合并前后的空闲 chunk:
   1. 如果有前后 chunk 因此被合并, 要将 chunk 从对应的 small/large bin中拆出, 即发生 `UNLINK`; 
   2. 如果后一个 chunk 是 TOP, 不会对 TOP 进行 UNLINK; 而是直接修改 `av->top`
   3. 否则把 chunk 放入 unsorted; 
   4. 如果合并后的size 大于阈值 `fastBIN_CONSOLIDATION_THRESHOLD`(65536) , glibc 认为堆中可能存在较多碎片, 因此会调用 `malloc_consolidate`; 
3. 否则这个 chunk 是 `mmap` 申请得来的, 就调用 `munmap_chunk` 返还给操作系统. 


### tcache

```cpp
static void * tcache_get (size_t tc_idx)
{
  tcache_entry *e = tcache->entries[tc_idx];
  assert (tc_idx < TCACHE_MAX_BINS);
  assert (tcache->entries[tc_idx] > 0);
  tcache->entries[tc_idx] = e->next;
  --(tcache->counts[tc_idx]);
  return (void *) e;
}

static void tcache_put (mchunkptr chunk, size_t tc_idx)
{
  tcache_entry *e = (tcache_entry *) chunk2mem (chunk);
  assert (tc_idx < TCACHE_MAX_BINS);
  e->next = tcache->entries[tc_idx];
  tcache->entries[tc_idx] = e;
  ++(tcache->counts[tc_idx]);
}
```

tcache涉及两个操作, `tcache_get`以及`tcache_put`. 引入tcache后, 这是malloc和free发生的变化😒

- malloc(__libc_malloc): 首先尝试在tcache中找对应的链表是否为空, 如果不为空就可以调用`tcache_get`从单链表中取一个出来, 后面就不会调用函数 `_int_malloc` . 

- _int_malloc: 在 fast 和 small bin 的精确查找过程中, 如果精确查找成功, 就会调用 `tcache_put` 把对应bin里的 chunk 装入 tcache 的链表, 直到填满7个为止; 
   - 另外, 在遍历unsorted的过程中, 如果chunk的长度和请求的长度一致, glibc会先把chunk通过`tcache_put`放到tcache里, 而不是立即返回这个. 个人猜测这样做的原因是要把unsorted列表里面同样大小的chunk给安排到tcache. 

- _int_free: 在检查是否能塞入fast bin之前, 优先通过 tcache_put 把chunk放到 tcache. 

#### 1.4版本的double free检测

```cpp
static void tcache_put (mchunkptr chunk, size_t tc_idx)
{
  tcache_entry *e = (tcache_entry *) chunk2mem (chunk);
  assert (tc_idx < TCACHE_MAX_BINS);

  /* Mark this chunk as "in the tcache" so the test in _int_free will
     detect a double free.  */
  e->key = tcache;

  e->next = tcache->entries[tc_idx];
  tcache->entries[tc_idx] = e;
  ++(tcache->counts[tc_idx]);
}
```
最新的ubuntu 18.04的glibc版本是 glibc-2.27ubuntu1.4，该版本堆对`tcache_entry`结构体增加了一个名为key的指针，`tcache_put`函数把chunk的key指针设置为tcache的地址；在释放一个chunk时，会检查当前chunk的key值是否等于tcache的地址，如果等于则表示发生了double free并终止程序。


## 利用

### 泄露堆结构的地址

如果 chunk 被插入 unsorted 链表的尾部, 它的 fd 和 bk 会被设置为一个“假的” chunk 的地址, 这个地址和 `main_arena` 有关, 因此能够进一步泄露 libc 的地址. 以下场景能够使得 chunk 被插入 unsorted 尾部: 
1. 释放一个大于 `global_max_fast` 长度的 chunk; 
2. last_remainder 分裂, 即上述 `_int_malloc` 的6.1.1; 
3. unsorted 的最后一个 chunk 发生分离, 即上述 `_int_malloc` 的6.3.3; 

这个地址是`main_arena.top`成员变量的地址, 这个关系和 `malloc_state` 的存储结构有关, 如下图所示; 在64bit ubuntu 18.04中, 这个地址等于 (char*)&main_arena+88. 这个“假”chunk的fd和bk正好指向了`main_arena.bins[0]`及`main_arena.bins[1]`, 也就是 unsorted 的第一个chunk, 共同组成了一个双链表. 

```cpp
struct malloc_state
{
  __libc_lock_define (, mutex);           // &main_arena+0, mutex_t, 4字节
  /* Flags (formerly in max_fast).  */
  int flags;                              // &main_arena+4, 32bit整数, 4字节
  int have_fastchunks;                    // gdb 调试发现没有这个变量, 估计被编译器优化掉了
  mfastbinptr fastbinsY[NFASTBINS];       // &main_arena+8, 指针数组, 长度为10, 80字节
  mchunkptr top;                          // &main_arena+88, 指针, 8字节
  mchunkptr last_remainder;               // &main_arena+96, 指针, 8字节
  /* Normal bins packed as described above */
  mchunkptr bins[NBINS * 2 - 2];          // &main_arena+104
  /*
   ...
   */
}
```
所以, 根据泄露出来的`main_arena.top`地址就能根据libc的库文件计算main_arena的地址; 尽管libc的库文件里面没有main_arena这个符号, 但是另一个符号 __malloc_hook 却在库中, 而且它和main_arena的地址距离是固定, 因此就能够确定libc的版本了. 举个例子, 在64bit ubuntu16.04中, __malloc_hook位于main_arena之前0x10的地方, 而紧挨着另一个符号__realloc_hook ：

```
gdb$ x/gx 0x7fa731ec7b08
0x7fa731ec7b08 <__realloc_hook>:        0x00007fa731b88a70
gdb$ x/gx 0x7fa731ec7b10
0x7fa731ec7b10 <__malloc_hook>: 0x0000000000000000
gdb$ x/gx 0x7fa731ec7b20
0x7fa731ec7b20 <main_arena>:    0x0000000100000000
```

<!-- TODO -->
<!-- ### glibc的安全检查

### 写入任意内存地址

glibc使用单链表(tcache, fast bin)/双链表(small, large, unsorted bin)/跳表(large bin)。通过重复分配chunk然后释放等手段，修改链表的结构（指针），从而在chunk被插入或拆除的时候实现写入任意内存地址。 -->

## 引用

1. [CTF wiki 堆利用](https://ctf-wiki.github.io/ctf-wiki/pwn/linux/glibc-heap/introduction-zh/)
2. [glibc source malloc.c](https://code.woboq.org/userspace/glibc/malloc/malloc.c.html)
