---
toc: true
layout: "post"
catalog: true
title:  "数论学习笔记 - 欧几里得算法"
date:   2021-11-27 11:51:38 +0800
subtitle: "ちいさなそんざいだけど、大きな夢があるから"
header-img: "img/sz-talent-park-bg.jpg"
mathjax: true
categories: 
  - blog
tags:
  - cryptography
  - number theory
---

# 欧几里得算法

欧几里得算法是一个用来计算两个整数的最大公因数的算法，最早出现在欧几里得的《几何原本》（wiki语）。

## 辗转相除法

在天朝，该算法又叫做“辗转相除法”。为了求得两个正整数 $a$ 和 $b$ 的最大公因数，首先用 $b$ 除 $a$ 得到余数 $d_1$，然后将 $b$ 作为被除数、$d_1$ 作为除数，用 $d_1$ 除 $b$ 得到余数 $d_2$，然后分别将 $d_1$ 和 $d_2$ 作为被除数和除数重复此流程，直到得到 $d_{n-1}=kd_n$ 且余数为 $0$，这时候的 $d_n$ 就是整数 $a$ 和 $b$ 的最大公因数。

### 算法

用数学符号表示辗转相除法的过程，$d_0=b$，$d_i$ 非负且 $d_i\lt d_{i-1}$

$$
\begin{aligned}
a-bq_1&=d_1\\
b-d_1q_2&=d_2\\
&\cdots\\
d_{i-2}-d_{i-1}q_n&=d_{i}\\
&\cdots\\
d_{n-2}-d_{n-1}q_n&=d_{n}\\
d_{n-1}-d_nq_{n+1}&=d_{n+1}
\end{aligned}
$$

当出现 $d_{n+1}=0$ 时，正整数 $d_n$ 就是 $a$ 和 $b$ 的最大公因数。

### 证明

首先，因为 $d_i$ 非负且 $d_i\lt d_{i-1}$，

$$
0\le d_{n+1}\lt d_{n} \lt d_{n-1} \lt\cdots\lt d_2\lt d_1
$$

所以 $d_i$ 是一个不断减小的非负整数的序列，最多在 $n+1$ 个步骤之后出现 $d_{n+1}=0$ 而且 $d_{n}\gt 0$。因此该算法总能在有限个步骤内结束。

自底向上看，在第 $n+1$ 步可知 $d_n\mid d_{n-1}$，结合 $d_{n-2}-d_{n-1}q_n=d_{n}$ 可以推出 $d_n\mid d_{n-2}$。同理，可以相继推断出 

$$
d_n\mid d_{n-3}\text{, }d_n\mid d_{n-4}\text{, }\cdots\text{, }d_n\mid d_{2}\text{, }d_n\mid d_{1}
$$

所以 $d_n\mid b$ 且 $d_n\mid a$，因此 $d_n$ 是 $a$ 和 $b$ 的公因数，即 

$$d_n\le\gcd(a,b)\tag{1}$$

自顶向下看，在第一步可知 $\gcd(a,b)\mid d_1$，结合第二步 $b-d_1q_2=d_2$ 可知 $\gcd(a,b)\mid d_2$。同理，可以相继推断出

$$
\gcd(a,b)\mid d_3\text{, }\cdots\text{, }\gcd(a,b)\mid d_{n-2}\text{, }\gcd(a,b)\mid d_{n-1}
$$

所以 $\gcd(a,b)\mid d_{n}$；加上 $d_{n}\gt0$，因此 $\gcd(a,b)\le d_{n}$。结合 $(1)$ 式，得到 

$$d_n=\gcd(a,b)\tag{Q.E.D}$$

这个算法可以用非常简单，可以用以下代码实现：

```python
def gcd(a, b):
    while True:
        d = a % b
        if d == 0:
            return b
        a, b = b, d
```

顺便提一个点就是代码无需比较 $a$ 和 $b$ 的大小并且调换被除数和除数的顺序。即使 $a\lt b$，在第二轮里数值较大的 $b$ 就会变成被除数、上一轮较小的 $a$ 会变成除数。

## 扩展欧几里得算法

在欧几里得算法的基础上还可以做进一步推断：存在整数 $s$ 和 $t$ 满足

$$
as+bt=\gcd(a,b)\tag{2}
$$

整数 $s$ 和 $t$ 可以使用改进之后的欧几里得算法计算得到，这里先从证明入手。首先，欧几里得算法中每一个步骤中的 $d_i$ 都可以写成 $a$ 和 $b$ 的多项式

$$
as_i+bt_i=d_i\tag{3}
$$

这个结果不是瞎猜的：观察辗转相除法的前两条等式

$$
\begin{aligned}
d_1&=a\times1-b\times q_1\\
d_2&=b-d_1q_2=a\times(-1)+b\times(1+q_1q_2)\\
\end{aligned}
$$

将上述两个等式代入 $d_3=d_1-d_2q_3$

$$
\begin{aligned}
d_3&=(a-bq_1)-[a\times(-1)+b\times(1+q_1q_2)]q_3\\
&=a\times(1+q_3)+b\times[-q_1-(1+q_1q_2)q_3]
\end{aligned}
$$

所以 $d_3$ 也可以用关于 $a$ 和 $b$ 的多项式表示。实际上

### 证明

这个可以用归纳法证明。当 $i=1$ 时，$s_1=1$ 且 $t_1=-q_1$

$$a-bq_1=a\times1+b\times(-q_i)=d_1$$

当 $i=2$ 时，将 $d_1=a-bq_1$ 代入 $b-d_1q_2=d_2$

$$b-(a-bq_1)q_2=a(-q_2)+b(1+q_1q_2)=d_2$$

所以 $s_2=-q_2$ 且 $t_2=1+q_1q_2$，当 $i=1$ 或者 $i=2$ 时，$(3)$ 式成立。

假设当 $i\lt k$ 时，$(3)$ 式成立，换言之 $i=k-2$ 或 $i=k-1$ 时，存在以下等式

$$
\begin{aligned}
as_{k-2}+bt_{k-2}&=d_{k-2}\\
as_{k-1}+bt_{k-1}&=d_{k-1}\\
\end{aligned}
$$

将上述等式代入 $b_{k-2}-b_{k-1}q_{k}=d_{k}$ 可以得到

$$
\begin{aligned}
d_{k}&=(as_{k-2}+bt_{k-2})-(as_{k-1}+bt_{k-1})q_{k}\\
&=a(s_{k-2}-s_{k-1}q_k)+b(t_{k-2}-t_{k-1}q_k)
\end{aligned}
$$

令 $s_k=s_{k-2}-s_{k-1}q_k$，$t_k=t_{k-2}-t_{k-1}q_k$，因此 $d_k=as_k+bt_k$。这说明 $d_k$ 也可以写成关于 $a$ 和 $b$ 的多项式的形式，原假设 $(3)$ 对于 $i=k$ 也成立。换句话说，最大公因数 $d_n=\gcd(a,b)$ 也可以用 $a$ 和 $b$ 的多项式来表达

$$as_n+bt_n=d_n\tag{Q.E.D}$$

### 算法

上述归纳证明还给出了 $s_i$ 和 $t_i$ 的递推计算方式

$$
\begin{aligned}
s_i&=s_{i-2}-s_{i-1}q_i\\
t_i&=t_{i-2}-t_{i-1}q_i\\
d_i&=d_{i-2}-d_{i-1}q_i\\
\end{aligned}
$$

且 $i\ge2$。这里为了实现方便可以对 $i\lt2$ 的情况可以稍加修改，根据 $s_1$ 和 $s_2$ 逆推 $s_0$ 的值，${t_0}$ 同理

$$
\begin{cases}
s_0=0\\
t_0=1
\end{cases}
\text{ and }
\begin{cases}
s_1=1\\
t_1=-q_1&(a=bq_1+d_1)\\
\end{cases}
$$

实际上用代码实现的时候只需要计算 $t$ 或 $s$ 当中的其中之一就可以了，另一个可以通过 $a$，$b$ 以及 $\gcd(a,b)$ 计算出来。

```python
def euclid_ex(a,b):
    to, tn, ao, bo = 0, 1, a, b
    while True:
        d = a % b
        if d == 0:
            return (bo - bo * tn) // ao, tn, b
        q = a // b
        to, tn = tn, to - tn * q
        a, b = b, d
```


## 贝祖定理

前面的扩展欧几里得算法提到的 $(2)$ 式：存在整数 $s$ 和 $t$ 满足

$$
as+bt=\gcd(a,b)\tag{2}
$$

实际上，能满足 $as+bt$ 形式的**最小整数**就是 $\gcd(a,b)$，是为[贝祖定理](https://zh.wikipedia.org/wiki/%E8%B2%9D%E7%A5%96%E7%AD%89%E5%BC%8F)。

这是显而易见的。假设存在 $d\le\gcd(a,b)$ 使得 $as'+bt'=d$，由于 $\gcd(a,b)\mid a$ 且 $\gcd(a,b)\mid b$，所以 $\gcd(a,b)\mid d\implies d\ge\gcd(a,b)$。结合假设，可知 $d=\gcd(a,b)$。

特别地，如果 $a$ 和 $b$ 互质，那么存在 $s$ 和 $t$ 使得

$$
ax+by=1
$$

## 算法效率

TODO

<!-- 施工中 -->

