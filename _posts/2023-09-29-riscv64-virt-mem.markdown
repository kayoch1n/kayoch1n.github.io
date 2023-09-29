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

# RISCV64 Virtual Memory

在RISCV64 RCORE OS 的虚拟内存之前的章节中，程序需要考虑以下问题：

1. 程序内存大小受限制。程序数量越多，单个程序能使用的内存就越少；
2. 无法保证数据安全。假如一个程序的读写逻辑存在BUG或者安全漏洞，可能破坏另一个程序甚至是内核的内存区域。

虚拟内存的意义在于将上述问题“转嫁”到内核：由**内核**在运行时为程序提供一个大小远远超过物理内存的、读写相互隔离的地址空间，禁止直接读写物理内存，可以减轻程序作者的编码负担，使其可以专注于业务逻辑。下文记录[RISCV64 RCORE OS 课程的虚拟内存章节](https://rcore-os.cn/rCore-Tutorial-Book-v3/chapter4/index.html)的学习笔记。


## Virtual Memory 

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


### SV39 Virtual Memory

SV39是RISCV64下的一个虚拟内存机制，因其64-bit的虚拟地址仅使用39个bit而得名，总共能够寻址$2^39=512\text{GiB}$的地址空间。每个虚拟地址的高位64~40需要跟第39个bit保持一致，换言之，整个寻址空间可以分成两个部分：

- 0 ~ 0x3F FFFF FFFF
- 0xFFFF FFC0 0000 0000 ~ 0xFFFF FFFF FFFF FFFF

每个部分大小都是 256 GiB，只有这两个部分的地址能通过MMU，其他地址将会引起异常（什么异常）。在SV39机制中，每个4K页表包含512个页表项（Page Table Entry，每个8字节），对应地可以用9个bit来定位这个页表中的页表项。页表项的8个字节包含了指向下一级页的物理地址的信息，以及指示MMU其是否可读可写等等权限信息。


|Physical Page Number|RSW|D|A|G|U|X|W|R|V|
|-|-|-|-|-|-|-|-|-|-|
|44|2|1|1|1|1|1|1|1|1|


如上图所示低8bits(0~7)用于权限控制：V表示是否虚拟页已被映射，RWX分别表示是否可读可写可执行，U表示是否允许CPU在privilege level为U的时候访问，等等。第10到53个bit表示物理页的号码（PPN），这个值乘以4K就是页的物理地址。

#### Virtual Address

虚拟地址的39bits分成两部分：3个页表index（3x9 bits）和页内offset（12 bits）。第i个页表index值n，用于告诉MMU在第i-1级页表的第n个页表项存储了i级页表的物理地址。根据页表index的长度，

1. 页表的根节点，也就是1级页表，数量只有1个，所在的物理地址存在**SATP**寄存器中；
2. 2级页表最多有512个，
3. 3级页表最多有512x512=256K个，
4. 每个3级页表能索引512个 frame，总共能索引512x256K=128M个frame

又因为每个frame的大小为4KiB，因此能寻址合共 128Mx4KiB=512GiB 的地址空间，跟39-bit的长度是对应上的。

#### Address Translation

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

可以得到3个页表index+1个页内offset：0x2, 0x1, 0x14E 和 0xEB8。翻译过程如下：

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

#### Storage Fault

在上述例子中，MMU访问的所有物理页，包括页表的中间节点和叶子节点，都经过了映射；如果其中一个物理页未经映射，也就是对应的页表项的V字段为0，CPU就会产生一个fault。在 trap handler中设置断点，命中之后检查S级中断的原因：

```
gdb$ i r sepc scause
sepc           0x1007a  0x1007a
scause         0xf      0xf
```

[查表得知](https://five-embeddev.com/riscv-isa-manual/latest/supervisor.html#sec:scause)，scause 最高位0表示这个 trap 并非由 interrupt 引起，0xf 表示 Store/AMO page fault。这个时候需要内核决定是否处理这个fault。

<!-- app cpu 执行写入内存的指令 -> MMU 触发 fault？中断？ 

- 有没有什么资料表明这个中断来自CPU内部？
- MMU 如何发现 fault -->

<!-- -> 中断 handler -> 映射物理内存到虚拟内存的地址 -> 然后指令重新执行？ -->
<!-- 
#### Continuous Address Space 

一个特殊的现象是，对于一块连续的虚拟内存来说，其底下的物理内存却不一定是连续的。

#### Address Mapping

页表存储了虚拟内存和物理内存的映射关系。但是如何管理这个映射关系，比如虚拟地址0x1000要映射到哪个物理地址，是内核需要考虑的事情。

最普通的是随机映射，虚拟地址和物理地址并无必然关系。对于应用程序要用到的地址，内核可以找一个任意的空闲的物理地址形成映射并记录在页表中。


使用 identical mapping 的一个原因是，

1. 内核要直接使用物理地址


### Multi-programming

#### RISCV64 SATP 寄存器

- mode：是否启用 虚拟内存
- 页表 的物理地址

#### Address Space Layout

#### Context switching

## 总结

## Q

- OS 也运行在虚拟内存之上，有什么好处？ -->
