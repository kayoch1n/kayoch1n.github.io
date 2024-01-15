---
toc: true
layout: "post"
catalog: true
title: "从一次DNS失效看 Ubuntu DNS 机制"
date:   2023-12-20 21:40:38 +0800
header-img: "img/sz-transmission-tower.jpg"
categories:
  - blog
tags:
  - network
  - ubuntu
  - dns
  - systemd-resolved
---


桥接实验结束之后通过iproute2手动恢复多网卡。发现原先的 DNS 不管用了

```
ubuntu@VM-0-5-ubuntu:~/project$ curl qq.com
curl: (6) Could not resolve host: qq.com
```

众所周知DNS用的端口是53，所以用tcpdump抓包[任意网卡(>=2.2内核)](https://serverfault.com/a/805008/599288)并过滤53端口，结果显示DNS查询发往了127.0.0.53:53，这是一个本地地址。

```
ubuntu@VM-0-5-ubuntu:~/project/ssh$ sudo tcpdump -i any port 53 -n
tcpdump: verbose output suppressed, use -v or -vv for full protocol decode
listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes
16:08:56.985152 IP 127.0.0.1.44529 > 127.0.0.53.53: 40036+ [1au] A? qq.com. (35)
16:08:56.985158 IP 127.0.0.1.44529 > 127.0.0.53.53: 16493+ [1au] AAAA? qq.com. (35)
```

好怪哦，再看一下[是哪个进程在用这个端口](https://www.ibm.com/support/pages/how-can-i-check-if-application-listening-port-and-applications-name)(ubuntu下需要使用sudo否则不显示无权限的进程)：

```
ubuntu@VM-0-5-ubuntu:~$ sudo netstat -anpel | grep 127.0.0.53
tcp        0      0 127.0.0.53:53           0.0.0.0:*               LISTEN      101        18158      1147/systemd-resolv
udp        0      0 127.0.0.53:53           0.0.0.0:*                           101        18157      1147/systemd-resolv
ubuntu@VM-0-5-ubuntu:~/project/kayoch1n.github.io$ cat /proc/1147/cmdline
/lib/systemd/systemd-resolved
```

这个进程来自 /lib/systemd/systemd-resolved，是一个 Ubuntu 上的[后台服务](https://unix.stackexchange.com/q/612416/325365)，这个服务的工作逻辑还比较复杂。正常来说 /etc/resolv.conf 控制 DNS 配置，文件里包含DNS服务器的IP地址，实际上在Ubuntu 上这个文件是一个symlink，指向的文件里包含一个IP地址 127.0.0.53，所以 DNS 请求都会发往 systemd-resolved。

```
ubuntu@VM-0-5-ubuntu:~$ ls /etc/resolv.conf -al
lrwxrwxrwx 1 root root 39 Aug  8  2018 /etc/resolv.conf -> ../run/systemd/resolve/stub-resolv.conf
ubuntu@VM-0-5-ubuntu:~$ tail /etc/resolv.conf
#
# Third party programs must not access this file directly, but only through the
# symlink at /etc/resolv.conf. To manage man:resolv.conf(5) in a different way,
# replace this symlink by a static file or a different symlink.
#
# See man:systemd-resolved.service(8) for details about the supported modes of
# operation for /etc/resolv.conf.

nameserver 127.0.0.53
options edns0
ubuntu@VM-0-5-ubuntu:~$
```

执行 `systemd-resolve --status` 可以看出来这两个网卡没有配置DNS 服务器

```
Link 3 (eth1)
      Current Scopes: none
       LLMNR setting: yes
MulticastDNS setting: no
      DNSSEC setting: no
    DNSSEC supported: no

Link 2 (eth0)
      Current Scopes: none
       LLMNR setting: yes
MulticastDNS setting: no
      DNSSEC setting: no
    DNSSEC supported: no
```

可能有的人认为改一下 /etc/resolv.conf 或者说指向一个自己的配置文件就完事了。但是这个stub文件的第一行也说了，这玩意是 systemd-resolved 来维护的，任何手动修改都会在重启之后丢失。本着“发行版的问题就要按照发行版的方式来解决”的思路，这个地方需要用一个 Ubuntu Way 来解决。根据 man page

> The DNS servers contacted are determined from the global settings in /etc/systemd/resolved.conf, the per-link static settings in
> /etc/systemd/network/*.network files, the per-link dynamic settings received over DHCP and any DNS server information made available by other
> system services. See resolved.conf(5) and systemd.network(5) for details about systemd's own configuration files for DNS servers.

systemd-resolved 会使用`systemd.network`的配置文件，因此需要修改 `/{run,etc/lib}/systemd/network` 下的对应网卡的配置文件的DNS配置。如果有netplan，因为netplan也是用的`systemd.network`，直接修改netplan的配置YAML就可以了。该启用DHCP的就启用DHCP，该hardcode DNS就 hardcode DNS。
