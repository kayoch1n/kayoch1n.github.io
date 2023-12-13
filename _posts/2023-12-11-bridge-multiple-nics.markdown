---
toc: true
layout: "post"
catalog: true
title: "软件桥接多网卡"
date:   2023-12-10 21:40:38 +0800
header-img: "img/hn-wuzhizhou.jpg"
categories:
  - blog
tags:
  - network
---


# 软件桥接多网卡

## 配置多网卡

### 使用 iproute2 工具包配置路由

当物理网卡就位之后，下一步就要配置路由。在配置之前需要了解linux系统在将一个packet发往网卡的时候是如何选择路由的。

#### Linux route selection

这个过程涉及三个数据结构：

1. 路由缓存 (route cache)
2. RPDB(routing policy database) 存储 `src, dst, tos, fwmark, iif` 和 route table的关系。有的资料把这个叫做路由策略
3. 路由表

首先，系统会以`(dst, src, tos, fwmark, iif)`为key，尝试从路由缓存中找一条路由。路由缓存可以通过输入`ip route show cache`查看。>=3.6的linux内核不再支持IPv4 route cache，输入该命令永远返回空，[有的参考资料比较老](https://serverfault.com/q/1091128/599288)，并没有记录这一点。如果有，就直接使用这条路由并结束查找，否则继续查找；

然后，系统遍历 RPDB 里的每一项是否跟当前key匹配，如果可以匹配，就会进一步遍历该项对应的路由表。如果路由表中有满足条件的、就直接使用这条路由并结束查找，否则继续遍历 RPDB 的下一项。


### 使用 iproute2 配置路由

总的来说，配置多网卡需要做三个事情，我们可以用 iproute2 工具包来操作：

1. 为网卡创建单独的路由表。这个需要用文本编辑器编辑 `/etc/iproute2/rt_tables`；
2. 使用`ip route`在每个路由表中增加路由
    - e.g., `ip route add default via 172.16.0.1 dev eth0 metric 100 table 10`，
    - 这表示添加一个往table 10中添加发往eth0、经过网关172.16.0.1的默认路由；
3. 使用`ip rule`在RPDB中为每个路由表增加routing policy，
    - e.g.，`ip rulee add from 172.16.0.5 table 10`，
    - 这表示添加一个当源地址是172.16.0.5时选择table 10的路由策略。

### 使用 netplan 配置路由

iproute2 是集成到linux内核的，所有linux发行版都会有这个工具包。相较于使用命令，使用固定的配置文件更能适应配置下发、云主机初始化和容器部署等场景下的网络控制策略。个人觉得这应该算是linux发行版所带来的便利。netplan就是使用yaml文件配置网络的工具。

在 /etc/netplan 下面新建一个yaml文件。文件名不能太随意。程序将这里头的文件按照字典序进行配置，在yaml 中同样的key，字典序靠后的文件会覆盖前面的文件。往yaml文件写入以下内容。

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

routes对应写入路由表的内容，routing-policy对应写入RPDB的内容。使用者需要在这两部分分别用table字段标识出来关联哪一个routing table。如果整数对应的路由表不存在、将创建对应的路由表，无需手动编辑 `/etc/iproute2/rt_tables`。其他需要注意的内容需要参考`man netplan`。

写好配置文件之后执行 `sudo netplan apply` 使配置生效。完了之后可以通过指定网卡执行 cURL 看下是否都能通网(`ping -I`也提供类似的功能)：

```bash
curl qq.com --interface eth0
curl qq.com --interface eth1
```

P.S. 使用netplan配置unreachable的时候，在对应的route里需要加上 `via: 0.0.0.0` ，否则不生效，而且[netplan也不会报告出来](https://askubuntu.com/a/1082839/925210)。

## 配置桥接

TODO:

## 测试

TODO:


## VMWare 模拟

TODO:

## Reference

- 路由表 http://linux-ip.net/html/routing-tables.html
- RPDB http://linux-ip.net/html/routing-rpdb.html
