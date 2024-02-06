---
toc: true
layout: "post"
catalog: true
title: "“暗度陈仓”"
subtitle: "从一个 VPN demo 认识 Linux TUN 接口"
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

`/dev/net/tun` 是个特殊的文件，它是个[字符设备(character special)](https://unix.stackexchange.com/a/60147/325365)(`/dev/urandom` 也是个字符设备)，可按照字节流读取or写入 IPv4 packets(L3)。[上一篇笔记]({{ site.url }}/blog/linux-iptables)提到，通过 fd 写入 tun 接口的数据，会被视为操作系统从 tun 接口**接收**到的 IPv4 packets。与之对应，当 netfilter 中的 IPv4 packets 在离开时，如果 OUT 为该 tun 接口，进程就能从 tun fd 读取到该数据。从API的角度来看，写入socket的数据，和写入一个 tun fd 的数据，两者的处理方式是不同的：

- 写入 socket 的数据，会被装上协议的 header，然后才进入 netfilter；
- 写入 tun fd 的数据，会直接进入 netfilter，API 对调用者的协议一无所知。

简单来说，tun 接口给予了使用者直接写入/读取 netfilter 数据的便利。这篇笔记将从一个用 Python 实现的简单 VPN demo 出发，学习 Linux tun 接口的工作方式。

## Device allocation

用 `open` 打开 `/dev/net/tun` 并通过 `ioctl` 关联上一个名字之后，内核就会创建一个虚拟的网络接口，这个接口并无对应的物理网卡。具体 API 操作可以查看[这里](https://docs.kernel.org/networking/tuntap.html#network-device-allocation)。默认情况下，同一时刻只能有一个进程打开 `/dev/net/tun` 并关联上同样的名称，比如说 `tun0`，此时如果另一个进程尝试打开`/dev/net/tun` 并关联`tun0`时，系统就会报告一个错误 EBUSY(device or resource busy)。当进程结束后，`tun0`就会被删除。

不过，凡事有例外。有一种使用场景是，先用 iproute2 创建、配置并启动 `tun0`，然后在程序中用 API 打开并读写 `tun0`。因为命令本身是一个单独的进程， `tun0` 如果是被进程独占的话结束之后就会被删除，这种使用场景就无从实现了。那实际上 iproute2 是怎么做的呢？可以用 `strace ip tuntap add dev `tun0` mode tun`观察一下

```c
// ...
open("/dev/net/tun", O_RDWR)            = 4
ioctl(4, TUNSETIFF, 0x7fffefed4140)     = 0
ioctl(4, TUNSETPERSIST, 0x1)            = 0
close(4)                                = 0
// ...
```

前面两个创建接口的 syscall 跟[这里](https://docs.kernel.org/networking/tuntap.html#network-device-allocation)描述一致。第三个 syscall 用了一个叫做 `TUNSETPERSIST` 的request code，根据[网上的资料](https://www.gabriel.urdhr.fr/2021/05/08/tuntap/#persistent)，这个值可以使虚拟接口在进程退出之后避免被操作系统删除。

### See resolved macros

用 Python 创建 tun 接口需要使用一些宏作为参数，但是这些宏在 CPython 中并未定义，得用点代码把这些值打出来：

```c
void dump_hex(void* mem, size_t size) {
    printf("dump %lu bytes starting from %p:\n", size, mem);
    const char* ptr = (const char*)mem;
    for (size_t i = 0; i < size; i++)
    {
        printf("%02X", ptr[i]);
    }
    printf("\n");
}
```

顺便提一个找出头文件在文件系统中实际位置的方法，方便查找本地的头文件源代码：

```bash
gcc cmem.cc -H -fsyntax-only 2>&1 | grep tun.h
```

## Use tun in a VPN demo

tun 虚拟接口常被用来实现 VPN。这个 VPN demo 根据[这篇文章](https://lxd.me/a-simple-vpn-tunnel-with-tun-device-demo-and-some-basic-concepts)用 Python 改写而成，源代码在[这里](https://github.com/kayoch1n/vpndemo-azuna)。

在这个 demo 中，client `eth0` 的地址是 192.168.96.2，server 的  `eth0`  的地址是 192.168.96.3，网关是 192.168.96.1。这里记录一下我对这个VPN的理解。


### Docker container

因为涉及到修改 netfilter 和路由表，我怕把主机搞坏，所以用容器模拟一下；而且容器可以默认用户是root，敲命令可以不需要 sudo，而且容器用完之后删掉即可。说起容器，有不少人会将它跟虚拟机划等号，忘了容器其实是一个用户态进程的本质。可以用 `docker inspect` 命令查看容器对应的进程的 pid

```bash
docker inspect setsuna | grep -i PID
```

执行 iptables 修改 netfilter 需要 root 特权，容器在默认情况下无法使用。根据 `man capabilities` 的描述，传统上 Unix 将进程分成特权进程(euid=0, root/superuser)和非特权进程，通过 euid 和 egid 等方式检查权限；而 Linux 则是将root的特权划分成更小的单元，称为 capability ，可以为进程单独设置一个或多个 capabilities。为了能够修改 netfilter ，需要在 `docker-compose.yml` 中加入名为 `NET_ADMIN` 的 capabilities；此外，还需要[映射 `/dev/net/tun` 设备](https://stackoverflow.com/a/68071527/8706476)，否则 demo 打开该设备会失败：

```yml
version: "3.8"
services:
  shizuku:
    # ... 其他字段
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun
```

最后，需要在宿主机上面打开IPv4转发，以及[允许 netfilter 输出所有 namespace 的日志](https://stackoverflow.com/questions/39632285/how-to-enable-logging-for-iptables-inside-a-docker-container#comment94786207_39681550)：

```bash
sudo sysctl net.ipv4.ip_forward=1
sudo sysctl net.netfilter.nf_log_all_netns=1 # 如果你要观察日志的话。。。
```

P.S. 有的资料提到 docker 允许[单独为容器指定部分内核参数](https://docs.docker.com/compose/compose-file/compose-file-v3/#sysctls)，这个说法恐怕会造成迷惑。我本地（ubuntu 18.04，docker 24）试了一下发现，在宿主机 IPv4 转发关闭的情况下，容器尽管使用了 `sysctls: [net.ipv4.ip_forward=1]` 也还是不能转发IPv4。而且这跟宿主机的 user 是否为 root 无关，哪怕容器本身是用 sudo 拉起来的也一样。不过，反过来就不一样了，在宿主机打开该开关的情况下，容器使用了 `net.ipv4.ip_forward=0` 雀食能禁止 IPv4 转发，猜测 docker 只能关闭内核参数，而不能主动打开被宿主机关闭的内核参数。


### Client

client 的发包和收包过程大致是：

1. netfilter 将所有进程产生的 IPv4 packets 路由到 `tun0` ；
2. client.py 从 `tun0` 读取 IPv4 packets，加密之后写入 UDP socket；
3. client.py 从 UDP socket 接收到数据，解密之后写入 `tun0` ；
4. netfilter 将 reply dispatch 到对应的进程。

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn-client.svg)

> 在 netfilter 中，同一个 packet 先后遍历了两次 source localhost(1 and 3) 以及两次 destination localhost(14 and 16)。

#### Route all traffics to `tun0` 

首先，client 通过 iproute2 修改默认的 main 路由表配置，将所有 IPv4 packet 都路由到 `tun0` 接口：

```sh
ip route add 0/1 dev tun0
ip route add 128/1 dev tun0
```

这里 `0/1` 和 `128/1` 是 [CIDR](https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing) 的表示方式：`0/1` 表示选择第一个bit是0的所有 IPv4 地址，`128/1` 表示选择第一个bit是1的所有IPv4。两者组合在一起等同于默认路由 `0.0.0.0/0`，使用这两个路由组合可以避免跟已有的默认路由产生冲突。一般来说在用CIDR的时候会采取最长掩码匹配策略，这两个CIDR的 subnet mask 长度都是1，因此比默认路由（长度为0）的优先级高。

上述两条路由起作用的时机是 Local Process 之后的第一次 routing decision，在 OUTPUT chain 之前；这次 routing decision 将 IPv4 packet 的源地址设定为 `tun0` 的 IPv4 地址，就像下面的 `ping -c1 119.29.29.29` 产生的日志一样：

```log
[Jan 31 21:15] IN= OUT=tun0 SRC=10.8.0.2 DST=119.29.29.29 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=61307 DF PROTO=ICMP TYPE=8 CODE=0 ID=41 SEQ=1
```

> 可见在 raw OUTPUT 之前，源地址已经是 `tun0` 的 IPv4 地址 `10.8.0.2`
> 
> 日志：`iptables -I OUTPUT -t raw -d 119.29.29.29 -j LOG`

#### "Forward" IPv4 packets from `tun0` to  `eth0` 

当 IPv4 packet 被路由到 `tun0` 之后，client 就能从 `tun0` fd 读取到完整的 IPv4 packet，而不仅仅是 payload data。这一点非常重要：对于server来说，保留了 IP 目的地址，server 才能将 packet 转发到真正的目的地。

client 将从 `tun0` fd 读取的 IPv4 packet 作为 UDP 的 payload 原封不动地发送给 server。在实际应用中这部分逻辑可能更复杂，client 可以将 payload 加密，而且传输协议也不限于 UDP。为了避免这个 UDP datagram 又跑到 `tun0` 造成死循环了，路由表需要再加一个发往目的地 server 使用默认网关的路由：

```sh
ip route add 192.168.96.3 via 192.168.96.1
```

<!-- #### Dispatch replies to local process -->

### Server

server 的发包和收包过程大致如下：

1. server.py 从 UDP socket 中接收到加密的数据，将其解密后写入 `tun0` ；
2. netfilter 从 `tun0` 收到 IPv4 packets，将其转发到  `eth0` ，MASQUERADE 修改源地址地址，发往真正的目的地；
3. netfilter 从  `eth0`  收到 reply，MASQUERADE 矫正目的地址，转发到 `tun0` ；
4. server.py 从 `tun0` 中读取到 IPv4 packets，将其加密后往 UDP socket 发送。

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn-server.svg)

> 同一个 packet 先后遍历 destination localhost(5)、两次 forwarded packets(7 and 10) 以及一次 source localhost(12)。
> 
> 另外 server 的 `tun0` 的 IPv4 地址其实根本没用上。

#### MASQUERADE

相比 client，server 不需要设置路由，但是要设置 iptables。server 从 UDP socket 中读取的 IPv4 packet 源地址仍然是 client `tun0` 的 10.8.0.2。为了能正常收到 reply，server 设置了一条针对源地址 10.8.0.2/16 使用 MASQUERADE 的规则：

- 在 forward incoming IPv4 packets 的 POSTROUTING chain，IPv4 packet 的源地址如果是 10.8.0.2/16 就会被修改为 192.168.96.3，也就是 server  `eth0`  的地址；
- 在 forward reply 的过程中，reply 的目的地址会从 192.168.96.3 被修改为 10.8.0.2。这可能是 nat PREROUTING 利用 conntrack 实现的。

> [上一篇关于 iptables 的笔记]({{ site.url }}/blog/linux-iptables#masquerade)也记录过 MASQUERADE。

### More on iptables

还有两条 iptables 规则值得注意：

```bash
iptables -I FORWARD 1 -i tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -I FORWARD 1 -o tun0 -j ACCEPT
```

这两条规则都指定了顺序为1，目的是要让 FORWARD chain 确保 VPN 的 traffic 不会被 DROP 掉。虽然 chain 的默认 policy 可能是 ACCEPT，但是如果单纯依赖这一点而不用规则显式 ACCEPT 的话，就有可能出现 VPN traffic 被别的规则 DROP 掉的问题。而且，考虑到将来可能的用途，包括 LOG、修改默认 policy or precedence，显式 ACCEPT 也是一个好的习惯。

### Bugs

### Conclusion

写入 tun 接口 fd 的数据，会被当作一个 IPv4 packet（而不是payload） 进入 netfilter；当一个 IPv4 packet 带着 OUT=tun 接口离开 netfilter 的时候，使用者可以通过 tun 接口 fd 读取到它的包括header在内的完整数据，而不只是 payload。tun 接口给予了使用者直接写入/读取 netfilter 数据的便利。

IPv4 packets 从 client 的 `tun0` 的进入，从 server 的 `tun0` 出来，其内容在这期间没有经过任何修改，就像进入了一个隧道一样，进去的时候是啥样，出来的时候也是那个鬼样，反之亦然。不得不佩服协议分层确实是一个精妙的设计！这个 IP 隧道对于所有运行于 IPv4 之上的应用程序来说是透明的，应用程序无需修改or重启即可使用隧道，同时保有上层协议的全部能力（e.g., TCP keepalive）。

最后来一个 vpn demo 的全景图~

![vpn demo client]({{ site.url }}/assets/2024-01-31-tunvpn.svg)


## Reference

- [Linux TUN/TAP](https://docs.kernel.org/networking/tuntap.html#network-device-allocation)
- [A simple VPN (tunnel with tun device) demo and some basic concepts](https://lxd.me/a-simple-vpn-tunnel-with-tun-device-demo-and-some-basic-concepts)
- docker [Compose file V3 reference](https://docs.docker.com/compose/compose-file/compose-file-v3/)