---
toc: true
layout: "post"
catalog: true
title:  "《深入浅出密码学》中的数学芝士"
date:   2021-05-02 12:10:38 +0800
header-img: "img/sz-talent-park-bg.jpg"
categories: 
  - blog
tags:
  - cryptography
  - number theory
---
# 正文

《深入浅出密码学》_Understanding Cryptography: A Textbook for Students and Practitioners_ 是一本可读性非常强的密码学著作。跟面向在校学生的数学课本比起来，这本书着眼于密码学的实际应用，略去大部分晦涩的数学原理；刚毕业上过一两年班的社畜码农（指那些不敢从早到晚一直摸鱼的，比如我）可以较为流畅地读下去，同时也接触到许多数学概念。

<!-- ## 对称加密

### AES

#### AES的S-Box

#### AES的操作模式 -->

## 公钥加密

目前应用最广泛的公钥加密原理是三种，分别是RSA的整数分解问题、_Diffie-Hellman_ 密钥交换的离散对数问题和椭圆曲线（不是圆锥曲线）问题。

### RSA原理

RSA的加密过程用公式表示为 $ x^e \equiv y \pmod m $，解密过程为 $ y^d \equiv x \pmod m$。其中，
1. $m=pq$，$p$ 和 $q$ 是两个素数；
2. $e$ 和 $m$ 为公钥，$d$ （或者 $p$ 和 $q$）是私钥；
3. $e$ 和 $d$ 互为模 $m$ 乘法逆，即满足 $ ed \equiv 1 \pmod {\phi(m)}$。
    - 该条件的前提是 $\gcd(e, \phi(m))=1$；
    - $d$ 可通过扩展欧几里得算法计算出。根据[贝祖定理](https://zh.wikipedia.org/wiki/%E8%B2%9D%E7%A5%96%E7%AD%89%E5%BC%8F)，这样的 $d$ 必然存在。
4. $\phi(m)$ 是欧拉函数，$\phi(m)=(p-1)(q-1)$； 

书中给出了关于RSA加密解密正确性的解释；只要看到上面的几个定义，就可以很快理解这一过程，因此这里不再记录了。

RSA的单向函数(_one-way function_)和整数分解问题有关：计算两个数的乘积是简单的，但将一个整数分解成若干个因数是困难的。上述私钥 $d$ 的计算依赖 $\phi(m)=(p-1)(q-1)$。目前没有解决整数分解的有效算法，只能靠暴力枚举获得 $m$ 的分解方式。假设整数乘法所消耗的时间是一个常数，这个过程的时间复杂度为 $\mathcal{O}(\sqrt {m})$；如果 $m$ 的二进制表示的长度为 $n$ ，实际的复杂度是**指数级别**的 $\mathcal{O}(\sqrt m)=\mathcal{O}(\sqrt {2^n})=\mathcal{O}(2^{\frac{n}{2}})$ 。

#### 快速幂

平方求幂(squaring-and-multiply)

$$
a^{k}=a^{\sum_{i}^{n}{2^id_i}}=a^{2^0d_0}\times a^{2^1d_1}\times\dots\times a^{2^n d_n}\text{, } d_i\in \{0, 1\}
$$

double-and-add

$$
k\times a=a\times\sum_{i}^{n}{2^id_i}=a\times{2^0d_0}+ a\times{2^1d_1}+\dots+a\times{2^n d_n}\text{, } d_i\in \{0, 1\}
$$

从MSB开始

#### 蒙哥马利算法

#### 利用孙子定理加速解密过程

书里讲了如何利用孙子定理（又叫中国剩余定理）加速解密过程，但是没有对孙子定理做进一步解释。简单来说，这个定理解决的是形如“已知一个正整数除以3余2、除以5余3、除以7余2、求这个整数的最小值”的问题。用公式去描述就是，求同时满足以下条件的最小正整数。

$$
\begin{aligned}
x_1&\equiv a_1 \pmod {p_1} \\
x_2&\equiv a_2 \pmod {p_2} \\
&\ldots \\
x_n&\equiv a_n \pmod {p_n} \\
\end{aligned}
$$

其中，$p_i$ 是素数。wiki给出了构造解的一般形式为：

$$
\begin{gathered}
x=\sum_{i=1}^{n}{a_iA_iA_i^{-1}} +k\prod_{i=1}^{n}{p_i}\text{, }k \in \mathbb{Z} \\
A_i=\prod_{j=1, j\ne i}^{n}{a_j} \\
A_iA_i^{-1}\equiv 1 \pmod {p_i} \\
\end{gathered}
$$

容易看出，$a_iA_iA_i^{-1} \equiv a_i \pmod {p_i}$；另外， $\forall j\ne i\text{, }{A_j} \equiv 0 \pmod {a_i} \implies a_jA_jA_j^{-1} \equiv 0 \pmod {p_i}$，因此 $\sum_{i=1}^{n}{a_iA_iA_i^{-1}} \equiv a_i \pmod {p_i}$。构造解的一般形式能满足上述一次同余方程组，解的存在性得证。

公钥加解密大都涉及大整数运算，比如两个大整数的乘法，不能像32或64bit整数乘法那样能够在一个指令周期运算。在RSA场景下，孙子定理的作用是将大整数 $m$ 取余问题转化为两个相对小素数 $p$ 和 $q$ 的取余问题，而且 $p$ 和 $q$ 的二进制长度通常是 $m$ 的一半，从而减少整数乘法耗时。

特别地，在运用孙子定理对密文进行解密之前，RSA会对密文进行处理，将密文的幂次数从 $d$ 分别降低到 $d_p$ 以及 $d_q$：

$$
\begin{aligned}
y_p \equiv y^{d} \equiv y^{d_p} \pmod p \\
y_q \equiv y^{d} \equiv y^{d_p}\pmod q \\
\end{aligned}
$$

其中，$d_p \equiv d\pmod {\phi(p)}$ 以及 $d_q \equiv d\pmod {\phi(q)}$。幂次数的降低可以证明。如果 $\gcd(y,p)=p$，那么 $y_p \equiv y^{d} \equiv y^{d_p} \equiv 0 \pmod p$；否则$\gcd(y,p)=1$，那么可以运用费马小定理 $y^{\phi(p)}\equiv 1\pmod {p}$，得到

$$
\begin{aligned}
y^{d} \equiv y^{d_p+t\phi(p)} \equiv y^{d_p} \pmod p 
\end{aligned}
$$


#### 如何挑选出素数

如前文所述，RSA需要两个素数；实际上RSA通过随机整数生成器挑选素数，这里需要解决两个问题：

- 素数的分布规律如何？
- 如何检验一个随机整数是否素数？

第一个问题会影响挑选素数的效率。给定一个整数 $N$ 表示筛选范围，$\pi(N)$ 表示小于 $N$ 的素数的个数，那么随机整数是素数的概率是$\frac{\pi(N)}{N}$。根据素数定理，$\pi(N) \sim \frac{N}{\ln N} \implies \frac{\pi(N)}{N} \sim \frac{1}{\ln N}$。这个近似在wiki上有描述，但是超出我的芝士范围了实在看不懂😣。

和分析整数分解复杂度类似，假设 $N$ 有 $n$ 个比特，那么随机整数是素数的概率近似于 

$$
\begin{gathered}
\frac{1}{\ln N}=\frac{1}{\ln{2^n}}=\frac{1}{n\ln 2}
\end{gathered}
$$

而且如果只检测奇数的话，这个概率还能翻倍。例如，长度为1024，这个概率就是 $\frac{2}{1024\times \ln 2}\approx\frac{1}{354}$，这表示使用者期望至少需要随机生成354个整数才能找到一个素数。

<!-- 针对第二个问题，在现有算法中没有除了枚举以外的有效算法，而书里给出两种概率算法。第一个算法基于费马小定理。由于费马小定理是素数的必要条件，而不是充分条件；对于部分合数，例如卡米克尔数(_Carmichael numbers_) $m$，

$$
\forall a\in \{a|a\in \mathbb Z \text{ and } \gcd(a, m)=1\} \implies a^{m-1} \equiv 1 \pmod m
$$

用费马小定理检测这类合数都会失效。 -->

### 离散对数

像我这种非数学专业的本科菜鸡，在学校的时候是不会自觉接触跟数论有关的知识的（理直气壮）。

$$
\begin{aligned}
\alpha^{x}&\equiv \beta  &\pmod p \\
x&\equiv \log_{\alpha}{\beta} &\pmod p
\end{aligned}
$$

#### 循环群

由生成元的定义可知，这个解必然存在

#### Elgamal scheme

nondeterministic