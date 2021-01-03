---
classes: wide
layout: single
title:  "记一次分享 switch 截图的过程"
date:   2020-08-21 23:15:38 +0800
diary: "今天用刷子打出11杀，真是最高にhighでやつだ！"
categories: 
  - blog
tags:
  - switch
---
今明两天是 Splatoon2 的祭典活动，主题是“这个世界上是先有母鸡呢还是先有蛋”。菜鸡好不容易打出11杀，结果发现截图只能分享到推或者 fb ;就算开了加速器，也不能分享（其实用脚趾头想一下，加速器是不会支持这个功能的）。那么只好从现有的工具下手了。

## 思路

把大象塞进冰箱需要几步?很容易想到一个点是:
1. 让同一个局域网内可以科学上网的机器开一个HTTP代理;
2. 让switch和这个机器连同一个局域网;
   1. 有支持 5G 频段 WIFI 的小伙伴请注意检查下5G热点和2.4G热点名称是不是一样的;
   2. 因为switch貌似不支持5G频段，如果是一样的，请确保switch和机器连的都是2.4G的那个~
3. 在switch的无线热点设置里启用代理，并且把这个机器的IP及代理的端口填上去。

## 关于梯子

平时有用到 v2rayN(Windows端)，就想这软件应该可以开给局域网（这不是废话么😓要不然SwitchyOmega怎么用）。

1. 打开主界面 -> v2rayN 设置，勾选“允许来自局域网的连接”;
2. 参数设置-> Core基础设置，记录下本地监听端口。

然而尴尬的问题来了，基础设置里面的协议是 SOCKS(亲测是SOCKS5)，不能修改的，而且老任的switch不支持。

![Settings socks]({{ site.url }}/assets/2020-08-21-settings-socks.png)

## HTTP TO SOCKS5

仔细想一下，浏览器是用HTTP的，SwitchyOmega 肯定是有特别的技巧能够将 HTTP 流量转换为 SOCKS 流量。网上有一个叫 [Privoxy](http://www.privoxy.org/) 的工具，可以实现转发HTTP到SOCKS服务的功能。

具体操作方法是:

1. 安装 Privoxy ;
2. 在安装目录下面找到配置文件 config.txt，添加以下两项内容:
   1. `forward-socks5t / 127.0.0.1:10808 .` 将 HTTP 流量转发到 10808 端口;
   2. `listen-address 0.0.0.0:8118` 为了能让 switch 用上，还得设置下监听本地端口以及IP地址;这里的 IP 地址不要用 localhost 或者 127.0.0.1，否则 switch 连不上的;
3. 启动 Privoxy.
4. 启动 v2rayN.

## 最后的最后

可以在MinGW的窗口用以下命令检查下是否成功:

```shell
curl https://www.google.com -v -s -o /dev/null
# 提示DNS解析失败

export http_proxy=localhost:8118
export https_proxy=localhost:8118
# 设置代理的环境变量

curl https://www.google.com -v -s -o /dev/null
# 输出信息如果有200，那就是设置成功了
```

设置成功之后，就可以在switch设置好代理服务器的IP和端口（如果不知道 Privoxy 机器的IP，可以 `ipconfig` 看一下无线网卡的），最后就可以使用 switch 的分享截图功能啦。

## 插曲1-gpg校验签名
这个其实不是必须的。。。官网提供工具本身及签名文件下载，但是Windows 没有自带的校验签名的工具（日常，windows上要啥没啥）。不过，如果安装了 MinGW  的 git，那么gpg工具会随着 MinGW 一块安装上;因此可以用 MinGW 里的 gpg 命令校验签名:

```shell
gpg --verify privoxy_setup_3.0.28.exe.asc privoxy_setup_3.0.28.exe
# 首次校验可能失败，提示本地没有某某密钥，比如这里的 F14381F4A112856D

gpg --keyserver pgp.mit.edu --recv-key F14381F4A112856D
# 从远程key服务器上安装密钥 F14381F4A112856D

gpg --verify privoxy_setup_3.0.28.exe.asc privoxy_setup_3.0.28.exe
# 校验成功，显示以下信息
# gpg: Signature made 2018年12月31日  4:05:47
# gpg:                using RSA key F14381F4A112856D
# gpg: Good signature from ""Lee Rian"" [expired]
# gpg: Note: This key has expired!
# Primary key fingerprint: A64E FD41 6B94 82FD 3734  7AC9 F143 81F4 A112 856D
```

用gpg校验签名有效，但是提示密钥过期。因为我不懂签名这块的知识，是否安全还不好把握。


## 插曲2-启动失败

过程中可能会出现启动失败的问题。如果失败信息显示 "fatal error init error_log() can't open logfile '.\privoxy.log'"，可尝试以下步骤排查:

1. 安装目录下有没有 privoxy.log ?如果没有就给新建一下;
2. 新建之后问题依旧，尝试把这个log删掉，自己从别的地方新建一个然后丢到这个目录。
   1. 如果OK，就说明是权限问题:程序安装在 "C:\Program Files (x86)" 下，一开始这个log的所有者是 Administrator，Privoxy 由普通用户启动后读写这个文件失败;因此需要一个由普通用户创建的log。

![File owner]({{ site.url }}/assets/2020-08-21-file-owner.png)

## Reference

1. [使用 privoxy 转发 socks 到 http](http://einverne.github.io/post/2018/03/privoxy-forward-socks-to-http.html)
2. [下载Privoxy](http://www.privoxy.org/)
3. [如何使用gpg校验签名](https://www.apache.org/info/verification.html#CheckingSignatures)
