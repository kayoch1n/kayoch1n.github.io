---
toc: true
classes: wide
layout: single
title:  "国内Linux服务器编译安装radare2+r2ghidra"
date:   2021-01-27 12:10:38 +0800
categories: 
  - blog
tags:
  - radare2
  - r2ghidra
---

# 编译安装radare2+r2ghidra

## 背景

- 需要反编译二进制程序；
- 网上的IDA Pro都上传到百度网盘。但是我不喜欢百度的产品，所以就不找IDA Pro的下载资源；
- 公司的电脑不方便研究这个东西。所以就想在服务器上面弄；
- 服务器是ubuntu，没有gui；
- snowman反编译出来的c++代码不好看；
- 终于找到radare2+r2ghidra作为IDA Pro的替代品。

## 从源码编译安装 radare2

先克隆[radare2](https://github.com/radareorg/radare2)的代码到本地。这个代码库的体积很大，有127M：

```shell
curl -s https://api.github.com/repos/radareorg/radare2 | jq .size | numfmt --to iec --from-unit=1024
# 127M
```
国内克隆github代码库的速度普遍慢的一批，可以使用镜像源[cnpm](github.com.cnpmjs.org)加速，当中的具体原理不明，但是速度蹭蹭的就上去了。

```shell
git clone https://github.com.cnpmjs.org/radareorg/radare2
```

radare2编译过程中会克隆另一个代码库[capstone](https://github.com.cnpmjs.org/aquynh/capstone)，这个代码库大小是41M，也得使用镜像源，所以需要在安装脚本里面找到克隆代码的步骤并且修改代码库的URL。通过grep找到克隆capstone所用到的URL在[shlr/Makefile的41行](https://github.com/radareorg/radare2/blob/5.1.0/shlr/Makefile#L41)：

```
41 CS_URL_BASE=github.com.cnpmjs.org/aquynh/capstone
42 CS_URL=$(GIT_PREFIX)$(CS_URL_BASE).git
43 CS_ARCHIVE=https://$(CS_URL_BASE)/archive
```
安装很简单，按照官方README.md执行就可以了。
```shell
sys/install.sh
```

## 从源码编译安装 r2ghidra

先克隆[radare2](https://github.com/radareorg/r2ghidra)的代码到本地。这个代码库使用到两个子模块，同样道理，.gitmodules的URL需要修改成镜像源实现加速克隆：

```
[submodule "ghidra/ghidra"]
	path = ghidra/ghidra
	branch = r2ghidra
	url = https://github.com.cnpmjs.org/radareorg/ghidra.git
[submodule "third-party/pugixml"]
	path = third-party/pugixml
	url = https://github.com.cnpmjs.org/zeux/pugixml.git
```

光修改了.gitmodules 是不会生效的，需要执行命令[更新子模块的元信息](https://stackoverflow.com/a/914090/8706476)：

```shell
git submodule sync --recursive
```

我打算用cmake。r2ghidra 会安装到一个自动生成的目录，但是要想让radare2识别出这个插件，需要把产物丢到radare2的插件目录。先看下插件的目录是在哪里，以ubuntu为例子：

```shell
r2 -H
# ...
# R2_LIBR_PLUGINS=/usr/local/lib/radare2/5.1.0
# R2_USER_PLUGINS=/home/ubuntu/.local/share/radare2/plugins
# ...
```

这个自动生成的目录是lib/radare2/last，所以要给cmake的安装前缀改成 /usr/local 。不改前缀也可以，这样的话需要把core_ghidra.so拷贝到radare2的插件目录下。

按照官方README.md的操作执行编译。因为我指定了目录 /usr/local，所以需要在安装的时候加上 sudo：

```shell
git submodule init
git submodule update
mkdir build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local ..
make
sudo make install
```

安装成功之后，执行 `r2 -AA /bin/ls`，然后在radare2的命令行里输入 `pdg` 就可以看到反编译的代码了～

```
[0x00005850]> pdg

// WARNING: [r2ghidra] Failed to match type int for variable argc to Decompiler type: Unknown type identifier int

void entry0(undefined8 placeholder_0, undefined8 placeholder_1, int64_t arg3)
{
    undefined8 in_stack_00000000;
    undefined auStack8 [8];
    
    (*_reloc.__libc_start_main)(main, in_stack_00000000, &stack0x00000008, 0x162c0, 0x16330, arg3, auStack8);
    do {
    // WARNING: Do nothing block with infinite loop
    } while( true );
}
[0x00005850]> 
``` 
