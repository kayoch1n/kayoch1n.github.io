---
toc: true
toc_sticky: true
title:  "x86/x86_64函数调用"
date:   2021-02-27 17:15:38 +0800
categories:
  - blog 
tags: 
  - pwn
---
# 一些总是在要用的时候想不起来的芝士点

## calling convention

对于用户空间的函数调用，x86和x86_64的参数传递方式有所不同，可以写个代码观察结果：

```c
#include <stdio.h>

int main() {
    printf("%d,%d,%d,%d,%d,%d!\n",2,3,4,5,6,7);
    return 0;
}
```

在64-bit的ubuntu上用`gcc debug.c -o debug`编译，然后在`gdb debug`打开，用`disas main`命令dump出main函数的汇编指令：
```
   0x0000000000000652 <+8>:     pushq  $0x7
   0x0000000000000654 <+10>:    mov    $0x6,%r9d
   0x000000000000065a <+16>:    mov    $0x5,%r8d
   0x0000000000000660 <+22>:    mov    $0x4,%ecx
   0x0000000000000665 <+27>:    mov    $0x3,%edx
   0x000000000000066a <+32>:    mov    $0x2,%esi
   0x000000000000066f <+37>:    lea    0x9e(%rip),%rdi        # 0x714
   0x0000000000000676 <+44>:    mov    $0x0,%eax
   0x000000000000067b <+49>:    callq  0x520 <printf@plt>
```

可见，第1~6个参数分别通过rdi, rsi, rdx, rcx, r8d和r9d寄存器传递，从第7个开始的参数通过栈传递。

类似地，编译32-bit程序`gcc debug.c -o debug -m32`后查看汇编指令，可见所有参数均通过栈传递。

```
   0x00000539 <+28>:    push   $0x7
   0x0000053b <+30>:    push   $0x6
   0x0000053d <+32>:    push   $0x5
   0x0000053f <+34>:    push   $0x4
   0x00000541 <+36>:    push   $0x3
   0x00000543 <+38>:    push   $0x2
   0x00000545 <+40>:    lea    -0x19e8(%eax),%edx
   0x0000054b <+46>:    push   %edx
   0x0000054c <+47>:    mov    %eax,%ebx
   0x0000054e <+49>:    call   0x3b0 <printf@plt>
```

总结一下x86以及x86_64下用户调用的参数传递方式：
- x86: rdi, rsi, rdx, rcx, r8d and r9d + 栈
- x86_64: 栈

## system call

用户程序需要借助系统调用才能完成像I/O、fork以及execve等等在内的操作。根据[这篇文章](https://blog.packagecloud.io/eng/2016/04/05/the-definitive-guide-to-linux-system-calls/)，在linux中，用户可以通过使用 int 0x80 指令触发中断，从而切换到特权空间；而0x80则表示这个中断将会执行系统调用。

### 中断指令

- eax: 某个系统调用的号码
- ebx, ecx, edx, esi, edi, ebp 分别传递第1~6个参数

### system call table

/usr/include/asm/unistd_32.h
/usr/include/asm/unistd_64.h

### shell

```cpp
#include <stdio.h>
#include <unistd.h>

int main() {
    const char* argv[] = {"/bin/sh", NULL};
    execve(argv[0], argv, NULL);
    return 0;
}
```

## Reference

1. [x86调用约定](https://zh.wikipedia.org/wiki/X86%E8%B0%83%E7%94%A8%E7%BA%A6%E5%AE%9A)
2. [The Definitive Guide to Linux System Calls](https://blog.packagecloud.io/eng/2016/04/05/the-definitive-guide-to-linux-system-calls/)