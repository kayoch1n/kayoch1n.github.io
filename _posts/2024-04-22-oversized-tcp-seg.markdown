---
toc: true
layout: "post"
catalog: true
title: "关于IP包长度超过MTU这件事"
date:   2024-04-22 21:40:38 +0800
header-img: "img/sz-transmission-tower.jpg"
categories:
  - blog
tags:
  - network
  - nic
  - mtu 
---

```bash
sudo tcpdump -n -v -i eth0 'tcp port 443 and (tcp[((tcp[12] & 0xf0) >> 2)] = 0x16)'
```

> 抓取 _tls handshake_ message。这条filter的解释可以见[这里](https://stackoverflow.com/a/39644735/8706476)



```
tcpdump: listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
11:44:18.527544 IP (tos 0x0, ttl 64, id 24715, offset 0, flags [DF], proto TCP (6), length 557)
    172.16.16.15.44834 > 109.244.236.76.443: Flags [P.], cksum 0x0d5c (correct), seq 2313579562:2313580079, ack 414341838, win 502, length 517
11:44:18.535277 IP (tos 0x68, ttl 56, id 61055, offset 0, flags [DF], proto TCP (6), length 3817)
    109.244.236.76.443 > 172.16.16.15.44834: Flags [P.], cksum 0x253c (incorrect -> 0x1abc), seq 1:3778, ack 517, win 501, length 3777
11:44:18.536134 IP (tos 0x0, ttl 64, id 24717, offset 0, flags [DF], proto TCP (6), length 133)
    172.16.16.15.44834 > 109.244.236.76.443: Flags [P.], cksum 0x07d9 (correct), seq 517:610, ack 3778, win 501, length 93
```


在抓包 tls handshake 的时候发现了一个问题：第二条记录是一个收包，IP包的长度3817字节超过了MTU。而且 TCP checksum 是错误的。这条记录包括了 server certificate 在内的数据。

```
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
    link/ether 52:54:00:d4:4b:49 brd ff:ff:ff:ff:ff:ff
    altname enp0s5
    altname ens5
```

> `ip link show eth0` 查看 eth0。MTU 只有**1500**字节。


## tcpdump 的 _length_ 

首先，IP那一行的 3817 是整个 IP packet的长度(total length)，下一行的 3777 是 TCP payload的长度。tcp header里没有用来表示长度的字段；估计这个是tcpdump根据ip total length减去tcp header length算出来的。

在这里，3817=20(ip header)+20(tcp header)+3777(tcp payload)，已经超过了MTU。

## 内核参数 `generic-receive-offload`

查资料发现内核存在[跟网卡offloading有关的参数](https://docs.kernel.org/networking/segmentation-offloads.html)，可以用 `ethtool` 查看是否启用


```bash
ethtool -k eth0 | grep offload
```

其中，generic-receive-offload 会使**网卡**先将一些小的IP 包组装成更大的包再传递给内核

```
tcp-segmentation-offload: off
generic-segmentation-offload: off [requested on]
generic-receive-offload: on
large-receive-offload: off [fixed]
# ...
```

这里可以看见 `generic-receive-offload` 是打开状态，其他都是关闭的。这个feature貌似不会重新计算TCP checksum，所以tcpdump显示TCP checksum是错误的。先使用 ethtool 将 gro 关掉：

```bash
# sudo ethtool -K eth0 gro on # 开启
sudo ethtool -K eth0 gro off # 关闭
```

然后再次抓包：

```
tcpdump: listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
14:41:19.886613 IP (tos 0x0, ttl 64, id 6541, offset 0, flags [DF], proto TCP (6), length 557)
    172.16.16.15.60612 > 109.244.236.76.443: Flags [P.], cksum 0x8f82 (correct), seq 826074211:826074728, ack 2169594896, win 502, length 517
14:41:19.894981 IP (tos 0x68, ttl 56, id 32654, offset 0, flags [DF], proto TCP (6), length 1456)
    109.244.236.76.443 > 172.16.16.15.60612: Flags [.], cksum 0xc2c8 (correct), seq 1:1417, ack 517, win 501, length 1416
14:41:19.895866 IP (tos 0x0, ttl 64, id 6545, offset 0, flags [DF], proto TCP (6), length 133)
    172.16.16.15.60612 > 109.244.236.76.443: Flags [P.], cksum 0xfd0d (correct), seq 517:610, ack 3778, win 501, length 93
```

这个时候 headshake 所在IP包的长度就变成 1456 了，tcp checksum也正常了。但是少掉的 server certificate跑哪里去了呢？答案是server certificate被“拆成”多个tcp segment了，或者准确的说它本来就是用多个segment进行传输的~用wireshark打开，可以看见server hello的最后一个msg中会有一个3 Ressembled TCP segments的提示。

## 内核参数 `tcp-segmentation-offload`

tso 则可以在**发送** tcp segment 的时候由**网卡**将一个大包拆成多个小包，减少内核的CPU处理时间。

在 tso 开启的情况下发送一个data很长的http request

```bash
dd if=/dev/urandom bs=2048 count=1 | base64 > data.dat
curl ${simple_server}:8080 -d @data.dat
```

```
14:51:18.967598 IP local.56686 > simple-server.webcache: Flags [P.], seq 1:2886, ack 1, win 251, options [nop,nop,TS val 991521530 ecr 3767871536], length 2885: HTTP: POST / HTTP/1.1
```

可见总长度为 2885 的 tcp payload。当 tso 关掉之后，就会变成小于1500字节了。（准确的来说是小于 MSS）

```
14:54:56.527433 IP localhost.51608 > simple-server.webcache: Flags [.], seq 1:1413, ack 1, win 251, options [nop,nop,TS val 991739090 ecr 3767925926], length 1412: HTTP: POST / HTTP/1.1
14:54:56.527435 IP localhost.51608 > simple-server.webcache: Flags [.], seq 1413:2825, ack 1, win 251, options [nop,nop,TS val 991739090 ecr 3767925926], length 1412: HTTP
14:54:56.527436 IP localhost.51608 > simple-server.webcache: Flags [P.], seq 2825:2886, ack 1, win 251, options [nop,nop,TS val 991739090 ecr 3767925926], length 61: HTTP
```

根据这一差别，我猜 tcpdump 抓包的时机在于syscall之后、网卡之前：如果tcpdump抓包的时机在syscall，则无论tso开启与否，都应该抓到一个大packet而不是三个小packet。

## ICMP Code 3 Type 4

PMTUD 是一个用于探测通往目标的链路的 MTU的方法，在linux上可以通过使用 ping `-s` 参数指定 payload 大小来实现。wiki 描述到当一个主机收到一个长度超过 MTU 的包时会回复ICMP Code3 Type4；一方可以多次发送payload长度逐渐增加的packet，直到接收到ICMP Code3 Type4，此时就能得知这个链路上的MTU。

但是要再现这个行为是挺困难的：一方面要让超长的packet真正从网卡发送出去：调整网卡的mtu使其大于实际链路的mtu，但使用 setsockopt 设置 DF + sendto 长 packet 的时候会返回 message too long，packet 其实未被发送出去，这个可能跟操作系统有关？另一方面，不同的目标对于超长的packet的处理方式不一样，像 github.com, stackoverflow.com 确实能支持很大的 MTU，而有的目标貌似对于超过1500的ip包直接不返回任何东西，疑似通过 iptables drop 掉了，比如国内的网站 baidu.com，zhihu.com。

## P.S. `AF_NETLINK` socket

通过 strace 观察syscall，可以知道这个操作网卡feature的工具是通过给 `AF_NETLINK` socket 发消息来完成的。

```
socket(AF_NETLINK, SOCK_RAW, NETLINK_GENERIC) = 3
```

同样 iproute2 工具包里的东西也是用的 `AF_NETLINK` socket 来干活的。

```
socket(AF_NETLINK, SOCK_RAW|SOCK_CLOEXEC, NETLINK_ROUTE) = 4
```

顺便一提，这玩意儿是 linux-only，macos是没有的。
