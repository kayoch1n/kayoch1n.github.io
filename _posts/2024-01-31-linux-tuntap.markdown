---
toc: true
layout: "post"
catalog: true
title: "暗度陈仓：Linux TUN 接口"
subtitle: "一个简单的 VPN demo"
date:   2024-01-31 21:40:38 +0800
header-img: "img/sz-transmission-tower.jpg"
categories:
  - blog
tags:
  - network
  - Netfilter
  - iptables
  - docker
  - tun
  - VPN
  - CIDR
  - capabilities
---

`/dev/net/tun` 是个特殊的文件，它是个[字符设备(character special)](https://unix.stackexchange.com/a/60147/325365)(`/dev/urandom` 也是个字符设备)，可按照字节流读取or写入 IP packets(L3)。[上一篇笔记]({{ site.url }}/blog/linux-iptables#执行)提到，通过 fd 写入 tun 接口的数据，会被视为操作系统从 tun 接口**接收**到的 IP packets。与之对应，当 IP packets 离开 netfilter 时，如果 OUT 是一个 tun 接口，进程就能从 tun fd 读取到该数据。Linux 对 socket 和 tun fd 的处理方式是不同的：

- 写入 socket 的数据，会被装上协议的 header，然后才进入 netfilter；
- 写入 tun fd 的数据，如果是有效的 IPv4/IPv6 格式，就会直接进入 netfilter。

简单来说，tun 接口给予了使用者直接写入/读取 netfilter 数据的便利。这篇笔记将从一个用 Python 实现的简单 VPN demo 出发，记录 Linux tun 接口的工作方式。

## TUN 设备

[打开 `/dev/net/tun` 并通过关联上一个名字之后](https://docs.kernel.org/networking/tuntap.html#network-device-allocation)，内核就会创建一个虚拟的网络接口，这个接口并无对应的物理网卡。默认情况下，同一时刻只能有一个进程打开 `/dev/net/tun` 并关联上同样的名称，比如说 `tun0`，此时如果另一个进程尝试打开`/dev/net/tun` 并关联`tun0`时，系统就会报告一个错误 EBUSY(device or resource busy)。当进程结束后，`tun0`就会被删除。

实际上大部分程序，比如 iproute2 的 `ip tuntap add`，在创建 tun 接口的时候，会用一个叫做 `TUNSETPERSIST` 的request code，[这个值](https://www.gabriel.urdhr.fr/2021/05/08/tuntap/#persistent)可以使虚拟接口在进程退出之后避免被操作系统删除。这一点可以用 `strace ip tuntap add dev tun0 mode tun`观察一下

```c
// ...
open("/dev/net/tun", O_RDWR)            = 4
ioctl(4, TUNSETIFF, 0x7fffefed4140)     = 0
ioctl(4, TUNSETPERSIST, 0x1)            = 0
close(4)                                = 0
// ...
```

宏 TUNSETPERSIST 和 TUNSETIFF 在 python 中并未定义，得写一段C代码把这些具体的值打出来。顺便提一个找出头文件在文件系统中实际位置的方法，方便查找本地的头文件源代码：

```bash
gcc cmem.cc -H -fsyntax-only 2>&1 | grep tun.h
```

## VPN demo

tun 虚拟接口常被用来实现 VPN。基于[这篇文章](https://lxd.me/a-simple-vpn-tunnel-with-tun-device-demo-and-some-basic-concepts) 我用 Python 改写了[一个实验demo](https://github.com/kayoch1n/netwlabs/tree/master/lab-vpn/src)。这个 demo 涉及到的 IP 地址如下：

- VPN client: 
  - `eth0` 192.168.96.2/24
  - `tun0` 10.8.0.2/16
- VPN server:
  - `eth0` 192.168.96.3/24
  - `tun0` 10.8.0.1/16
- 网关 192.168.96.1

### 用容器组网

比起直接修改机器的网络设置，用容器组网可以避免一些麻烦，比如配置错了可以直接删掉容器，对宿主机没有影响。关于组网的内容可以参考[这里]({{ site.url }}/blog/network-emu-container)。总的来说需要注意这三个事情：

1. 给予 NET_ADMIN capability
2. 映射 TUN 设备
3. 宿主机打开内核 ipv4 转发

此外，如果要观察日志的话，还得[允许 netfilter 输出所有 namespace 的日志](https://stackoverflow.com/questions/39632285/how-to-enable-logging-for-iptables-inside-a-docker-container#comment94786207_39681550)：

```bash
sudo sysctl net.ipv4.ip_forward=1
sudo sysctl net.netfilter.nf_log_all_netns=1 # 容器内没法使用 dmesg
```

### Client

client 的发包和收包过程大致是：

1. netfilter 将所有 IPv4 packets 路由到 `tun0` (1)；
2. client.py 从 `tun0` 读取 IPv4 packets，加密之后写入 UDP socket (2, 3)；
3. client.py 从 UDP socket 接收到数据，解密之后写入 `tun0` (14, 15)；
4. netfilter 将 reply dispatch 到对应的进程 (16)。

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn-client.svg)

> 按照 [iptables 中的三个路径的说法]({{ site.url }}/blog/linux-tuntap/)，发包 packet 先后遍历两次 source localhost(1 and 3) ，收包 packet 遍历两次 destination localhost(14 and 16)。

#### 路由所有流量到 `tun0` 

首先，client 修改默认的 main 路由表配置，将所有 IPv4 packet 都路由到 `tun0` 接口：

```sh
ip route add 0/1 dev tun0
ip route add 128/1 dev tun0
```

这里 `0/1` 和 `128/1` 是 [CIDR](https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing) 的表示方式：`0/1` 表示选择第一个bit是0的所有 IPv4 地址，`128/1` 表示选择第一个bit是1的所有IPv4。两者组合在一起[等同于默认路由 `0.0.0.0/0`](https://networkengineering.stackexchange.com/a/34475/92883)，使用这两个路由组合可以避免跟已有的默认路由产生冲突。一般来说操作系统在用CIDR的时候会采取[最长掩码匹配策略](https://en.wikipedia.org/wiki/Longest_prefix_match)，这两个CIDR的 subnet mask 长度都是1，因此比默认路由（长度为0）的优先级高。

上述两条路由起作用的时机是 Local Process 之后的第一次 routing decision，在 OUTPUT chain 之前；这次 routing decision 将 IPv4 packet 的源地址设定为 `tun0` 的 IPv4 地址，就像下面的 `ping -c1 119.29.29.29` 产生的日志一样：

```log
[Jan 31 21:15] IN= OUT=tun0 SRC=10.8.0.2 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=61307 DF PROTO=ICMP TYPE=8 CODE=0 ID=41 SEQ=1
```

> 可见在 raw OUTPUT 之前，源地址已经是 `tun0` 的 IPv4 地址 `10.8.0.2`
> 
> 日志：`iptables -I OUTPUT -t raw -d 119.29.29.29 -j LOG`

#### 封装 IPv4 为 UDP

当 IPv4 packet 被路由到 `tun0` 之后，client 就能从 `tun0` fd 读取到完整的 IPv4 packet，包括 IPv4 目的地址，而不仅仅是 payload data。这一点非常重要：对于server来说，保留了 IPv4 目的地址，server 才能将 packet 转发到真正的目的地。client 将 IPv4 packet 作为 UDP 的 payload 原封不动地发送给 server。在实际应用中这部分逻辑可能更复杂，client 可以将 payload 加密，而且传输协议也不限于 UDP。为简单起见，这里的 demo 就是直接发明文。以 ping 为例，下图是最终 client 发送给 server 的 UDP datagram

![UDP datagram]({{ site.url }}/assets/2024-01-31-tunvpn-udp.svg)

> 可见在 ICMP msg 连带 IPv4 header 都作为 UDP 的 payload 出现

另外，为了避免这个 UDP datagram 受到[前面添加的两条路由](./#route-all-traffics-to-tun0)的影响、又跑到 `tun0` 造成死循环，client 的路由表需要再加一个发往目的地 server 使用默认网关的路由：

```sh
ip route add 192.168.96.3 via 192.168.96.1
```

<!-- #### Dispatch replies to local process -->

### Server

server 的发包和收包过程大致如下：

1. server.py 从 UDP socket 中接收到加密的数据，将其解密后写入 `tun0` ；
2. netfilter 从 `tun0` 收到 IPv4 packets，将其转发到  `eth0` ，MASQUERADE 修改源地址，发往真正的目的地；
3. netfilter 从  `eth0`  收到 reply，MASQUERADE 矫正目的地址，转发到 `tun0` ；
4. server.py 从 `tun0` 中读取到 IPv4 packets，将其加密后往 UDP socket 发送。

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn-server.svg)

> 在 netfilter 中，同一个 packet 先后遍历 destination localhost(5)、两次 forwarded packets(7 and 10) 以及一次 source localhost(12)。

#### 设置 iptables MASQUERADE 规则

相比 client，server 不需要设置路由，但是要设置 iptables。server 从 UDP socket 中读取的 IPv4 packet 源地址仍然是 client `tun0` 的 10.8.0.2。为了能正常收到 reply，server 设置了一条针对源地址 10.8.0.2/16 使用 MASQUERADE 的规则：

- 在 forward incoming IPv4 packets 的 POSTROUTING chain，IPv4 packet 的源地址如果是 10.8.0.2/16 就会被修改为 192.168.96.3，也就是 server  `eth0`  的地址；
- 在 forward reply 的过程中，reply 的目的地址会从 192.168.96.3 被修改为 10.8.0.2。这可能是 nat PREROUTING 利用 conntrack 实现的。
- client `tun0` 和 server `tun0` 的 IPv4 地址需要在同一个子网，否则 MASQUERADE 不会起作用，原因见 [上一篇关于 iptables 的笔记]({{ site.url }}/blog/linux-iptables#masquerade)。

### 设置 iptables 其他规则

#### 防止默认drop

client 和 server 都会设置以下两条规则：

```bash
iptables -I FORWARD 1 -i tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -I FORWARD 1 -o tun0 -j ACCEPT
```

这两条规则都指定了顺序为1，目的是要让 FORWARD chain 确保 VPN 的 traffic 不会被 DROP 掉。虽然 chain 的默认 policy 可能是 ACCEPT，但是如果单纯依赖这一点而不用规则显式 ACCEPT 的话，就有可能出现 VPN traffic 被别的规则 DROP 掉的问题。而且，考虑到将来可能的用途，包括 LOG、修改默认 policy or precedence，显式 ACCEPT 也是一个好的习惯。

#### VPN 网关

最后，client 上还有一条使用了 MASQUERADE 的规则

```bash
iptables -t nat -A POSTROUTING -o tun0 -j MASQUERADE
```

这条规则可以让 client 起到 _VPN 网关_ 的作用，让同一个子网下的其他主机不需要各自启动 VPN client 即可使用该 VPN 的能力，其他主机只要设置路由将 traffic 甩到 client 主机。client 本身已经开启 IPv4 转发，而 MASQUERADE 会将转发的 IPv4 的源地址修改为 tun0 的 10.8.0.2，reply 的时候又能自动修正目的地址~

```bash
ip route add 0/1 via 192.168.96.2
ip route add 128/1 via 192.168.96.2
```

> 在第三台主机 192.168.96.3 上设置路由。其中，192.168.96.2 是 client 的 IPv4 地址。

### 结论

<!-- 在发包的时候，VPN client 先将所有 traffic 路由到 `tun0`，利用 `tun0` fd 读取 IP packet ，将 IP packet 打包作为 UDP payload 发送到 server；server从 UDP datagram 中拆箱出 IP packet，利用 `tun0` fd 写入 IP packet，再让 netfilter 转发到真正的目的地。

在处理 reply 的时候，server 上的 netfilter MASQUERADE 还原 reply 的目的地址，转发到 `tun0`， -->

进程发送的 IPv4 packets 在 client 上从 `tun0` 进入，在 server 上也是从 `tun0` 出来，其内容在这期间没有经过任何修改，就像进入了一个隧道一样，进去之前跟出来出来之后的数据是一致的；方向反过来也是如此。这个设计确实有意思：IP 隧道对于所有运行于 IPv4 之上的应用程序来说是透明的，应用程序无需修改or重启即可使用隧道，同时也能保有上层协议的全部能力（e.g., TCP keepalive）。最后来一个 vpn demo 的全景图~

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn.svg)

## 参考资料

- [Linux TUN/TAP](https://docs.kernel.org/networking/tuntap.html#network-device-allocation)
- [A simple VPN (tunnel with tun device) demo and some basic concepts](https://lxd.me/a-simple-vpn-tunnel-with-tun-device-demo-and-some-basic-concepts)
- docker [Compose file V3 reference](https://docs.docker.com/compose/compose-file/compose-file-v3/)
