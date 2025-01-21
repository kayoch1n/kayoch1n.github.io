---
toc: true
layout: "post"
catalog: true
title: "用容器模拟组建网络"
subtitle: "一键自动化"
date: 2024-12-27 09:00:38 +0800 
mermaid: true
header-img: "img/gz-SCNBC-bald-cypress.jpg"
categories:
  - blog
tags:
  - iptables
  - docker
  - docker-compose
  - tc
  - iproute2
---


用 docker-compose 可以组建一些简单的网络，测试一些简单的功能。这个方法不需要准备多个真机和路由器，只要在单个运行Linux的机器上就能实现；而且得益于Linux namespace的隔离特性，变更路由或者修改防火墙等网络设置只会影响到单一容器而不影响宿主机，所有对于路由表、防火墙或者队列的修改都会在 `docker-compose down` 之后被撤销，加上配合 tc 可以实现流量控制、模拟loss和延迟等，因此在执行一些自动化任务的时候有优势。

当然缺点也很明显，这个方法只适用于Linux，而且容器跟真机可能还是有差别的。

## 组网

只要容器的 `networks` 标签值包含相同的网络的名称的字符串，docker-compose就会把对应的容器放在同一个网络，根据这一点就可以在 docker-compose.yml 里编排网络的拓扑结构了：

```mermaid
flowchart LR
    subgraph network_ayupyon["Network ayupyon"]
    direction TB
    host_ayumu["Host ayumu"]
    end

    router["Router"]

    host_ayumu <--> router 
    router <--> host_setsuna

    subgraph network_chase["Network chase"]
    direction TB
    host_setsuna["Host setsuna"]
    end
```

这个例子包含两个通过路由器连接的网络，两个网络各自包含一个容器，对应如下的 yaml 配置。

```yaml
services:
  ayumu:
    networks:
    - ayupyon
    cap_add:
      - NET_ADMIN
    depends_on:
    - router
    # ...
  setsuna:
    networks:
    - chase
    cap_add:
      - NET_ADMIN
    depends_on:
    - router
    # ...
  router:
    networks:
    - ayupyon
    - chase
    cap_add:
      - NET_ADMIN
    # ...
networks:
  ayupyon: # ...
  chase: # ...
```

> 完整配置见 [github](https://github.com/kayoch1n/netwlabs/blob/master/lab-tcp-cctrl/docker-compose.yml)

1. 两个网络在顶级标签 `networks` 里声明；
2. 两个容器的 `networks` 分别包含对应的网络的名字；
3. router 的 `networks` 同时包含了两个网络，符合人设；
4. 两个容器分别通过 `depends_on` 标签声明启动时的依赖关系。如果容器启动的时候需要执行一些命令比如解析router IP，就可以用这个标签避免因为启动顺序没协调好而造成的报错以至于启动失败的问题；

### 分配 NET_ADMIN capability

修改路由和防火墙需要 root 特权，容器在默认情况下无法使用。

传统上 Unix 将进程分成特权进程(euid=0, root/superuser)和非特权进程，通过 euid 和 egid 等方式检查权限；而 Linux 则是将 root 的特权划分成更小的单元，称为 capability ，可以为进程单独设置一个或多个 capabilities。为了修改路由和防火墙，需要在 `docker-compose.yml` 中加入名为 `NET_ADMIN` 的 capabilities。

### （可选）映射 TUN 设备

如果容器需要读写 TUN 设备，需要[将 `/dev/net/tun` 设备映射到容器内](https://stackoverflow.com/a/68071527/8706476)，不然容器打开 TUN 设备会失败

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

### （可选）IP配置

docker-compose 支持[对网络指定网段或者容器分配IP](https://docs.docker.com/reference/compose-file/services/#ipv4_address-ipv6_address)。这个不是必须的，除非有需求

```yaml
services:
  ayumu:
    networks:
      ayupyon:
        ipv4_address: 172.16.238.10
    # ...
networks:
  front-tier:
    ayupyon:
      driver: default
      config:
        - subnet: "172.16.238.0/24"
# ...
```

### 防止容器退出

容器的本质是被namespace隔离的进程，换言之必须要有一个可以执行的“入口”，也就是 entrypoint。我模拟组网的目的有时可能只是验证一些拓朴结构里的猜想，比如简单ping一下测试通不通；简单起见，网络里的节点很多时候是“空转”的，换言之没有一个固定的执行的进程。

因此为了不让空转的容器退出，entrypoint 为 bash 的容器可以在 yml 里指定 `tty: true`。

或者，也可以在 command 参数中使用 `tail -f xxx`，其作用是持续检测文件 xxx 是否有追加数据并且输出，因此不会退出。这个方法适用于需要提前执行一段命令或者本来就有入口的容器。

```yaml
services:
  ayumu:
    entrypoint: bash
    command: ["-c", "python3 start.py && tail -f /dev/null"]
# ...
```

另外，对于有入口的容器，可能还要增加一段入口挂掉之后重新启动的逻辑。比如 `iperf3` 的 server 端在 client 测试完成之后就会自动退出，为了防止容器挂掉，得用 bash 的 while 重新拉起来

```yaml
services:
  ayumu:
    entrypoint: bash
    command: >
      -c "while true ; do iperf3 -s -1 ; done"
# ...
```

### 设置容器作为路由器

Linux 内建了 IP 转发的功能。为了实现转发 IP packet，宿主机需要启用对应的内核参数：

```bash
sysctl -w net.ipv4.ip_forward=1
```

docker 允许[单独为容器指定部分内核参数](https://docs.docker.com/compose/compose-file/compose-file-v3/#sysctls)，不过也不完全对。本地（ubuntu 18.04，docker 24）试了一下发现，在宿主机 IPv4 转发关闭的情况下，容器尽管使用了 `sysctls: [net.ipv4.ip_forward=1]` 也还是不能转发IPv4。这跟当前登录用户是否为 root 无关，哪怕容器本身是用 sudo 拉起来的也一样。不过，反过来就不一样了，在宿主机打开该开关的情况下，容器使用了 `net.ipv4.ip_forward=0` 雀食能禁止 IPv4 转发，猜测 docker 只能关闭内核参数，而不能主动打开被宿主机关闭的内核参数。

这还没完，这里会有个小问题。由于两个容器分别和 router 的两个网卡分别处在同一个子网，当这个名为 router 的容器发现[收包的源地址跟下一跳是同一个网段](https://serverfault.com/a/402047)的时候，这个不成熟的router就会发送一个 ICMP redirect。用 sidecar tcpdump 可以看到

```
19:57:15.188446 IP 192.168.176.3.55040 > 113.108.81.189.443: Flags [S], seq 596096153, win 64240, options [mss 1460,sackOK,TS val 4125452867 ecr 0,nop,wscale 7], length 0
19:57:15.188507 IP 192.168.176.2 > 192.168.176.3: ICMP redirect 113.108.81.189 to host 192.168.176.1, length 68
19:57:17.204440 IP 192.168.176.3.55040 > 113.108.81.189.443: Flags [S], seq 596096153, win 64240, options [mss 1460,sackOK,TS val 4125454883 ecr 0,nop,wscale 7], length 0
19:57:17.204506 IP 192.168.176.2 > 192.168.176.3: ICMP redirect 113.108.81.189 to host 192.168.176.1, length 68
```

其实没有回包。为了解决这个问题，这个不成熟的 router 的防火墙需要使用 [masquerade 规则](https://stackoverflow.com/a/69055795)

```yaml
services:
  ayumu:
    image: # ...
    entrypoint: bash
    command: > 
      -c "echo 'add iptables rule...' &&
      iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE &&
      iptables -A FORWARD -i eth0 -j ACCEPT &&
      iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE &&
      iptables -A FORWARD -i eth1 -j ACCEPT && 
      tail -f /dev/null"
# ...
```

### 设置DNS服务器

到这里这个名为 router 的容器已经具备转发包的能力了，不过DNS还是没有的。如果要具备DNS的能力，router需要安装类似 dnsmasq 的东西并且设置为 entrypoint，而且各个容器还得改DNS设置。不过这里我没有需要因此就没整了。

## 设置默认路由

一般情况下，容器的默认路由是指向docker的网关。为了让容器的traffic能够经过 router，需要分别在容器启动之前修改其默认路由

```yaml
services:
  ayumu:
    networks:
      - ayupyon
    depends_on:
      - router
    entrypoint: bash
    command: >
      -c "ip route change default via `dig router +short` &&
      tail -f /dev/null"
```


## 设置流量控制

容器毕竟不是真机，不像真实网络会出现丢包延迟，容器之间发包要多快有多快。这个时候 tc 可以派上用场了。tc 是用于操作Linux内核流量管控的工具。包被发往网卡之前会先进入内核的队列，可以借由tc对流量进行分类(class)、给队列(qdisc)设置属性等方式模拟丢包或延迟。tc 内部为每个网卡维护一个树状结构，其节点有两种：

1. qdisc: 队列，这是真正存储包的地方。叶子节点只能是qdisc。创建的时候需要指定 handle，父节点不能是 qdisc ；
    - classful qdisc: 子节点可以为多个 class，比如 htb。
    - classless qdisc: 无子节点。比如 netem，这个可以用来实现弱网下的延迟或者概率丢包。
2. class: 流量的队列。这是树结构的中间节点；
    - 子节点可以为多个 class，或者有且只有一个 qdisc；
    - 创建的时候需要指定 classid。classid的major部分必须是qdisc的handle，而不是结构上的父节点。

一个_可能_的tc结构如下

```mermaid
flowchart TB
    root[
        root
        classful qdisc
        handle 1:
    ] 
    root --> class_1_2[
        class 1:2
        htb rate 2Mbit
    ]
    root --> class_1_3[
        class 1:3
        htb rate 3Mbit
    ]
    root --> class_1_4[
        class 1:4
        htb rate 4Mbit
    ]

    class_1_2 --> qdisc_bfifo[
        bfifo 0.1MB
        classless qdisc
    ]

    class_1_3 --> class_1_5["class 1:5"]
    class_1_3 --> class_1_6["class 1:6"]
    class_1_5 --> fifo

    class_1_4 --> qdisc_htb[
        htb
        classful qdisc
        handle 2:
    ]

    qdisc_htb --> class_2_5["class 2:5"]
```

> tc 的树状结构猜测。非本文的例子

除此之外还有名为 filter 的结构，当一个节点包含多个class的时候，可以用filter指定匹配某一class。

包在被发往网卡之前，实际上是先遍历 tc 的树结构然后挂到叶子节点，也就是qdisc队列中。包在遍历过程中被施加流量类对应的特性，然后才能等待被发往网卡。

本文例子中添加的tc规则来自[这篇文章](https://witestlab.poly.edu/blog/tcp-congestion-control-basics/)，一开始的目的是为了观察TCP CWND 和 sstresh 在不同拥塞算法下的变化过程。分别给 router 的两个网卡添加一样的流量控制

```yaml
services:
  router:
    cap_add:
      - NET_ADMIN
    networks:  # router 衔接上述两个容器的网络
      - chase
      - ayupyon
    entrypoint: bash
    command: > 
      -c "echo 'add iptables rule...' &&
      iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE &&
      iptables -A FORWARD -i eth0 -j ACCEPT &&
      iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE &&
      iptables -A FORWARD -i eth1 -j ACCEPT && 
      echo 'add traffic control...' &&
      tc qdisc add dev eth0 root handle 1: htb default 114 &&
      tc class add dev eth0 parent 1: classid 1:114 htb rate 1Mbit &&
      tc qdisc add dev eth0 parent 1:114 handle 514: bfifo limit 0.1MB &&
      tc qdisc add dev eth1 root handle 1: htb default 114 &&
      tc class add dev eth1 parent 1: classid 1:114 htb rate 1Mbit &&
      tc qdisc add dev eth1 parent 1:114 handle 514: bfifo limit 0.1MB &&
      echo 'done' &&
      tail -f /dev/null"
# ...
```

## 容器的 Sidecar

sidecar 是 k8s 里的概念，允许一个容器去访问另一个容器里的内容，一般的用法是让sidecar容器输出另一个容器里的微服务的日志。docker-compose里面也有[类似的功能](https://ilhicas.com/2023/01/26/How-to-run-a-sidecar-in-docker-compose.html)，做法是在作为 sidecar 的容器配置中指定 `network_mode: "services:xxxx"`

```yaml
services:
  ayumu:
    networks:
    - ayupyon
    # ...
  shioriko:
    image: # ...
    container_name: shioriko
    entrypoint: bash
    command: ["-c", "while sleep 0.01 ; do ss --no-header -eint4 ; done"]
    network_mode: "service:ayumu"  # sidecar 挂到其中一个容器上
# ...
```

以此法可实现 tcpdump 抓包、ss 获取 socket 状态等功能。但其实二者只是共享网络 namespace，文件系统则是独立的，sidecar 不能访问另一个容器的文件系统，从下面这个例子中可以看得出来：

```
ubuntu@VM-16-15-ubuntu:~/data$ docker exec ayumu bash -c 'echo 114514 > /data/1919810'
ubuntu@VM-16-15-ubuntu:~/data$ docker exec ayumu cat /data/1919810
114514
ubuntu@VM-16-15-ubuntu:~/data$ docker exec shioriko cat /data/1919810
cat: /data/1919810: No such file or directory
ubuntu@VM-16-15-ubuntu:~/data$
```

## 一键自动化

借助 docker-compose 可以实现一键启动、一键关闭指定拓扑结构的网络，这对于一些自动化任务来说是非常方便的。下面这个脚本使用了 docker-compose 进行 TCP 拥塞控制的相关实验 

```bash
# 启动网络拓扑
docker-compose up -d
ip=`docker exec setsuna dig setsuna +short`
# 执行 iperf3 打流
echo "iperf using reno"
docker exec ayumu iperf3 -c $ip -C reno -t 10
# 收集 sidecar 的日志
echo "collect tcp statistics"
docker-compose logs -t --no-log-prefix shioriko > output/ss-sender.txt
docker-compose down
```
