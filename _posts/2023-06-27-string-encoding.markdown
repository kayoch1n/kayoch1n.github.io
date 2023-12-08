---
toc: true
layout: "post"
catalog: true
title: "String Encoding"
date:   2023-06-27 21:40:38 +0800
header-img: "img/gz-canton-tower.jpg"
categories:
  - blog
tags:
  - encoding 
---


# string encoding

## TL;DR

- 编码（encoding）是将字符串变成一种用于进程间通信的格式的过程。
    - 所谓的进程间通信包括但不限于文件I/O，网络I/O，共享内存。从这个角度上看有那么一点序列化的意思。字符串类型是**编程语言**意义上的概念，这些类型的变量需要经过编码才能进行传输。
- 编码需要解决的一个问题是，如何区分不同的字符。
- JSON也是一种序列化格式。同一个数据的JSON格式再不考虑字段顺序的情况下总是唯一的；但是同一个字符串却有多种编码格式（encoding format）。
    - 比如 ascii，gb2312 和 utf-8。

ascii是坠坠坠常见的编码格式了，别的大部分的编码格式都兼容ascii。说一下 gb2312 和 utf-8。

## 内存布局


先搞两个样本，分别使用不同的编码，看下中文字符串在文件中是如何存储的：


```python
with open('gb2312.properties', mode='w', encoding='gb2312') as f:
    f.write('''#测试编码
test.password=admin
''')

with open('utf8.properties', mode='w', encoding='utf-8') as f:
    f.write('''#测试编码
test.password=admin
''')
```


```bash
%%bash
file gb2312.properties
file utf8.properties
```

    gb2312.properties: ISO-8859 text
    utf8.properties: UTF-8 Unicode text


貌似file命令认不出来gb2312编码（😂

### gb2312


```bash
%%bash
hexdump -C gb2312.properties
```

    00000000  23 b2 e2 ca d4 b1 e0 c2  eb 0a 74 65 73 74 2e 70  |#.........test.p|
    00000010  61 73 73 77 6f 72 64 3d  61 64 6d 69 6e 0a        |assword=admin.|
    0000001e


0x23 是 `#` 的ascii值，后面跟着的若干个值就是 gb2312 编码之后的内容。在gb2312中，

- 按照**区码**和**位码**（合称为“区位码”）来区分不同的中文字符
- 双字节
- 编码方式：字节1=区码+0xa0，字节2=位码+0xa0

上面的 "测" 字位于 18区 0x42位，因此 测 在 gb2312 编码下的二进制表示是 18+0xa0=0xb2, 0x42+0xa0=0xe2


```python
"测".encode('gb2312')
```




    b'\xb2\xe2'



### utf8 

UTF-8的全称是 8-bit Unicode Transformation Format。

- 按照code point区分不同的字符。实际上这里的code point就是 Unicode 的字符集。
- 多字节

unicode code point 和 UTF-8 字节的对应关系如下：

|First code point|Last code point|Byte 1|Byte 2|Byte 3|Byte 4|数量
|-|-|-|-|-|-|-|
|U+0000|U+007F|0xxxxxxx(0~127)||||128|
|U+0080|U+07FF|110xxxxx(192~223)|10xxxxxx|||2048|
|U+0800|U+FFFF|1110xxxx(224~239)|10xxxxxx|10xxxxxx||65536|
|U+10000|U+10FFFF|11110xxx(240~247)|10xxxxxx|10xxxxxx|10xxxxxx|2Mi|


回过头来看前面的样本：


```bash
%%bash
hexdump -C utf8.properties
```

    00000000  23 e6 b5 8b e8 af 95 e7  bc 96 e7 a0 81 0a 74 65  |#.............te|
    00000010  73 74 2e 70 61 73 73 77  6f 72 64 3d 61 64 6d 69  |st.password=admi|
    00000020  6e 0a                                             |n.|
    00000022



所有中文字符的code point都在U+0800~U+FFFF这个范围。utf8编码一个中文需要三个字节。“测” 的 code point 是U+6D4B，所以 测 在 utf-8 编码下的字节是 0xe6, 0xb5, 0x8b。可以用以下代码加深理解：

```python
bits = bin(0x6d4b)[2:].rjust(16, '0')
b1, b2, b3=bits[:4], bits[4:10], bits[10:]
b1, b2, b3=int(f'1110{b1}', 2), int(f'10{b2}', 2), int(f'10{b3}', 2)
print(hex(b1), hex(b2), hex(b3))
```

    0xe6 0xb5 0x8b

稍微验证一下：


```python
'测'.encode('utf8')
```


    b'\xe6\xb5\x8b'



## The notorious `UnicodeDecodeError`

用 utf-8 方式打开 gb2312 编码的文件会报错：


```python
with open('gb2312.properties', encoding='utf8') as f:
    print(f.read())
```


    ---------------------------------------------------------------------------

    UnicodeDecodeError                        Traceback (most recent call last)

    File /usr/local/python3.9/lib/python3.9/codecs.py:322, in BufferedIncrementalDecoder.decode(self, input, final)
        319 def decode(self, input, final=False):
        320     # decode input (taking the buffer into account)
        321     data = self.buffer + input
    --> 322     (result, consumed) = self._buffer_decode(data, self.errors, final)
        323     # keep undecoded input until the next call
        324     self.buffer = data[consumed:]


    UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb2 in position 1: invalid start byte


这个算是我刚学计算机的时候坠常遇见的和坠头痛的问题了。。。上班之后快四年的今天才搞明白，真的离谱Orz

从上面的UTF-8的表格可以看出来，每个字符串编码之后的第一个字节的范围只能落在：
- 0~0x7F (0xxxxxxx)
- 0xC0~0xDF (110xxxxx)
- 0xE0~0xEF (1110xxxx)
- 0xF0~0xF7 (11110xxx)

0xB2不在上面任何一个区间内，所以必然报错。用对了编码格式才能正常打开：


```python
with open('gb2312.properties', encoding='gb2312') as f:
    print(f.read())
```

    #测试编码
    test.password=admin
    


至于经典 “烫烫烫” 梗，其实就是编码格式搞错了，只是通过某种编码格式得到的字节的值正好可以被另一种编码格式解码而已。

## UTF-8 in JSON

有时候REST API可能会返回以下内容：

```JSON
{"code":0,"status":"502 Bad Gateway","desc":"\346\234\252\347\237\245\351\224\231\350\257\257"}
```

desc 字段对应的内容并非乱码，而是一段中文经过UTF编码之后塞进JSON结构的结果。这里的JSON用八进制表示每个字符，实际上用16进制也是ok的；如果用16进制，desc字段对应的内容就会是 `\xe6\x9c\xaa\xe7\x9f\xa5\xe9\x94\x99\xe8\xaf\xaf`。可以用下面的代码来还原内容：


```python
b = bytearray()
# https://stackoverflow.com/a/29169004/8706476
b.extend(map(ord, '\346\234\252\347\237\245\351\224\231\350\257\257'))
b.decode()
```

输出内容为 “未知错误”。
