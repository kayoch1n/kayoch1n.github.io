---
classes: wide
layout: single
title:  "修复xxx.github.io解析到本地127.0.0.1问题"
date:   2020-10-02 16:42:38 +0800
categories: 
  - blog
tags:
  - dns
---

中秋回家没有网，用了另一个电信卡开热点给笔记本，结果chrome打开github page提示拒绝连接 ❌ 黑人问号？？？.jpg

# Contents

换用另一只移动卡开热点，结果还是拒绝连接。我第一反应竟然是github.io被墙了 😂 

眉头一皱发现事情并不简单。先康康DNS是否正常:

```bash
$ dig kayoch1n.github.io

; <<>> DiG 9.10.6 <<>> kayoch1n.github.io
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 46931
;; flags: qr aa rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;kayoch1n.github.io.		IN	A

;; ANSWER SECTION:
kayoch1n.github.io.	3600	IN	A	127.0.0.1

;; Query time: 67 msec
;; SERVER: 127.0.0.1#53(127.0.0.1)
;; WHEN: Fri Oct 02 16:35:58 CST 2020
;; MSG SIZE  rcvd: 70
```

`127.0.0.1`?你不对劲！在cvm上面试一下:

```bash
$ dig kayoch1n.github.io

; <<>> DiG 9.10.3-P4-Ubuntu <<>> kayoch1n.github.io
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 26990
;; flags: qr rd ra; QUERY: 1, ANSWER: 4, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 4096
;; QUESTION SECTION:
;kayoch1n.github.io.            IN      A

;; ANSWER SECTION:
kayoch1n.github.io.     1661    IN      A       185.199.111.153
kayoch1n.github.io.     1661    IN      A       185.199.109.153
kayoch1n.github.io.     1661    IN      A       185.199.108.153
kayoch1n.github.io.     1661    IN      A       185.199.110.153

;; Query time: 8 msec
;; SERVER: 183.60.83.19#53(183.60.83.19)
;; WHEN: Fri Oct 02 16:59:09 CST 2020
;; MSG SIZE  rcvd: 111
```

可能是运营商的锅；而且网上的[DNS检测](https://www.ping.cn/dns/kayoch1n.github.io)更加坐实了这种判断: 

![ISP DNS]({{ site.url }}/assets/2020-10-02-isp-dns-test.png)

解决方法也简单，不使用运营商的默认DNS就OK，可以在当前网络连接中使用其他公共的DNS，比如腾讯云 119.29.29.29 。如果是macOS可以参考[官方指引](https://support.apple.com/zh-cn/guide/mac-help/mh14127/mac)