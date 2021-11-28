---
toc: true
layout: "post"
catalog: true
title:  "高等代数导论 - 欧拉函数"
date:   2021-11-27 11:51:38 +0800
header-img: "img/hn-wuzhizhou.jpg"
mathjax: true
categories: 
  - blog
tags:
  - cryptography
  - number theory
---

# 欧拉函数(Euler's totient function)

## 定义

定义欧拉函数 $\varphi(n)$ 是**小于 $n$** 且 **和 $n$ 互质** 的正整数的集合的计数，即

$$\varphi(n)=\mid S\mid \text{ , }S=\big\{x\mid x\in\mathbb{Z}^{+}\text{, } x\le n\text{ and }\gcd(x,n)=1\big\}$$

## 性质

$$
\varphi(n)=\begin{cases}
1&(n=1)\\
p-1&(n=p\text{ and }p\text{ is prime})\\
p^{t}-p^{t-1}&(n=p^t\text{ and }p\text{ is prime})\\
\varphi(a)\varphi(b)&(n=ab\text{ and }\gcd(a,b)=1)
\end{cases}
$$

举个栗子，$200=2^3\cdot5^2$，那么 $\varphi(200)=\varphi(2^3)\varphi(5^2)=(2^3-2^2)(5^2-5)=4\times20=80$，这表示在 $1\ge n\ge 200\text{,} n\in\mathbb{Z}$ 之间有80个整数和 $200$ 互质。

## 证明

前面两条性质 $n=1$ 或者 $n=p$ 是 trivial case。对于另外两种情况，以下按照[wiki的思路](https://zh.wikipedia.org/wiki/%E6%AC%A7%E6%8B%89%E5%87%BD%E6%95%B0)给出 $\varphi(n)$ 的简要证明。

### 质数幂
对于 $n=p^t$ 的情况可以考虑从那些与 $n$ 不互质的正整数入手。因为 $p$ 是质数，假如 $a$ 和 $n=p^s$不互质，也就是说两者有 **大于 $1$** 的公因数，那么这个公因数必然也是 $p$ 的幂，也就是说 $a$ 能够被 $p$ 的幂整除。更进一步地，$a$ 和 $p^s$ 有公因数，等价于 $p$ 整除 $a$。考虑被 $p$ 整除的整数 $a$ 的集合

$$
\begin{aligned}
S&=\big\{p, 2p,\dots, (p^{t-1}-1)p, p^{t-1}p\big\}\\
&=\big\{x\mid x=sp\text{ and }1\le s\le p^{t-1}\big\}
\end{aligned}
$$

$S$ 的大小是 $p^{t-1}$，所以不大于 $n=p^s$ 且被 $p$ 整除的整数 $a$ 有 $p^{t-1}$ 个，不能被 $p$ 整除的整数有 $p^t-p^{t-1}$ 个，因此 $\varphi(n)=p^t-p^{t-1}$

### 中国剩余定理

在证明积性函数性质之前，先来看一个定理：

给定 $n$ 个整数 $m_1, m_2,\cdots, m_n$，如果整数之间两两互质，即 $\gcd(m_i,m_j)=1\text{, }1\le i\lt j\le n$，那么对于以下方程组

$$
\begin{cases}
x\equiv a_1&\pmod {m_1}\\
x\equiv a_2&\pmod {m_2}\\
&\cdots\\
x\equiv a_n&\pmod {m_n}\\
\end{cases}\tag{1}
$$

存在通解，并且

$$
x\equiv \sum_{i=1}^{n} a_iM_i^{-1}M_i\pmod {\prod_{i=1}^{n}{m_i}}\tag{2}
$$

是该方程组的通解。用等号来表达就是

$$
x=k\prod_{i=1}^{n}{m_i}+\sum_{i=1}^{n} a_iM_i^{-1}M_i\text{, }k\in\mathbb{Z}\tag{3}
$$

其中，$M_i$ 为除 $m_i$ 以外所有模的乘积的同余（其实取等号也不是不行），即：

$$
M_i\equiv\prod_{j=0}^{j\ne i}m_j\pmod {m_i}\tag{4}
$$

而且 $M_i^{-1}$ 是 $M_{i}$ 的模 $m_i$ 乘法逆元，即：

$$
M_i^{-1}M_i\equiv1\pmod {m_i}\tag{5}
$$

两两互质是必要条件，否则至少一个 $m_i$ 的乘法逆元 $M_i^{-1}$ 不存在。这是因为假设存在两个整数 $\gcd(m_s,m_t)=d\gt1$，那么 $m_t$ 整除 $M_s$，$\gcd(m_s, M_s)\ge d \gt1$ ，不能满足乘法逆元的条件。

#### 充分性

结合 $(4)$ 式，对于任意 $1\le j\ne i\le n$ 都有 $M_j\equiv m_1\cdots m_{j-1}m_{j+1}\cdots m_n\equiv 0\pmod {m_i}$，因此

$$
\begin{cases}
aM_j^{-1}M_j&\equiv0&(j\ne i)\\
aM_i^{-1}M_i&\equiv a_i
\end{cases}\pmod {m_i}\tag{6}
$$

加上 $m_1m_2\cdots m_n\equiv0\pmod {m_i}$，对 $(3)$ 式模 $m_i$ 同余之后得到 

$$
\begin{aligned}
x&\equiv k\cdot0+\sum a_iM_i^{-1}M_i\\
&\equiv a_1M_1^{-1}M_1+\cdots+a_iM_i^{-1}M_i+\cdots+a_nM_n^{-1}M_n\\
&\equiv 0+\cdots+a_i+\cdots+0\\
&\equiv a_i\pmod {m_i}
\end{aligned}
$$

所以 $(3)$ 式是同余方程组的解，充分性得证。

#### 必要性

假设 $x_1$，$x_2$是方程组的两个解且 $x_1\ne x_2$，对于任意 $m_i$，都有

$$
x_1\equiv x_2\equiv a_i\pmod {m_i}\implies m_i\mid x_1-x_2
$$

由 $\gcd(m_i,m_j)=1$ 可以进一步得到 $m_im_j\mid x_1-x_2$。这个可以用[贝祖定理](https://en.wikipedia.org/wiki/B%C3%A9zout%27s_identity)推导出来


$$
m_is+m_jt=1
$$

$$ 
m_i(x_1-x_2)s+m_j(x_1-x_2)t=x_1-x_2
$$

加上 $m_im_j\mid m_i(x_1-x_2)$ 且 $m_im_j\mid m_j(x_1-x_2)$，所以 $m_im_j\mid x_1-x_2$。

这表明任意两个 $m$ 的积都能整除两个解的差。更进一步地，因为 $m_i$ 之间两两互质，所以可以对 $m_1m_2\cdots m_i$ 和 $m_{i+1}$ 反复应用上面的办法进行归纳，最终可以推导出 $m_1m_2\cdots m_n\mid x_1-x_2$，$x_1-x_2=km_1m_2\cdots m_n\text{, } k\in\mathbb{Z}$，换言之 $x_1$和$x_2$ 之间相差了$m_1m_2\cdots m_n$ 的整数倍，$x_1=x_2+k\prod_{i=1}^{n}m_i$。从前面“充分性”的部分已经知道方程组的一个解 $x_1=\sum_{i=1}^{n} a_iM_i^{-1}M_i$，因此方程组的通解是

$$
x=k\prod_{i=1}^{n}{m_i}+\sum_{i=1}^{n} a_iM_i^{-1}M_i\text{, }k\in\mathbb{Z}
$$

### 积性函数
利用中国剩余定理可知以下方程组

$$
\begin{cases}
x\equiv s&\pmod a\\
x\equiv t&\pmod b 
\end{cases}
$$

的解是

$$
\begin{aligned}
x&=kab+sb^{-1}b+ta^{-1}a\\
a^{-1}a&\equiv1\pmod b\\
b^{-1}b&\equiv1\pmod a\\
\end{aligned}
$$

$k\in\mathbb{Z}$。而且在区间 $[1,ab]$ 之间**有且只有一个**解

$$
x\equiv sb^{-1}b+ta^{-1}a\pmod {ab}
$$

#### 推论1

从上面结果中可以得到一个推论：假如 $a$ 和 $s$ 互质且 $b$ 和 $t$ 互质，那么 $x$ 必然和 $ab$ 互质。用反证法，先假设 $d=(x,ab)\gt1$。由算术基本定理可知存在一个质数 $p\mid d$，而且因为$(a,b)=1$，所以 $p\mid a$ 或 $p\mid b$。这里有两种等价的情形，可以取其中之一 $p\mid a$ 来进行考虑。观察 $x\pmod p$：

$$
\begin{aligned}
x&\equiv sb^{-1}b+ta^{-1}a&(p\mid a)\\
&\equiv sb^{-1}b&(b^{-1}b\equiv1)\\
&\equiv s\pmod {p}
\end{aligned}
$$

加上 $p\mid x$，因此 $p\mid s$，所以 $(a,s)\ge p$，这跟“ $a$ 和 $s$ 互质”的前提矛盾；因此 “$(x,ab)\gt1$”的假设不能成立，换言之$x$ 和 $ab$ 互质。利用中国剩余定理可以知道，在 $(a,b)=1$ 的前提下，_对于任意一个和 $a$ 互质的整数 $s$ 以及任意一个和 $b$ 互质的整数 $t$，都能找到唯一一个和 $ab$ 互质的整数 $x$_。

#### 推论2

反过来可以得到第二个推论。假如 $(x,ab)=1$，那么 $(x,a)=1$。又因为 

$$
x\equiv s\pmod a\implies x=ks+a\implies (ks+a,a)=1
$$

所以 $(s,a)=1$。同理$(t,b)=1$。换言之，_对于每一个和 $ab$ 互质的整数 $x$，都能找到一个整数对 $(s,t)$，满足 $s$ 和 $a$ 互质且 $t$ 和 $b$ 互质_。

#### 双射函数

令

$$
\begin{aligned}
A&=\{u\mid 1\le u\le a\text{, }u\in\mathbb{Z}\text{ and }(u,a)=1\}\text{, }&\mid A\mid &=\varphi(a)\\
B&=\{u\mid 1\le u\le b\text{, }u\in\mathbb{Z}\text{ and }(u,b)=1\}\text{, }&\mid B\mid &=\varphi(b)\\
D&=\{u\mid 1\le u\le ab\text{, }u\in\mathbb{Z}\text{ and }(u,ab)=1\}\text{, }&\mid D\mid &=\varphi(ab)\\
\end{aligned}\\
$$

定义

$$
f:A\times B\to D
$$

第一个推论表示 $f$ 是单射，第二个推论表示 $f$ 是满射，这两个结果说明 $f$ 是双射，因此 $\mid A\times B\mid =\mid D\mid $，即 

$$\varphi(ab)=\varphi(a)\varphi(b)\tag{Q.E.D}$$

## 欧拉定理
在欧拉函数定义的基础上，对于任意跟 $n$ 互质的正整数 $a$，也就是 $\gcd(n,a)=1$，都有

$$a^{\varphi(n)}\equiv1\pmod n$$

称为[欧拉定理(Euler's theorem)](https://zh.wikipedia.org/wiki/%E6%AC%A7%E6%8B%89%E5%AE%9A%E7%90%86_(%E6%95%B0%E8%AE%BA))。欧拉定理实际上是[费马小定理(Fermat's little theorem)](https://zh.wikipedia.org/wiki/%E8%B4%B9%E9%A9%AC%E5%B0%8F%E5%AE%9A%E7%90%86)的模推广到所有正整数的结果。

### 费马小定理

根据费马小定理，给定**质数** $p$，对于任意不能被 $p$ 整除的整数 $a$，都有

$$a^{p-1}\equiv1\pmod p$$

费马小定理的证明非常容易，这里就不赘述。这个定理有另一个形式：对于所有整数 $a$ （包括被 $p$ 整除）都有

$$a^p\equiv a\pmod p$$


### 底数的特殊情形

当 $(a,n)\ne 1$ 时，欧拉函数也有类似的结果：如果 $n=st$ 且 $\gcd(s,t)=1$，那么对于 $x=s$ 或者 $x=t$

$$
x^{\varphi(n)+1}\equiv x\pmod n\tag{1}
$$

证明如下。因为 $\gcd(s, t)=1$，所以可以利用欧拉定理得到

$$
s^{\varphi(t)}\equiv 1\pmod t\implies t\mid {s^{\varphi(t)}-1}\tag{2}
$$

观察到 

$$
\begin{aligned}
s^{\varphi(n)}-1&=s^{\varphi(s)\varphi(t)}-1\\
&=\big(s^{\varphi(t)}\big)^{\varphi(s)}-1\\
&=(s^{\varphi(t)}-1)Q
\end{aligned}
$$

其中 $Q$ 是某个整数多项式。然后$(2)$ 式可以进一步得到

$$
\begin{aligned}
t\mid {(s^{\varphi(t)}-1)Q}&\implies t\mid s^{\varphi(n)}-1\\
&\implies t\mid s^{\varphi(n)+1}-s\\
\end{aligned}
$$

另外，一个显而易见的事实是 $s\mid s^{\varphi(n)+1}-s$，加上 $(s,t)=1$，所以

$$
\begin{aligned}
st\mid s^{\varphi(n)+1}-s&\implies n\mid s^{\varphi(n)+1}-s\\
&\implies s^{\varphi(n)+1}\equiv s\pmod n
\end{aligned}
$$

这表示如果 $n$ 能够分解成两个互质的因数 $s$ 和 $t$ ，那么 $x=s$ 和 $x=t$ 都分别能满足 $x^{\varphi(n)+1}\equiv x\pmod n$ 。实际上，如果 $n$ 分解为两个以上互质的因数，这些因数也分别能满足这个同余关系。

需要注意的是，$(1)$ 式的底数并不能像费马小定理一样推广到所有正整数，对于部分$x$，$x^{\varphi(n)+1}$ 可能和 $0$ 同余；不过，如果 $(a,n)=s$，$x=a$ 也能满足 $(1)$ 式。这是因为 $a=\frac{a}{s}\cdot s$ 且 $\frac{a}{s}\in\mathbb{Z^+}$，而且 $(\frac{a}{s}, n)=1$，对 $\frac{a}{s}$ 使用欧拉定理可知

$$
(\frac{a}{s})^{\varphi(n)}\equiv1\pmod n\implies(\frac{a}{s})^{\varphi(n)+1}\equiv\frac{a}{s}\pmod n\tag{3}
$$

加上 $(1)$ 中 $x=s$ 的结果

$$
s^{\varphi(n)+1}\equiv s\pmod n\tag{4}
$$

$(3)\times(4)$ 可以得到

$$
\begin{aligned}
(\frac{a}{s}\cdot s)^{\varphi(n)+1}&\equiv\frac{a}{s}\cdot s\pmod n\\
a^{\varphi(n)+1}&\equiv a\pmod n
\end{aligned}\tag{Q.E.D}
$$

这个结果保证了RSA算法在底数为任意整数的加解密过程中的正确性。