---
toc: true
layout: "post"
catalog: true
title:  "高等代数导论-蒙哥马利算法"
date:   2021-10-02 12:10:38 +0800
header-img: "img/sz-transmission-tower.jpg"
mathjax: true
categories: 
  - blog
tags:
  - cryptography
  - number theory
---

# 正文

计算机中的模运算 `a % m`，在数论里面可以看作求 $a$ 的**模 $m$ 最小非负剩余**，用手工运算实现的话就是用长除法(long division)得到余数。长除法的算法描述步骤如下，

0. 初始条件 $q_0=0$，$i=0$
1. 用 $q_i$ 乘以 $m$ 得到 $A_{i}=q_im$
2. $q_i=q_i+1$
3. 比较 $A_{i}$ 和被除数$a_i$。如果 $A_{i}\le a$ 就回到1；否则可确定 $q_i-1$ 是商 $q$ 的第 $i$ 个数位
4. $a=a-(q_i-1)m$
5. $i=i+1$，回到1，直到 $a=0$ 为止

可见长除法包含一个试错的过程。手工运算可以通过“盲猜”计算商的数位，但是对于计算机来说只有“遍历”这一方法。不过，对于特定场景下、固定模数 $m$ 和给定进制 $r$ ($m\lt r$)的大数模运算，除了长除法以外还有其他方法可以有效地进行模运算 $a\pmod m$，即蒙哥马利算法。

## 前提

蒙哥马利算法需要使用到一些常量值。第一个是 $r$。对于模数 $m$，先设置一个 $r$ 满足 $m\lt r$ 且 $\gcd(m,r)=1$。$r$ 是为了能够快速计算 $x\pmod r$ 而设置的。在手工运算中，$r$ 可以设置为 1000，比如 $25,252\equiv252\pmod {1000}$；在计算机的实现中，base 可以是 $2$ 的、次数很高的幂，这样的话 $x\pmod {2^n}$ 就相当于取 least significant $n$ bits，也就是和一个mask进行“与”运算。

第二个是 $r'$ 和 $m'$。因为$m$和$r$互质，根据贝祖等式(Bezout's Identity)，存在两个整数 $r'$ 和 $m'$ 使得

$$
r'r=1+m'm
$$

而且$r'$ 和 $m'$的值可以使用扩展欧几里得算法(Extended Euclid's Algorithm)计算出。

第三个是 $w=r^2\pmod m$ 且 $0\le w\lt m$，即 $w$ 是 $r^2$ 模 $m$ 的最小非负剩余。以上三个数值 $r'$，$m'$ 和 $w$ 会被应用到算法中。

## 算法

算法假设需要进行模运算的值 $0\le a\lt mr$。

### 引入$r'$
这个步骤需要计算以下两个值 $s$ 和 $z$

$$
\begin{aligned}
s&\equiv am'\pmod r\\
z&=\frac{a+sm}{r}
\end{aligned}
$$

首先，基于上述前提，$s$ 是易于计算的，因为 $x\pmod r$是一个快速运算。

其次，算法断言 $z$ 必然是一个整数。这是因为

$$s\equiv am'\pmod r$$

$$sm\equiv am'm\pmod {rm}$$

$$a+sm\equiv a+am'm\equiv a(1+m'm)\equiv ar'r\pmod {rm}$$


$a+sm\equiv ar'r\pmod {rm}$ 意味着 $r$ 整除 $a+sm$，所以 $z=\frac{a+sm}{r}$ 是一个整数，即

$$
z=\frac{a+sm}{r}\equiv ar'\pmod m
$$

注意 $z$ 和 $\frac{a+sm}{r}$ 之间是等号，也就是说这两个变量的数值是一样的，和 $ar'$ 模 $m$ 同余。

再者，考察 $z$ 的范围。因为 $s\lt r$，$sm\lt rm$；加上 $a\lt mr$，所以

$$
a+sm\lt2mr\implies 0\le z=\frac{a+sm}{r}\lt 2m
$$

令

$$
c=\begin{cases}
z&(z\lt m)\\
z-m&(m\le z\lt 2m)
\end{cases}
$$

到这里为止，算法得到了一个值 $c$ 满足 $0\le c\lt m$，而这个数值和 $ar'$ 模 $m$ 同余。和 $a\pmod m$相比，$c$ 的值多乘了一个 $r'$，下一步需要消除掉这个多余的 $r'$。


### 消除$r'$
用 $w\equiv r^2\pmod m$ 乘以 $c$ 得到 $wc$。因为 $w,c\in [0, m)$ 且 $m\lt r$，所以 $0\le wc\lt m^2\lt mr$，满足前面步骤的要求 $[0,mr)$。对积 $wc$ 重复前面的步骤：

$$
\begin{aligned}
s'&\equiv wcm'\pmod r\\
z'&=\frac{wc+s'm}{r}
\end{aligned}
$$

在这里，$c$ 乘 $w$ 相当于引入了 $r^2\pmod m$；由于$c$ 本身包含了一个 $r'\pmod m$ ，积 $wc$ 多了一个 $r$。然后再次重复前面的步骤、再次引入 $r'$ 就能够消除 $r$

$$
z'=wcr'\equiv r^2cr'\equiv cr\equiv ar'r\equiv a\pmod m
$$

这表示 $z'$ 和 $a$ 模 $m$ 同余。最后

$$
c'=\begin{cases}
z'&(z'\lt m)\\
z'-m&(m\le z'\lt 2m)
\end{cases}
$$

$c'$ 就是 $a$ 模 $m$ 的最小非负剩余。Q.E.D

<!-- TODO -->
<!-- ## 总结 -->
