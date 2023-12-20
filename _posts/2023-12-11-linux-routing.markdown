---
toc: true
layout: "post"
catalog: true
title: "从多网卡看linux routing"
date:   2023-12-10 21:40:38 +0800
header-img: "img/hn-wuzhizhou.jpg"
categories:
  - blog
tags:
  - network
  - iproute2
  - RPDB
  - routing
  - ubuntu
  - bridge
  - systemd-networkd
  - netplan 
---


# 从多网卡看linux routing

给主机绑定多个物理网卡之后，需要正确配置路由表和RPDB才能让主机通过多网卡发包。在配置之前需要了解linux系统在将一个packet发往网卡的时候是如何选择路由的。

## Linux route selection

所谓路由route，就是一条让系统知道应该将packet发到哪个网卡的记录。[路由的选择过程](http://linux-ip.net/html/routing-selection.html)涉及三个数据结构：

1. 路由缓存 (route cache)；
2. RPDB(routing policy database) 存储 `src, dst, tos, fwmark, iif` 和路由表的关系。有的资料把这个叫做路由策略；
3. 路由表(routing table)。

首先，系统会以`(dst, src, tos, fwmark, iif)`为key，尝试从路由缓存中找一条路由。路由缓存可以通过输入`ip route show cache`查看。>=3.6的linux内核不再支持IPv4 route cache，输入该命令查看ipv4路由缓存将永远返回空，[有的参考资料比较老](https://serverfault.com/q/1091128/599288)，并没有记录这一点。如果路由缓存里有对应的路由，就直接使用这条路由并结束查找；

否则，系统遍历 RPDB ，检查每一项是否跟当前key匹配，如果可以匹配，就会进一步遍历该项对应的路由表。在路由表中以`(dst, tops, scope, oif)`为key查找是否有对应的路由，有的话就直接使用这条路由并结束查找；否则，遍历 RPDB 的下一项，继续执行这个操作，这个过程可以用以下python伪代码来表示：

```python
if packet.routeCacheLookupKey in routeCache :
    route = routeCache[ packet.routeCacheLookupKey ]
else
    for rule in rpdb :
        if packet.rpdbLookupKey in rule :
            routeTable = rule[ lookupTable ]
            if packet.routeLookupKey in routeTable :
                route = route_table[ packet.routeLookup_key ]
```
## 多网卡

有一点值得注意：在路由表中，源地址src并不参与到路由决策；src只在路由缓存和RPDB中起作用。总的来说，为了实现多网卡分别都能发包，我们需要正确配置RPDB和路由表，让系统首先通过src在RPDB找到路由表，再根据dst在路由表中找到路由。

### 使用 iproute2 配置路由

多网卡需要对每个网卡单独配置IPv4、路由表和RPDB，我们可以用 iproute2 工具包来操作：

```bash

# 1. 将网卡的DHCP关掉。编辑 `/etc/sysconfig/network-scripts/` 目录下网卡对应的配置文件，将BOOTPROTO 的值改成 static
# 2. 手动配置网卡的IP、子网掩码和网关。这是因为后面的手动配置需要hard-code使用到这信息
ip address add 172.16.0.5/20 dev eth0 broadcast 172.16.15.255

# 3. 为网卡创建单独的路由表。编辑 `/etc/iproute2/rt_tables`，每个路由表由一个整数ID和字符串组成，占一行，
# 整数ID用来标识出一个路由表，在操作 iproute2 的过程中需要用到这个ID，e.g.，新的路由表为 10
echo "10 t1" >> /etc/iproute2/rt_tables

# 4. 往路由表(table 10)中添加发往当前网卡(eth0的)、经过网关(172.16.0.1)的默认路由；
ip route add default via 172.16.0.1 dev eth0 metric 100 table 10

# 5. 往RPDB中添加一个针对特定源地址(172.16.0.5)、选择路由表(table 10)的路由策略。
ip rule add from 172.16.0.5 table 10
```

### More on DNS

完了之后，系统就可以知道哪个IP packet应该发到哪个网卡了。但是都2024年了、程序总不能老是使用IP地址吧，DNS啥的得安排上，不过iproute2对于DNS就无能为力了。



可以通过指定网卡执行 cURL 看下是否都能通网(`ping -I`也提供类似的功能)：

```bash
curl qq.com --interface eth0
curl qq.com --interface eth1
```

### 使用 netplan 配置网络

iproute2 是集成到linux内核的，所有linux发行版都会有这个工具包。相较于使用命令，我们也可以使用netplan通过配置文件对网络进行配置，使用这种方式主机在重启之后不会丢失配置。更能适应配置下发、云主机初始化和容器部署等场景下。个人觉得这应该算是linux发行版所带来的便利。

netplan会使用`/{lib,etc,run}/netplan/` 目录下的yaml文件。yaml的文件名不能太随意。程序将这里头的文件按照文件名字典序进行配置，在yaml 中同样的key，文件名字典序靠后的文件会**覆盖**字典序靠前的文件。往yaml文件写入以下内容。

```yaml
network:
    version: 2
    ethernets:
        eth0:
            match:
                macaddress: ff:ee:dd::cc::bb::aa
            set-name: eth0
            gateway4: 172.16.0.1
            dhcp4: false
            nameservers:
                addresses: [119.29.29.29]
            addresses: [172.16.0.5/20]
            routes:
                - to: 0.0.0.0/0
                  via: 172.16.0.1
                  table: 10
                  metric: 100
            routing-policy:
                - from: 172.16.0.5
                  table: 10
        eth1:
            match:
                macaddress: aa:bb:cc:dd:ee:ff
            set-name: eth1
            gateway4: 172.16.0.1
            dhcp4: false
            nameservers:
                addresses: [119.29.29.29]
            addresses: [172.16.0.7/20]
            routes:
                - to: 0.0.0.0/0
                  via: 172.16.0.1
                  table: 20
                  metric: 100
            routing-policy:
                - from: 172.16.0.7
                  table: 20
```

routes对应写入路由表的内容，routing-policy对应写入RPDB的内容。使用者需要在这两部分分别用table字段标识出来关联哪一个routing table。整数ID对应的路由表如果不存在将会被创建，使用者无需手动编辑 `/etc/iproute2/rt_tables`。其他需要注意的内容需要参考`man netplan`。

写好配置文件之后执行 `sudo netplan apply`，netplan会在运行时目录 `/run/systemd/network/`下为每个网卡生成 *.link 和 *.network 文件(`man -s 5 systemd.network`)，后台服务 systemd-networkd 将会读取这里的文件使配置生效(`man -s 8 systemd-networkd`)。systemd-networkd 是见于 Arch 和 Ubuntu 的组件，在CentOS上是没有的。总是有很多人不明就里地拿着 Ubuntu 的指引去操作 CentOS，比如配置网络，这就是发行版带来麻烦的证据之一。

P.S. 使用netplan配置unreachable的时候，在对应的route里需要加上 `via: 0.0.0.0` ，否则不生效，而且[netplan也不会报告出来](https://askubuntu.com/a/1082839/925210)。


## 桥接

将多个物理网卡桥接到一起作为一个网卡使用可以提升带宽(存疑)。相较于多网卡配置路由，配置桥接就简单多了，省去了折腾路由表和RPDB的步骤，而且两个物理网卡也不需要配置IP地址。

```bash
# 创建一个桥接设备
ip link add name brg type bridge
ip link set dev br0 up 

# 把物理网卡 eth1 down掉，然后加入到桥接
ip link set dev eth1 down
ip link set dev eth1 master br0
ip link set dev eth1 up

# 把物理网卡 eth0 down掉，然后加入到桥接
ip link set dev eth0 down
ip link set dev eth0 master br0
ip link set dev eth0 up

# 桥接设备使用dhcp获取IPv4地址
dhclient br0
```

netplan的配置就更简单了

```yaml
network:
    version: 2
    ethernets:
        eth0:
            dhcp4: false
        eth1:
            dhcp4: false
    bridges:
        br0:
            dhcp4: true
            interfaces:
                - eth0
                - eth1
```

完了之后可以通过ifconfig的结果看到只有桥接设备 br0 有IPv4地址，两个物理网卡 eth0和eth1 没有IPv4地址，并且通过 `curl qq.com --interface br0` 可以验证配置成功。顺便说一下，因为配置涉及到down掉网卡，如果是云上主机，会导致SSH登录连接被断开，所以在配置之前最好通过VNC登录而不是SSH登录。

值得一提的是，通过netplan创建的bridge，不能指望能被自动删除掉。需要手动先down再删掉bridge

```bash
sudo ip link set dev br0 down
sudo ip link delete br0 type bridge
```

### 提升带宽(存疑)

实验环境是腾讯云上的两个CVM，两个CVM放置在同一个子网中 172.16.0.0/16；一个CVM作为iperf3的服务端，另一个作为iperf3客户端，均绑定内网地址、使用TCP进行实验。桥接前单个网卡的实验结果如下：

```
[  4]   0.00-10.00  sec   511 MBytes   429 Mbits/sec    0             sender
[  4]   0.00-10.00  sec   511 MBytes   429 Mbits/sec                  receiver
```

桥接后的实验结果：
```
[  4]   0.00-10.00  sec   542 MBytes   454 Mbits/sec    0             sender
[  4]   0.00-10.00  sec   542 MBytes   454 Mbits/sec                  receiver
```

提升效果就这么点，我都怀疑到底有没有起作用，还是说这就是腾讯云内网带宽的上限？可以考虑走公网IP测试一下。

### 默认 DNS 失效

TODO:

<!--
桥接实验结束之后通过iproute2手动恢复多网卡。发现原先的 DNS 不管用了

```
ubuntu@VM-0-5-ubuntu:~/project$ curl qq.com
curl: (6) Could not resolve host: qq.com
```

众所周知DNS用的端口是53，所以用tcpdump[任意网卡(>=2.2内核)](https://serverfault.com/a/805008/599288)并过滤53端口，结果显示DNS查询默认情况下发往127.0.0.53:53，这是一个本地地址。

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
```

这个进程的名字是 systemd-resolved。
-->
<!-- ## VMWare 模拟 -->
<!-- 在 VMWare 的NAT模式中，宿主机是第一个IP，网关是第二个IP，虚拟机可以用剩下的除开broadcast以外的IP，e.g.，windows宿主机的IP是192.168.172.1，NAT网关的IP是192.168.172.2 .-->

## Reference

- 路由表 http://linux-ip.net/html/routing-tables.html
- RPDB http://linux-ip.net/html/routing-rpdb.html
- linux route selection http://linux-ip.net/html/routing-selection.html
