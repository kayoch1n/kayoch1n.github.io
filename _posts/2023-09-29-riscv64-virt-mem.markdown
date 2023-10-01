---
toc: true
layout: "post"
catalog: true
title: "RISCV64 Virtual Memory"
date:   2023-09-29 15:40:38 +0800
header-img: "img/sz-transmission-tower-2.jpg"
mermaid: true
categories:
  - blog
tags:
  - riscv64
  - os 
---

在RISCV64 RCORE OS 的虚拟内存之前的章节中，程序需要考虑以下问题：

1. 程序内存大小受限制。程序数量越多，单个程序能使用的内存就越少；
2. 无法保证数据安全。假如一个程序的读写逻辑存在BUG或者安全漏洞，可能破坏另一个程序甚至是内核的内存区域。

虚拟内存的意义在于将上述问题“转嫁”到内核：由**内核**在运行时为程序提供一个大小远远超过物理内存的、读写相互隔离的地址空间，禁止直接读写物理内存，可以减轻程序作者的编码负担，使其可以专注于业务逻辑。这篇文章[RCORE OS 课程的虚拟内存章节](https://rcore-os.cn/rCore-Tutorial-Book-v3/chapter4/index.html)的学习笔记，对应代码在[post/ch4-os-app-pagetable 分支](https://github.com/kayoch1n/rcore-course/tree/post/ch4-os-app-pagetable)。


# Virtual Memory 

在虚拟内存机制下，任何对于内存地址的读写都会被视为对虚拟地址的读写；但是最终都会落到硬件上变成对应的物理地址的读写操作，这一过程称为地址翻译（Address translation）。由软硬件——内核和MMU共同完成：

一个很常见的sd指令：

```
   0x0000000000010068 <+2>:     sd      ra,88(sp)
```

该指令的作用是将ra的值写入从sp+88处开始的连续的8个字节。当sp+88所代表的内存地址通过地址总线传输到CPU，MMU 查找页表（Page Table）、将虚拟地址翻译成物理地址，最终再写入该物理地址。MMU(Memory management unit) 是**CPU**的一部分。

而 Page table(页表)存储了虚拟页(page)和物理页(frame)的映射关系，由**内核**进行管理，是存储于内存的一个数据结构，所以页表本身也是要占内存的。页表的管理的粒度是页（page），常见大小为 4KB（4096B），也有的OS提供更大的大页。页表是一个树结构，页是其中的中间节点，物理页是叶子节点，而根节点所在的地址会存储在CPU中（比如某个寄存器）。地址翻译说白了就是MMU从根节点出发、遍历页表树、到达叶子节点的过程，至于选择哪个中间节点、则是跟具体的架构或具体的实现机制有关。通常在现代的CPU中，MMU还会集成一个TLB(Translation Lookaside Buffer)，用以缓存页表的结果来减少查页表的次数。

```mermaid
graph LR
    id1[1级页表]
    id1 --> id3[2级页表]
    id1 --> id4[...]
    id3 --> id7[3级页表]
    id3 --> id8[...]
    id7 --> id9[物理页]
    id7 --> id10[...]
```


## RISCV64 SV39

SV39是RISCV64下的一个虚拟内存机制，因其64-bit的虚拟地址仅使用39个bit而得名，总共能够寻址$2^39=512\text{GiB}$的地址空间。每个虚拟地址的高位64~40需要跟第39个bit保持一致，换言之，整个寻址空间可以分成两个部分：

- 0 ~ 0x3F FFFF FFFF
- 0xFFFF FFC0 0000 0000 ~ 0xFFFF FFFF FFFF FFFF

每个部分大小都是 256 GiB，只有这两个部分的地址能通过MMU，其他地址将会引起异常（什么异常）。在SV39机制中，每个4K页表包含512个页表项（Page Table Entry，每个8字节），对应地可以用9个bit来定位这个页表中的页表项。页表项的8个字节包含了指向下一级页的物理地址的信息，以及指示MMU其是否可读可写等等权限信息。


|Physical Page Number|RSW|D|A|G|U|X|W|R|V|
|-|-|-|-|-|-|-|-|-|-|
|44|2|1|1|1|1|1|1|1|1|


如上图所示低8bits(0~7)用于权限控制：V表示是否虚拟页已被映射，RWX分别表示是否可读可写可执行，U表示是否允许CPU在privilege level为U的时候访问，等等。第10到53个bit表示物理页的号码（PPN），这个值乘以4K就是页的物理地址。

### Virtual Address

|1级index|2级index|3级index|页内Offset|
|-|-|-|-|
|9|9|9|12|
|0x2|0x1|0x14E|0xEB8|

虚拟地址的39bits分成两部分：3个页表index（3x9 bits）和页内offset（12 bits）。第i个页表index值n，用于告诉MMU在第i-1级页表的第n个页表项存储了i级页表的物理地址。根据页表index的长度，

1. 页表的根节点，也就是1级页表，数量只有1个，所在的物理地址存在**SATP**寄存器中；
2. 2级页表最多有512个，
3. 3级页表最多有512x512=256K个，
4. 每个3级页表能 index 512个 frame，总共能索引512x256K=128M个frame

又因为每个frame的大小为4KiB，因此能寻址合共 128Mx4KiB=512GiB 的地址空间，跟39-bit的长度是对应上的。

### Address Translation

以一个例子来说明SV39机制下虚拟地址翻译物理地址的过程。在这个例子中，虚拟地址为 `0x8034eeb8`，可以用一个简单的脚本对这个地址拆分

```python
def sv39_virt_destruct(addr):
    addr = addr & (1<<39) - 1
    offset = addr & (1<<12)-1
    addr >>= 12
    i1 = addr & (1<<9)-1
    addr >>= 9
    return (addr >> 9, addr & (1<<9)-1, i1, offset)

list(map(hex, sv39_virt_destruct(0x8034eeb8)))
```

可以得到3个页表index+1个页内offset：`0x2`, `0x1`, `0x14E` 和 `0xEB8`。翻译过程如下：

1. MMU首先根据SATP的值访问1级页表，找到第0x2个页表项，得到2级页表的物理地址；
2. 访问2级页表，找到第0x1个页表项，得到3级页表的物理地址；
3. 访问3级页表，找到第0x14E个页表项，得到虚拟页对应的物理页的地址；
4. 将该物理页的地址和页内offset拼接，得到最终的物理地址。

```mermaid
flowchart TB
    subgraph 页表树
    direction TB
    1级页表 --0x0--> idooo20[2级页表]
    1级页表 --0x1--> idooo21[2级页表]
    1级页表 ==0x2==> id1[2级页表]
    id1 ==0x1==> id2[3级页表]
    id1 --0x2--> idooo30[3级页表]
    id2 --0x14D---> idooo40[物理页]
    id2 ==0x14E===> id3[物理页]
    end

    subgraph 虚拟地址
    direction LR
    0x2 ~~~ 0x1 ~~~ 0x14E ~~~ 0xEB8
    end
    
    虚拟地址 -.0x2.-> 1级页表
    虚拟地址 -.0x1.-> id1
    虚拟地址 -.0x14E.-> id2
```

## Store Fault

在上述例子中，MMU访问的所有物理页，包括页表的中间节点和叶子节点，都经过了映射；如果其中一个物理页未经映射，也就是对应的页表项的V字段为0，CPU就会产生一个fault。在 trap handler中设置断点，命中之后，检查S级中断的原因：

```
gdb$ i r sepc scause
sepc           0x1007a  0x1007a
scause         0xf      0xf
```

[根据文档得知](https://five-embeddev.com/riscv-isa-manual/latest/supervisor.html#sec:scause)，scause 最高位0表示这个 trap 并非由 interrupt 引起，0xf 表示 Store/AMO page fault。这个时候需要内核决定是否处理这个fault。

虚拟地址空间远远大于物理内存。已经映射过的物理页，可能因为swap机制被转存到次一级的存储设备，比如磁盘。如果没有空闲的物理页，swap机制再次起作用，内核将找出、淘汰掉部分物理页并转存到次级存储设备，将磁盘上的数据复制到腾出来的空闲的物理页，并更新页表。此时原先的虚拟地址才是可以读写的。

然而[rcore里并没有处理 fault](https://github.com/kayoch1n/rcore-course/blob/post/ch4-os-app-pagetable/os/src/trap/mod.rs#L68)。。。有一点值得注意，如果trap是由 syscall 引起的， `ecall` 在执行完之后会对 sepc 的值增加4，而`sret`会将pc设置为 sepc 的值，这表示 syscall 结束之后会执行应用程序的下一条指令。如果trap由 store fault引起，则无需对 sepc+4；假设内核将缺失的页重新装进了内存，则只需要重新执行原先的指令即可。

## Address Mapping

一个特殊的现象是，对于一块连续的虚拟内存来说，其底下的物理内存却不一定是连续的，这取决于内核映射内存的方式。

页表存储了虚拟内存和物理内存的映射关系。MMU利用这个映射关系读写内存，但是如何管理这个映射关系，比如虚拟地址 `0x10000` 要映射到哪个物理地址，是内核需要考虑的事情。最简单的是随机映射，虚拟地址和物理地址并无必然关系。内核可以选择将所有空闲物理页统一管理起来；对于应用程序要用到的虚拟页，内核可以找一个任意的、空闲的物理页形成映射并记录在页表中。在rcore中，内核就是用的随机映射处理应用程序的内存空间，将从 `0x10000` 开始的虚拟内存映射到任意可以用的物理页，比如`0xdead0000`。

### Identify Mapping

```mermaid
flowchart LR
  subgraph virt_s1[虚拟地址]
  virt2[0x80200000] --- virt3[0x80201000]
  end

  subgraph virt_s2[虚拟地址]
  virt1[0x10000]
  end

  virt_s1 --> phy1
  virt_s2 --> phy3

  subgraph 物理地址
  direction TB
  phy1[0x80200000] --- phy2[0x80201000]
  phy2 -."...".- phy3[0xdead0000]
  end
```

除此之外，在rcore中，内核还用到一种恒等映射：在这种映射方式中，虚拟地址等于物理地址，例如从 `0x80200000` 开始的内核的虚拟内存就被完整映射到从 `0x80200000` 开始的物理内存。

使用恒等映射的原因是，内核需要读写页表。前面提到页表是由内核维护的，加上内核本身也运行于虚拟地址之上，但是页表项存储的是下一级页的**物理地址**(否则MMU的地址翻译就会陷入无限递归)，内核需要读取该物理地址所在的页表节点、写入页表项数据；使用恒等映射之后，这个处理过程就方便很多了，内核可以直接将该物理地址当作虚拟地址使用。

### Recursive Page Tables

实际上，为了让内核能够读写页表，恒等映射只是其中一种实现方式；[blog_os](https://os.phil-opp.com/paging-implementation/#map-at-a-fixed-offset)还提到了另外两种方式：Map at a Fixed Offset 和 Recursive Page Tables。Map at a Fixed Offset 和恒等映射类似，虚拟地址和物理地址的值相差了一个固定的值，并且由 bootloader 进行初始化，内核在启动的时候就已经开始使用虚拟内存了。这一点跟rcore不同，因为rcore的内核在启动的时候使用的是物理内存，并且完全靠内核初始化虚拟内存。

Recursive Page Table 会在页表中设置一个特殊的index，比如511，并且将该index的页表项设置为当前页的物理地址。在访问特定的虚拟地址时，这个特殊的 index 能够缩短MMU实际遍历不同节点的数量。

举个例子，假设根节点所在的物理地址是 `0x2000`，将其中第511=`0x1ff` 个index的值设置为 `0x2000`，当MMU访问虚拟地址 `0x7ffffff000` 时，该地址被分解为3个页表index `0x1ff`, `0x1ff`, `0x1ff` 以及页内offset 0。MMU根据第一个index `0x1ff`，获取根节点的第 `0x1ff` 个页表项，其值为 `0x2000`，也就是当前节点的物理地址；如此再重复两次后，最后访问的还是根节点。类似地，当MMU访问虚拟地址 `0xbffff000`，实际上访问的是第0x2个2级页表，这是因为 `0xbffff000` 的三个index分别是 `0x2`，`0x1ff` 和 `0x1ff`，内核便可以以此法读写所有页表。


## Multi-programming

虚拟内存为多程序执行提供了极大的便利。代码的实现跟课程第4章正文的实现略有不同：原实现给内核使用了单独的页表，这个页表包含了内核用到的所有代码及数据；当CPU从U级切换到S级的时候，内核将应用程序的页表切换为内核自己的页表。

代码的实现沿用了习题2的思路，让应用程序和内核使用同一个页表，当发生 trap 、CPU从U级切换到S级的时候，页表也无需切换，代码也更加简洁。

### Address Space Layout

|备注|内容|
|-|-|
|起始：0x10000|ELF各个段|
|...|...|
||END of ELF|
|不映射|Guard Page|
||User stack|
||...|
|起始：0x80200000<br/>U级不可访问|内核|
||...|
|U级不可访问|Trap Context|

应用程序的地址空间如上所示，主要是4个part：

1. ELF各个段使用随机映射方式、被映射到 `0x10000` 开始的虚拟地址。通过 linker 脚本使得 .text 段的第一条指令放在了 `0x10000`；
2. 在ELF的段和user stack之间空出来一个 guard page，guard page不会映射到物理地址。一般来说栈从高地址向低地址生长，高地址的一端称为栈底、低地址的另一端称为栈顶，当栈顶因为无限递归等原因触及到guard page时（也就是所谓的“爆栈”），CPU会产生fault，内核得以发现并结束掉应用程序；
3. 内核的所有代码及数据均使用恒等映射，地址都是 `0x80200000`。所有应用程序的内核part都映射到同一个物理地址，使用同一份数据；
    - 页表项的权限不包含U，也就是U级不可读写这部分内存；
    - trap handler 也是U级。发生trap的时候，权限已经切换到S，trap handler 得以执行
4. Trap Context 跟内核一样，U级不可读写，由内核用以存储当trap发生时各个寄存器的值。

### Context switching

虽然每个应用程序的地址空间都使用同样的起始地址 `0x10000`，但是到底代码和数据还是不同的，因此每个应用程序都要用不同的页表。

rcore 在初始化的时候会一次性将所有应用程序装进内存，为每个应用程序的页表根节点分配并映射到一个随机物理页，用这个物理页的物理地址来区分不同应用程序的页表。在RISCV64中，当前应用程序页表的根节点的物理地址会被编码并存储到 SATP 寄存器中， SATP 的最高位为1表示MMU使用虚拟内存。事实上除了 SV39 以外，RISCV64 还存在 SV48, SV57, SV64 虚拟内存机制，比如 SV57 则是使用到了5级页表。

|Mode|ASID|PPN|
|-|-|-|
|4|16|44|
|8表示启用<br/>SV39虚拟内存|可选<br/>标识当前task/进程|根节点的物理页号|

当发生硬件时钟中断时，内核会决定要执行哪个程序，负责管理任务（或者说进程）的内核代码会找出对应程序页表的根节点。在rcore中，这些信息被记录在一个内核的全局变量中，对应rust代码里的`TaskControlBlock`。然后，内核将编码后的物理地址写入 SATP 寄存器，从而完成不同页表的切换。得益于对内核代码进行恒等映射，所有应用程序的内核代码均能完成切换动作，而且在切换页表的前后若干条指令之间，寄存器内的内存地址、或者说整个上下文用到的内存地址都是仍然有效的，不会出现fault。最后内核通过`sret`回到应用程序、从S级切换到U级，对于应用程序来说仿佛无事发生～～



<!-- ## 总结 -->

<!-- ## Q

- OS 也运行在虚拟内存之上，有什么好处？ -->
