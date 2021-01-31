---
toc: true
toc_sticky: true
title:  "Ubuntu 安装各种程序"
date:   2021-01-30 12:15:38 +0800
categories:
  - blog 
tags: 
  - ubuntu
  - docker
  - perl
---
# Contents

操作系统是64bit的ubuntu 18.04 。

```
ubuntu@VM-0-5-ubuntu:~$ cat /etc/os-release 
NAME="Ubuntu"
VERSION="18.04.4 LTS (Bionic Beaver)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 18.04.4 LTS"
VERSION_ID="18.04"
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
VERSION_CODENAME=bionic
UBUNTU_CODENAME=bionic
```

## gdb

使用者可以通过编辑 ~/.gdbinit 文件改变 gdb 的默认行为。关于如何编辑 ~/.gdbinit 使调试窗口高亮显示，可以参见[这个回答](https://stackoverflow.com/a/17341335/8706476)(亲测第一种办法不会高亮显示C代码)。

### glibc 源代码，符号表及调试信息

安装[glibc源代码](https://stackoverflow.com/questions/29955609/include-source-code-of-malloc-c-in-gdb#comment99820296_29956038)、[x86及x86_64的符号表及调试信息](https://stackoverflow.com/a/20019999/8706476)：

```shell
sudo apt-get install glibc-source libc6-dbg libc6:i386 libc6-dbg:i386
```
按照这个办法下载的源代码是个压缩包。然后得让[gdb找到已安装的源代码](https://stackoverflow.com/a/29956038/8706476)：

```shell
cd /usr/src/glibc
# 解压缩
tar xf glibc-2.27.tar.xz
# 编辑 `~/.gdbinit`，这样就不需要每次启动gdb都手敲一遍命令
echo "dir /usr/src/glibc/glibc-2.27/malloc" >> ~/.gdbinit
```

然鹅在gdb中调试过程中发现源代码大多数变量都被编译优化掉了ㄟ( ▔, ▔ )ㄏ只能勉强看下执行到源码哪里。


## Perl

ubuntu自带

### 安装模块

按照这个[CPAN的指引](http://www.cpan.org/modules/INSTALL.html)可以使用 cpan 安装perl模块，而ubuntu自带cpan。输入cpan后进入交互命令模式配置源:

```shell
# Optional. 
# Modify mirror
cpan[16]> o conf urllist
    urllist           
        0 [http://www.cpan.org/]
Type 'o conf' to view all configuration items


cpan[17]> o conf urllist pop http://www.cpan.org/
Please use 'o conf commit' to make the config permanent!


cpan[18]> o conf commit
commit: wrote '/home/ubuntu/.cpan/CPAN/MyConfig.pm'

cpan[20]> o conf urllist push http://mirrors.aliyun.com/CPAN/
Please use 'o conf commit' to make the config permanent!


cpan[21]> o conf commit
commit: wrote '/home/ubuntu/.cpan/CPAN/MyConfig.pm'

cpan[22]> o conf urllist
    urllist           
        0 [http://mirrors.aliyun.com/CPAN/]
Type 'o conf' to view all configuration items


cpan[23]> quit
```

```shell
# 1. 启用cpan
sudo cpan App::cpanminus
# 2. 安装你要的模块，比如HTML::Entities
sudo cpanm HTML::Entities
```

### 食用方法

[Scripts](https://stackoverflow.com/a/13161719/8706476) to convert HTML entities to characters:

```shell
curl http://cms.nuptzj.cn/about.php?file=about.php | perl -MHTML::Entities -pe 'decode_entities($_);' > about.php
```
## Docker 

### 从离线package安装

按照[官网的安装指引](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-from-a-package)，先下载离线：
- 查看ubuntu的 **开发代号**(codename)`lsb_release -c`。18.04的开发代号是bionic；
- 查看操作系统的 **架构**(architecture)`uname -a`。64bit对应的是amd64；
- 前往 `https://download.docker.com/linux/ubuntu/dists/{codename}/pool/stable/{arch}`下载这三样东西：`containerd.io`, `docker-ce-cli` 和 `docker-ce.`

然后执行安装命令即可

```shell
sudo dpkg -i /path/to/package.deb
```

### 配置镜像源(可选)
vim 打开 `/etc/docker/daemon.json`（不存在就创建一个），把下面这个镜像源加进去：
```json
{
  "registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"]
}
```
执行以下命令重启docker使配置生效。**注意**：第二条命令会停掉所有容器而且不会重新启动：

```shell
systemctl daemon-reload
systemctl restart docker  # 停掉所有容器而且不会重新启动
```

### 启动docker失败的可能的原因

第一次执行docker命令的时候可能会遇到这个问题：

```
docker: Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Post http://%2Fvar%2Frun%2Fdocker.sock/v1.40/containers/create: dial unix /var/run/docker.sock: connect: permission denied.
```

意思是当前用户没有权限操作`unix:///var/run/docker.sock`。这里有一个[解决方法](https://stackoverflow.com/a/48957722/8706476)，把当前用户加入到docker的用户组里面去。或者直接加权限也行：

```shell
sudo chmod 666 /var/run/docker.sock
```

### 常用命令

- 拉镜像 `docker pull <name:tag>`
- 列出所有本地镜像 `docker images`
- 启动一个容器，并映射本地端口8080到其容器的80 `docker run -itd -p 8080:80 <image:tag>`
- 进入容器内部 `docker exec -it <container-id> bash`
- 停掉一个容器 `docker stop <container-id>`
- 清除停掉的容器 `docker containers prune`

## radare2

### 背景[]~(￣▽￣)~*

- 需要反编译二进制程序；
- 网上的IDA Pro都上传到百度网盘。但是我不喜欢百度的产品，所以就不找IDA Pro的下载资源；
- 公司的电脑不方便研究这个东西。所以就想在服务器上面弄；
- 服务器是ubuntu，没有gui；
- snowman反编译出来的c++代码不好看；
- 终于找到radare2+r2ghidra作为IDA Pro的替代品。

### 从源码编译安装主件 radare2

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

### 从源码编译安装插件 r2ghidra

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