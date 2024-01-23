---
toc: true
layout: "post"
catalog: true
title: "从 tun ping 看 Linux netfilter 框架"
date:   2024-01-09 21:40:38 +0800
header-img: "img/gz-SCNBC.jpg"
categories:
  - blog
tags:
  - network
  - Netfilter
  - iptables
  - tcpdump
  - dmesg
  - scapy
  - tun
---

这篇笔记要从一个 demo 说起。原程序是 [github上面一个开源的rust网络通信组件的example](https://github.com/smoltcp-rs/smoltcp/blob/main/examples/ping.rs)，可以使用 tun 设备进行ping。因为我对tun设备以及iptables 的了解几乎是零，所以想学习一下相关知识，于是就有了这篇笔记。


## Python example

用 Python 改写了下这个 example，下文简称 tunping

```python
import fcntl
import os
import struct
import argparse
from scapy.all import IP, ICMP, raw

IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
TUNSETIFF = 0x400454ca

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src', required=True)
    parser.add_argument('-d', '--dst', required=True)
    args = parser.parse_args()

    ip_req = IP(src=args.src, dst=args.dst) / ICMP(type=8, code=0) / '1145141919810'.encode()

    with open("/dev/net/tun", mode='r+b', buffering=0) as f:
        bs = struct.pack("16s"+"H","tun0".encode(), IFF_TUN|IFF_NO_PI)
        fcntl.ioctl(f, TUNSETIFF, bs, False)

        length = os.write(f.fileno(), raw(ip_req))
        print(f"{length} byte(s) sent: {ip_req}")

        rsp = os.read(f.fileno(), 28)
        ip_rsp = IP(rsp)
        print(f"{len(rsp)} byte(s) received: {ip_rsp}")
    
main()
```

## How to run it?

这个 demo 不能直接运行，我需要先创建 tun 接口以及配置 iptables

```bash
# 创建 tun 接口。配置user为ubuntu之后，tunping 脚本就可以在不需要root权限的情况下执行。
sudo ip tuntap add dev tun0 mode tun user ubuntu
# 配置 IP 地址和 netmask
sudo ip addr add 192.168.69.100/24 dev tun0
# 拉起来
sudo ip link set dev tun0 up
```

```bash
# tunping 脚本单靠tun0接口无法实现正常ping，需要配置 iptables
sudo iptables -t nat -A POSTROUTING -s 192.168.69.0/24 -j MASQUERADE
# 然后打开Linux内核的ip转发功能。可以先看下打开了没 sysctl net.ipv4.ip_forward
sudo sysctl net.ipv4.ip_forward=1
```

```
41 byte(s) sent: IP / ICMP 192.168.69.1 > 119.29.29.29 echo-request 0 / Raw
28 byte(s) received: IP / ICMP 119.29.29.29 > 192.168.69.1 echo-reply 0
```

> 最后通过 `python3 tunping.py -d 119.29.29.29 -s 192.168.69.1` 执行，成功的话可以看到以上输出

接下来讲述这个过程涉及到的一些概念。

## tun interface

`/dev/net/tun` 是个特殊的文件，它是个[字符设备(character special)](https://unix.stackexchange.com/a/60147/325365)，按照字节流读取or写入，`/dev/urandom` 也是这种。打开 `/dev/net/tun` 并通过 ioctl 关联上一个名字之后，内核就会创建一个虚拟的网络接口，这个接口并无对应的物理网卡。默认情况下同一时刻只能有一个进程打开 `/dev/net/tun` 并关联上同样的名称，当另一个进程尝试打开`/dev/net/tun` 并关联一样的名称时，系统会报一个错误 EBUSY(device or resource busy)。

tunping 以此法获得一个fd，通过read/write进行收发packet。这跟 Linux `ping` 不一样：传统做法是创建一个 raw socket 并且绑定一个物理网卡对应的接口，packet 将会**从接口被发送**出去，系统日志(dmesg)体现为 OUT=eth0，无 IN。使用tunping的时候， packet 是**从tun0接口进入** netfilter，在dmesg中体现为 IN=tun0，无OUT。Linux `ping` 和 `tunping` 在 netfilter 中所经过的路径是不一样的，见后文。


## netfilter and iptables

netfilter 是一个由 Linux 内核提供的、用于[管理网络数据包的框架](https://en.wikipedia.org/wiki/Netfilter)，包括 `ip_tables`, `ip6_tables`, `arp_tables`和`ebtables`四个内核模块，以及对应的4个能运行在用户态的工具`iptables`, `ip6tables`, `arptables` 和 `ebtables`。使用者可以分别使用这四个工具操作 IPv4/IPv6、ARP packets和Ethernet frames。在 netfilter 中，IP packet 的处理过程被分割成若干个用 table 和 chain 共同标识的节点，如下图所示：

![IP packets 处理过程](https://www.frozentux.net/iptables-tutorial/images/tables_traverse.jpg)

所有IP packet都会进入到上图所示的处理流程。这个流程总共有三条不同的路径，分别对应三种场景:

1. source localhost: 进程往接口发送了一个 IP packet。
    - Local Process -> `OUTPUT` -> Routing Decision -> `POSTROUTING` -> NETWORK
    - [上一篇文章]({{ site.url }}/blog/linux-routing)的多网卡路由配置，其实就是这条路径的 Routing Decision 节点处起作用；
2. destination localhost: 进程从接口接收到IP packet；
    - NETWORK -> `PREROUTING` -> Routing Decision -> `INPUT` -> Local Process
3. forwarded packets: 内核从一个接口接收到IP packet，并发送到另一个接口。
    - NETWORK -> `PREROUTING` -> Routing Decision -> `FORWARD` -> Routing Decision -> `POSTROUTING` -> NETWORK

这篇文章详细讲述了它们将分别以何种顺序[遍历不同的chain和table](https://www.frozentux.net/iptables-tutorial/iptables-tutorial.html#TRAVERSINGOFTABLES)。

说个题外话，个人觉得这个命名方式（“table”和“chain”）容易造成误解。“table”让人联想到DB的table，给人一种table以及table里的内容可以任意添加的错觉；实际上，“table”是固定的，[用户无法创建 table](https://askubuntu.com/q/316990/925210)。iptables 总共只有5个table，其中4个分别是上图的`filter`(默认),`raw`,`filter`,`mangle`，外加一个我在Wikipedia和archlinux wiki上面都找不到图的`security`。与其说是“table”，不如说是对处理节点的标签 tag。不过chain倒是可以添加or删除。


## Track packets in kernel 

每个节点可以有多条“规则”，用户可以通过 `iptables` 实现插入、修改or删除规则，达到过滤or修改 IP packet的目的。为了理解内核处理packet流程，我使用 iptables 在所有处理节点配置 log 并且通过查看内核日志来追踪 IPv4 packet 如何在 netfilter 中流动。由于iptables 涉及4个table共13个chain，为了方便起见使用以下脚本进行批量操作：

```bash
#!/bin/bash

# ./logpkt
prefix="114514"

if [[ $1 == "setup" ]]; then
    option=-A
elif [[ $1 == "teardown" ]]; then
    option=-D
elif [[ $1 == "show" ]]; then
    dmesg -H | grep "\[$prefix\]" --color=auto
    exit 0
else
    echo unknown operation "\"$1\""
    exit -1
fi

subnet=$2
if [[ -z $subnet ]]; then
    echo missing ip address
    exit -1
fi

set -e
while read i
do
    table=${i% *}
    chain=${i#* }
    # 注意log prefix 最长三十个字符，超过则会截断
    iptables -t $table $option $chain -s $subnet -j LOG --log-prefix "$table-$chain [$prefix]" --log-level debug
    iptables -t $table $option $chain -d $subnet -j LOG --log-prefix "$table-$chain [$prefix]" --log-level debug
done <<< 'raw PREROUTING
mangle PREROUTING
nat PREROUTING
mangle INPUT
filter INPUT
mangle FORWARD
filter FORWARD
raw OUTPUT
mangle OUTPUT
nat OUTPUT
filter OUTPUT
mangle POSTROUTING
nat POSTROUTING'

for table in nat raw mangle filter; do
    iptables -L --line-numbers -t $table -n
done
```

这个脚本有三个功能: 

1. `sudo ./logpkt setup 119.29.29.29`：在 iptables的所有节点添加两条rule，分别针对源地址和目的地址 119.29.29.29 的IP packet打一条带上特定的前缀的log；
2. `sudo ./logpkt teardown 119.29.29.29`：删除按照上一步骤添加的 rule；
3. `./logpkt show`：使用 dmesg 捞取对应规则产生的系统日志。


执行 tunping 并观察日志：


```bash
sudo ./logpkt setup 119.29.29.29
python3 tunping.py -s 192.168.69.1 -d 119.29.29.29
./logpkt show
```

发包的日志：
```
[Jan14 11:48] raw-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000011] mangle-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] nat-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000010] mangle-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] filter-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] mangle-POSTROUTING [114514]IN= OUT=eth0 SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000002] nat-POSTROUTING [114514]IN= OUT=eth0 SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

回包的日志：
```
[  +0.004704] raw-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000005] mangle-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000005] mangle-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] filter-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=tun0 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

### packet sent from tun0

```
[Jan14 11:48] raw-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

> 写入 tun0 fd的packet进入 raw PREROUTING

首先，从第一条日志可以看出程序写入tun fd的ICMP packet会从tun0**进入**到netfilter(IN=tun0)。这一点跟 `ping -I tun0` 存在很大不同。执行 `ping -c1 119.29.29.29 -I tun0` 对比看一下日志，可以知道 `ping -I tun0` 是从 Local Process进入


```
[Jan14 11:54] raw-OUTPUT [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000005] mangle-OUTPUT [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000003] nat-OUTPUT [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000002] filter-OUTPUT [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000001] nat-POSTROUTING [114514]IN= OUT=tun0 SRC=192.168.69.100 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
```

> `ping -I tun0` 实际上走的是source localhost路径

由于tun0并不对应真正的物理网卡，`ping -I tun0` 发出去的包不会被发到物理介质上，即使在任意接口上使用 tcpdump 也不会被抓到。

### packet forwarded to eth0

```
[  +0.000010] mangle-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] filter-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

> 进入到 forwarded packets 路径，**TTL减少 1**

回到 tunping 的日志。packet 经过两个 FORWARD CHAINS 之后 TTL 的值减少1，从64变成63，而且OUT从空字符串变成 eth0。可以看出 `tunping` 实际上走的是forwarded packets路径，从一个网卡 IN=tun0 被转发到 OUT=eth0。

假如 `net.ipv4.ip_forward=0`，packet 在 netfilter 的 traversal 在第一次 Routing Decision 就会结束，根本不会有两个FORWARD CHAINS 以及后续的所有日志。由此可知 `net.ipv4.ip_forward` 起作用的地方是第一次 Routing Decision，这一点可以通过关闭 `net.ipv4.ip_forward`之后再执行并观察日志来验证。

### MASQUERADE and reply

之后 packet 来到 nat POSTROUTING。tun0 只是让packet进入到netfilter，如果没有对应的规则处理的话也还是发不出去，所以先前配置的 MASQUERADE 规则在这里就起作用了。MASQUERADE 类似于 SNAT，能够修正出包的源地址，同时也能根据conntrack自动修正后续回包(reply)的目的地址。使用 MASQUERADE 还是 SNAT 取决于[源地址是否会发生变化](https://unix.stackexchange.com/a/264540/325365)。

```
[  +0.004704] raw-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

> 回包进入到 raw PREROUTING，目的地址为物理网卡的地址 **172.16.16.15**


后续来自119.29.29.29的回包（IN=eth0）间接证明了发包的源地址被成了eth0的地址 172.16.16.15（本地和远程之间至少还有一层NAT）。

```
[  +0.000005] mangle-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] filter-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=tun0 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

> 回包也进入到 forwarded packets 路径，**TTL减少 1**

回包(IN=eth0)同样要走forwarded packets路径。经过两个 FORWARD chains 之后 TTL 减少 1，从56变成55，而且 OUT变成 tun0，表示从 eth0 转发到 tun0。回包(IN= OUT=tun0)将会被dispatch到使用tun0的进程，跟发包的时候IN=tun0相对。在整个过程中，tcpdump能抓到两个ICMP发包，分别是进入到tun0的和从eth0发出去的：

```bash
sudo tcpdump -n -i any 'icmp and (dst 119.29.29.29 or src 119.29.29.29)'
```

```
16:50:51.458202 IP 192.168.69.1 > 119.29.29.29: ICMP echo request, id 0, seq 0, length 21
16:50:51.458230 IP 172.16.16.15 > 119.29.29.29: ICMP echo request, id 0, seq 0, length 21
16:50:51.462920 IP 119.29.29.29 > 172.16.16.15: ICMP echo reply, id 0, seq 0, length 21
16:50:51.462929 IP 119.29.29.29 > 192.168.69.1: ICMP echo reply, id 0, seq 0, length 21
^C
4 packets captured
4 packets received by filter
0 packets dropped by kernel
```

不过我有一点不明白：回包的目的地址在 mangle PREROUTING 之后变成了 192.168.69.1，但是没出现 nat PREROUTING 的日志。暂时没找到关于 MASQUERADE 在回包何时起作用的资料，记录一下问题先。

## Conclusion

- netfilter 是 linux 内核中负责处理网络 packet 的框架。这个处理过程存在若干用 tables and chains 标记的 “hooks”，用户可以通过 iptables 修改 hook 达到过滤or修改 packet 的目的。
- 写入 tun 接口的数据会被当作从 tun 接口进入 netfilter 的 packet。

## Reference

- [iptables遍历过程](https://www.frozentux.net/iptables-tutorial/iptables-tutorial.html#TRAVERSINGOFTABLES):
  - [过程图](https://www.frozentux.net/iptables-tutorial/images/tables_traverse.jpg)
- [Linux tuntap driver](https://docs.kernel.org/networking/tuntap.html)
