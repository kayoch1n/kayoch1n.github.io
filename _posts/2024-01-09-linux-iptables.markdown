---
toc: true
layout: "post"
catalog: true
title: "“管中窥豹”"
subtitle: "从一个 tun ping demo 认识 Linux netfilter 框架"
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

这篇笔记要从一个 demo 说起。原程序是 [github上面一个开源的rust网络通信组件的example](https://github.com/smoltcp-rs/smoltcp/blob/main/examples/ping.rs)，可以使用 tun 接口进行ping。因为我对 tun 接口以及 netfilter 的了解几乎是零，所以就有了这篇学习笔记，这篇笔记的主题是 netfilter，tun 接口的相关笔记在[下一篇文章]({{ site.url }}/blog/linux-tuntap)。

## Python example

用 Python 改写了下这个 example，下文简称 tunping

```python
import fcntl
import os
import struct
import argparse
# 需要安装 scapy
from scapy.all import IP, ICMP, raw

IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
TUNSETIFF = 0x400454ca

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src', required=True, help="source IP address")
    parser.add_argument('-d', '--dst', required=True, help="destination IP address")
    args = parser.parse_args()

    ip_req = IP(src=args.src, dst=args.dst) / ICMP(type=8, code=0) / '1145141919810'.encode()

    # 打开一个 tun 接口
    with open("/dev/net/tun", mode='r+b', buffering=0) as f:
        # 关联上 tun0 这个名称
        bs = struct.pack("16s"+"H","tun0".encode(), IFF_TUN|IFF_NO_PI)
        fcntl.ioctl(f, TUNSETIFF, bs, False)

        length = os.write(f.fileno(), raw(ip_req))
        print(f"{length} byte(s) sent: {ip_req}")

        rsp = os.read(f.fileno(), 28)
        ip_rsp = IP(rsp)
        print(f"{len(rsp)} byte(s) received: {ip_rsp}")
    
main()
```

### How to run it?

这个 demo 不能直接运行。需要先创建 tun 接口以及配置 iptables

```bash
# 创建 tun 接口。
# 配置 user 为ubuntu之后，tunping 就可以在不需要root权限的情况下执行。
sudo ip tuntap add dev tun0 mode tun user ubuntu
# 配置 IPv4 地址和 netmask
sudo ip addr add 192.168.69.100/24 dev tun0
# 拉起来
sudo ip link set dev tun0 up
```

tun 接口的部分在[下一篇笔记]({{ site.url }}/blog/linux-tuntap)。简单说一下就是，通过 fd 写入 tun 接口的数据，会被视为 Linux 从 tun 接口**接收**到的 IP packet；这一点跟寻常的物理接口不一样，因为当你创建一个socket fd、主动绑定物理接口（的IP地址）并写入数据后，这些数据是从物理接口**发送**出去的。

```bash
# tunping 脚本单靠tun0接口无法实现正常ping，需要配置 iptables
sudo iptables -t nat -A POSTROUTING -s 192.168.69.0/24 -j MASQUERADE
# 然后打开Linux内核的ip转发功能。可以先看下打开了没 sysctl net.ipv4.ip_forward
sudo sysctl net.ipv4.ip_forward=1
# 执行 tunping
python3 tunping.py -d 119.29.29.29 -s 192.168.69.1
```

```
41 byte(s) sent: IP / ICMP 192.168.69.1 > 119.29.29.29 echo-request 0 / Raw
28 byte(s) received: IP / ICMP 119.29.29.29 > 192.168.69.1 echo-reply 0
```

> 成功的话可以看到以上输出。
> 
> P.S. 发包的源地址(192.168.69.1)和 tun0 的IP地址(192.168.69.100)**不同**，原因见后。

## Linux netfilter

`iptables` 是一个运行在用户态的工具，被用来操作 Linux 内核的 [网络数据包框架 netfilter](https://en.wikipedia.org/wiki/Netfilter)。netfilter 里面有四个模块，包括 `ip_tables`, `ip6_tables`, `arp_tables`和`ebtables`，对应有 4 个命令工具 `iptables`, `ip6tables`, `arptables` 和 `ebtables`，使用者可以分别使用这四个工具操作 IPv4/IPv6 packets、ARP packets和 Ethernet frames。

netfilter 处理数据包的抽象全景图如下所示。这个流程是一个有向无环图，被分割成若干个用 table 和 chain 共同标识的节点，入口和出口分别都只有一个。有的资料管这些节点叫做 hooks。Linux 内核中的所有数据包都会进入这个流程，遍历其中的某一条路径，具体视协议而定。

![netfilter](https://i.stack.imgur.com/NHq7t.png)

每一条路径宛如一个流水线，每个节点可以包含多个规则(rule)。一个规则包括TARGET 和可选的 match，当数据包走到某个节点的时候，内核会检查该节点的规则的match是否能和数据包匹配上，如果ok就会执行对应的 TARGET ，否则遍历下一条规则，如此循环执行。用户可以**添加、修改or删除**节点里的规则。其中，

- match 表示条件，例如 `iptables` 支持的源地址`-s`，输入接口`-o`，协议 `-p`等等；
- TARGET 表示采取的动作，可能会导致数据包被 drop 掉，可能会修改数据包的某些字段，也可能啥也没发生就遍历下一跳规则等等。例如，iptables 所支持的 TARGET 有 SNAT(源地址NAT)，LOG(写入内核日志)等等。

关于 match 和 TARGET ，更详细的列表可以参考 `man iptables-extensions`。netfilter 的其中一个用途是实现有状态的防火墙。

这个命名方式（“table”和“chain”）容易造成误解。“table”让人联想到DB的table，给人一种table以及table里的内容可以任意添加的错觉；实际上，“table”是固定的，[用户无法创建 table](https://askubuntu.com/q/316990/925210)。以 iptables 为例，iptables 总共只有5个table，其中4个分别是上图的`filter`(默认),`raw`,`filter`,`mangle`，外加一个我在Wikipedia和archlinux wiki上面都找不到图的`security`。与其说是“table”，不如说是对处理节点的标签 tag。chain倒是可以添加or删除，有点类似 CI 流水线的“stage”概念。

### iptables

在 netfilter 中，IP packet 的处理过程如下图所示：

![IPv4 packets 处理过程](https://www.frozentux.net/iptables-tutorial/images/tables_traverse.jpg)

这个流程总共有三条不同的路径，分别对应三种场景:

1. source localhost 
    - **进程**往接口发送 IPv4 packet
    - Local Process -> `OUTPUT` -> Routing Decision -> `POSTROUTING` -> NETWORK
    - [上一篇文章]({{ site.url }}/blog/linux-routing)的多网卡路由配置，其实就是这条路径的 Routing Decision 节点处起作用；
2. destination localhost: 
    - **进程**从接口接收到 IPv4 packet
    - NETWORK -> `PREROUTING` -> Routing Decision -> `INPUT` -> Local Process
3. forwarded packets: 
    - 内核从一个接口接收到 IPv4 packet，并发送到另一个接口
    - NETWORK -> `PREROUTING` -> Routing Decision -> `FORWARD` -> Routing Decision -> `POSTROUTING` -> NETWORK

这篇文章详细讲述了它们将分别以何种顺序[遍历不同的chain和table](https://www.frozentux.net/iptables-tutorial/iptables-tutorial.html#TRAVERSINGOFTABLES)。

### Track IPv4 packets using iptables

为了学习 Linux 处理packet流程，可以使用 iptables 在所有处理节点配置 LOG ，并且通过查看内核日志来追踪 IPv4 packet 如何在 netfilter 中流动。由于 iptables 涉及的节点比较多，有4个table共13个chain，方便起见使用以下脚本进行批量操作：

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
    # 注意log prefix 最长29个字符，超过则会截断
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

1. `sudo ./logpkt setup 119.29.29.29`：在 iptables 的所有节点添加两条rule，分别针对源地址和目的地址 119.29.29.29 的IP packet打一条带上特定的前缀的log；
2. `sudo ./logpkt teardown 119.29.29.29`：删除按照上一步骤添加的 rule；
3. `./logpkt show`：使用 `dmesg` 捞取对应规则产生的系统日志。
    - iptables 的 LOG target 会把日志写入到内核的ring buffer

执行 tunping 并观察日志：

```bash
sudo ./logpkt setup 119.29.29.29
python3 tunping.py -s 192.168.69.1 -d 119.29.29.29
./logpkt show
```

发包的日志：

```log
[Jan14 11:48] raw-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000011] mangle-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] nat-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000010] mangle-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] filter-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] mangle-POSTROUTING [114514]IN= OUT=eth0 SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000002] nat-POSTROUTING [114514]IN= OUT=eth0 SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

reply 的日志：
```log
[  +0.004704] raw-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000005] mangle-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000005] mangle-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] filter-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=tun0 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

接下来逐条日志仔细研究下这个数据包走过了 netfilter 的哪些路径。

#### Coming from tun0

首先是前面三条日志，数据从 NETWORK **进入**到netfilter。从这里可以看出程序写入tun fd的 ICMP msg，被内核视为从从tun0接收的数据包。

```log
[Jan14 11:48] raw-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000011] mangle-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] nat-PREROUTING [114514]IN=tun0 OUT= MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=64 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

> `tunping`：packet 进入 raw PREROUTING 节点。

前面也说了，这一点跟物理接口不同。当你往物理接口写入数据的时候，数据是从 Local Process 进入 netfilter 的，走的路径是上面提到的 source localhost 路径。执行 `ping -c1 119.29.29.29 -I eth0` 对比看一下日志就能看出这一点

```
[Jan14 11:54] raw-OUTPUT [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000005] mangle-OUTPUT [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000003] nat-OUTPUT [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000002] filter-OUTPUT [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
[  +0.000001] nat-POSTROUTING [114514]IN= OUT=eth0 SRC=172.16.16.15 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=54074 DF PROTO=ICMP TYPE=8 CODE=0 ID=24112 SEQ=1
```

> `ping -c1 119.29.29.29 -I eth0`：packet 进入 raw OUTPUT 节点。


#### Forwarded to eth0

```log
[  +0.000010] mangle-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
[  +0.000003] filter-FORWARD [114514]IN=tun0 OUT=eth0 MAC= SRC=192.168.69.1 DST=119.29.29.29 LEN=41 TOS=0x00 PREC=0x00 TTL=63 ID=1 PROTO=ICMP TYPE=8 CODE=0 ID=0 SEQ=0
```

> packet 进入到 FORWARD chains，**TTL 减少 1**。
> 
> P.S. 这里 IN 和 OUT 都非空，iptables 可以用 `-i` 和 `-o` 同时 match

回到 tunping 的日志。packet 经过两个 FORWARD chains 之后 TTL 的值减少1，从64变成63。在 FORWARD 之前有一个 routing decision，我猜就是在这一步内核通过路由表等信息判断出 DST=119.29.29.29 要使用默认路由(eth0)，因此OUT从空字符串变成 eth0。

此外，`net.ipv4.ip_forward` 起作用的时机也是在这一次 routing decision，这一点可以通过 `sysctl net.ipv4.ip_forward=0` 之后再执行并观察日志来验证。假如 `net.ipv4.ip_forward=0`，packet 在 netfilter 的 traversal 在第一次 Routing Decision 就会结束，根本不会有两个 FORWARD chains 以及后续的所有日志。 

可以看出 `tunping` 实际上走的是forwarded packets路径，从一个网卡 IN=tun0 被转发到 OUT=eth0。

#### MASQUERADE

之后 packet 来到 nat POSTROUTING。packet SRC=192.168.69.1，这是 tun0 的 IPv4 地址，跟物理网卡 eth0 172.16.16.15 不是一个子网。主机的网关在收到 reply 的时候，不会认为 DST=192.168.69.1 的 packet 要转发给当前主机；即使 tun0 配置成跟 eth0 同一个子网也不行，因为 tun0 并不是一个真正的物理接口，网关也无从知晓这个地址对应当前主机。所以这个 ICMP msg 是收不到 reply 的。

因此需要 MASQUERADE 规则发挥作用了。MASQUERADE 类似于 SNAT，能够修正出包的源地址(如何？)，同时也能根据 conntrack 自动修正后续 reply 的目的地址。使用 MASQUERADE 还是 SNAT 取决于[源地址是否会发生变化](https://unix.stackexchange.com/a/264540/325365)。MASQUERADE 将这个 ICMP msg 的 SRC 修正为物理网卡的IP地址 172.16.16.15，这样一来网关在收到后续 reply 的时候就知道要转发给当前主机；而 SNAT 需要指定一个静态的IP地址。

```bash
sudo iptables -t nat -A POSTROUTING -s 192.168.69.0/24 -j MASQUERADE
```

> 对所有源地址跟 192.168.69.0/24 位于同一网络的 packet 应用 MASQUERADE


使用 MASQUERADE 规则是有条件的。在这个例子中，只有 IPv4 源地址跟 tun0 处于同一个子网并且和 tun0 的地址不一样，IP packet 才能进入 FORWARD chain，MASQUERADE 才能起作用；否则 routing decision 根本不会让 IP packet 进入 FORWARD。这跟 _路由器_ 或者说 _网关_ 的使用场景一致：网关从网卡 _a_ 接收来自 _A_ 的网络的 packet，转发到网卡 _b_ 连接的 _B_ 网络。这也是为什么前面执行脚本时指定源地址跟 tun0 同一个子网的原因。

```
[root@695fc1ccaaa6 ayumu]# python3 tunping.py -d 119.29.29.29 -s 192.168.1.1   
41 byte(s) sent: IP / ICMP 192.168.1.1 > 119.29.29.29 echo-request 0 / Raw
^CTraceback (most recent call last):
  File "tunping.py", line 31, in <module>
    main()
  File "tunping.py", line 27, in main
    rsp = os.read(f.fileno(), 28)
KeyboardInterrupt
```

> 该ICMP msg的源地址 192.168.1.1 跟 tun0 192.168.69.100/24 不在同一个子网，无法被转发。

在 outbound 方向，MASQUERADE 起作用的节点是 nat POSTROUTING；在 inbound 方向，MASQUERADE 起作用的节点可能是 nat PREROUTING。

#### Reply from remote

```log
[  +0.004704] raw-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000005] mangle-PREROUTING [114514]IN=eth0 OUT= MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=172.16.16.15 LEN=41 TOS=0x08 PREC=0x60 TTL=56 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

>  reply 进入到 PREROUTING，目的地址为物理网卡的地址 **172.16.16.15**

后续来自119.29.29.29的 reply （IN=eth0）间接证明了在发包的时候，IP packet的源地址被成了eth0的地址 172.16.16.15（本地和远程之间至少还有一层NAT）

```log
[  +0.000005] mangle-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] filter-FORWARD [114514]IN=eth0 OUT=tun0 MAC=52:54:00:d4:4b:49:fe:ee:f5:ba:3d:ed:08:00 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
[  +0.000002] mangle-POSTROUTING [114514]IN= OUT=tun0 SRC=119.29.29.29 DST=192.168.69.1 LEN=41 TOS=0x08 PREC=0x60 TTL=55 ID=1 PROTO=ICMP TYPE=0 CODE=0 ID=0 SEQ=0
```

>  reply 也进入到 FORWARD chains，**TTL 减少 1**

reply (IN=eth0)同样要走 forwarded packets 路径。在这之前 DST 已经从物理网卡的地址 172.16.16.15 变成了 tun0 的地址 192.168.69.1，这可能发生在 nat PREROUTING（猜测）。

再经过两个 FORWARD chains 之后 TTL 减少 1，从56变成55。 reply (IN= OUT=tun0)将会被dispatch到使用tun0的进程，跟发包的时候IN=tun0相对。在整个 tunping 过程中，如果tcpdump对所有接口抓包的话能抓到两个ICMP，分别是进入到tun0的和从eth0发出去的：

```bash
sudo tcpdump -n -i any 'icmp and (dst 119.29.29.29 or src 119.29.29.29)'
```

```log
16:50:51.458202 IP 192.168.69.1 > 119.29.29.29: ICMP echo request, id 0, seq 0, length 21
16:50:51.458230 IP 172.16.16.15 > 119.29.29.29: ICMP echo request, id 0, seq 0, length 21
16:50:51.462920 IP 119.29.29.29 > 172.16.16.15: ICMP echo reply, id 0, seq 0, length 21
16:50:51.462929 IP 119.29.29.29 > 192.168.69.1: ICMP echo reply, id 0, seq 0, length 21
^C
4 packets captured
4 packets received by filter
0 packets dropped by kernel
```

不过我有一点不明白： reply 的目的地址在 mangle PREROUTING 之后变成了 192.168.69.1，但是没出现 nat PREROUTING 的日志。暂时没找到关于 MASQUERADE 在 reply 何时起作用的资料，记录一下问题先。

## Conclusion

1. netfilter 是linux 内核处理packet的框架；用户可以通过 iptables 干预内核处理 IP packet 的过程；
2. tunping 通过往 tun0 的 fd 写入 ICMP msg，使 ICMP msg 从 tun0 接口进入 netfilter 并且被转发到 eth0 接口，最后发送到目的主机；同时在转发之后修改 packet 的源地址为 eth0 的地址，达到类似NAT的效果收到 reply，最终实现了 ping 的功能。

![tunping]({{ site.url }}/assets/2024-01-09-tunping.svg)

## Reference

- [netfilter 遍历过程](https://upload.wikimedia.org/wikipedia/commons/3/37/Netfilter-packet-flow.svg)
- [iptables 遍历过程](https://www.frozentux.net/iptables-tutorial/iptables-tutorial.html#TRAVERSINGOFTABLES):
  - [过程图](https://www.frozentux.net/iptables-tutorial/images/tables_traverse.jpg)

