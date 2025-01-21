---
toc: true
layout: "post"
catalog: true
title:  "HTTPS nginx 反向代理"
date:   2022-03-14 12:10:38 +0800
header-img: "img/jp-biwako.jpg"
categories: 
  - blog
tags:
  - ubuntu 
  - https
  - nginx
  - proxy
  - openssl
---

这里使用了腾讯云CVM ubuntu 作为服务器，SSL证书同样来自腾讯云。实现目标如下：

- 在80端口启动一个没有HTTPS的httpd作为后台服务，但是不让外部访问80（可以通过腾讯云安全组限制）；
- 在443端口启动nginx反向代理，将外部请求导流到本地80端口的httpd。

拓扑关系图如下：

```
浏览器 <--HTTPS--> nginx(反向代理) <--HTTP--> httpd(业务)
```

如果没有其他网关或者代理，浏览器和nginx、nginx和httpd之间将会各自建立一个TCP连接；其中浏览器和nginx的HTTPS在TLS隧道上进行。

## HTTPS 握手过程

简单描述一下建立 TLS1.2 HTTPS 会话的过程，IBM有[一篇文章详细描述了这个过程](https://www.ibm.com/docs/en/sdk-java-technology/7.1?topic=handshake-tls-12-protocol)，同时也可以用wireshark抓包来对比观察这个过程。

```
Client |-------client hello----->| Server
       |                         |
       |<------server hello------|
       |<------certificate-------|
       |<--certificate  status---|
       |<--server key exchange---|(optional)
       |<---server hello done----|
       |                         |
       |---client key exchange-->|
       |----client hello done--->|(我没观测到-_-|||)
       |                         |
       |<-----encrypted data---->|
```

1. 浏览器发送一些初始参数，其中包含TLS的版本（1.2）和若干个支持的[密码suite](https://en.wikipedia.org/wiki/Cipher_suite)，供服务器选择，每个suite都包含key exchange算法、身份验证算法和bulk exchange算法在内的若干个信息。以[TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384](https://ciphersuite.info/cs/TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384/)为例，这个suite将使用ECDHE交换密钥，用RSA进行身份验证，用AES256GCM对数据流进行对称加密，以及用SHA384进行数字签名。
2. 服务器发送已选择的密码suite以及证书。server key exchange 还会交换一段信息，通常是因为客户端无法通过证书的公钥获取足够信息来产生密钥。
3. 浏览器发送用于产生对成加密密钥的信息。
4. 交换密钥信息完成后，TLS隧道建立完成。浏览器和服务器在这个隧道上进行HTTP会话。

TLS1.2至少需要2-RTT，而 TLS1.3 由于强制使用 DH 算法仅仅 1-RTT 就能完成握手。

## 搭建反向代理

### 证书

HTTPS少不了证书，证书文件有两种存储方式：文本和二进制。

文本存储用的是[PEM格式(Privacy Enhanced Mail)](https://en.wikipedia.org/wiki/Privacy-Enhanced_Mail)，这种格式用base64编码内容，可以用一般的文本编辑器打开查看，以 `-----BEGIN XXX-----`换行开头、以`-----END XXX-----`，XXX在这里是 `CERTIFICATE`。按理说PEM不止用来存储证书，也可以单独存储公钥和私钥。`ssh-keygen`命令默认生成的密钥对就是用的PEM格式。PEM格式可以用 `*.crt` 和 `*.pem`作为拓展名。

二进制存储用的是ASN.1 格式，无法直接用文本编辑器打开，这种文件扩展名一般是 `*.der`。从 chrome 的小锁头导出来的证书就是用的这个格式。

搭建反向代理之前首先得有一个有效的证书，为了说明效果、先不要用自己签的；我用的是腾讯云上面免费签1年的。一般来说需要三个文件：证书(.crt)、私钥(.key)和 root_bundle.crt(也不知道中文该叫啥)。


### 自签证书

有时候基于开发测试原因、我们需要弄一个自己签发的证书，比如需要给IP签发证书，但是腾讯云的免费套餐并不支持～ 关于如何生成自签证书的详细步骤，可以参考台湾网友写的[这篇文章](https://blog.miniasp.com/post/2019/02/25/Creating-Self-signed-Certificate-using-OpenSSL)，我这里简单记录一下操作步骤。

首先编写配置文件

```conf
[req]
prompt = no
default_md = sha256
default_bits = 2048
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = CN
O = Test Inc.
OU = Test Department
CN = localhost

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = *.localhost
DNS.2 = localhost
IP.1 = 192.168.2.100 # 重要！如果要给IP签发证书就要改这个
```

dn小节里的内容都不重要，主要是alt_names里的东西要写对。然后通过openssl生成证书和私钥

```shell
openssl req -x509 -new -nodes -sha256 -utf8 -days 3650 -newkey rsa:2048 -keyout server.key -out server.crt -config ssl.conf
```

除非将该证书导入到OS、正常的浏览器都不会信任证书～所以如果要出现小锁头还得手动导入一下。

### httpd 服务器

然后用一个httpd模拟无加密的后台服务。安装httpd，在ubuntu上其实是叫apache2。

```shell
sudo apt-get install apache2 -y
# 这个时候访问80端口会发现是HTTP
```

ubuntu httpd 的配置文件在 /etc/apache2/apache2.conf 。

### 配置 nginx HTTPS

如果跟着前面启用了httpd的https功能，到这里为了说明效果得先把httpd的https关掉

```
sudo a2dissite default-ssl
sudo a2dismod ssl
sudo systemctl reload apache2
```
然后开始操作nginx

```shell
# 首先得装一个nginx
sudo apt-get install nginx
```

这里的nginx在安装完成之后并没有马上起来，估计是因为80端口被httpd占用掉了，先不管。nginx 默认的配置文件在 /etc/nginx/nginx.conf ，不过我打算用自己的配置文件`/usr/share/nginx/nginx.conf` 。这里参考了[这篇文章](https://www.supereasy.com/how-to-configure-nginx-as-a-https-reverse-proxy-easily/)

```nginx
user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
	worker_connections 768;
}

http {
	sendfile on;
	tcp_nopush on;
	tcp_nodelay on;
	keepalive_timeout 65;
	types_hash_max_size 2048;
	# server_tokens off;

	# server_names_hash_bucket_size 64;
	# server_name_in_redirect off;

	include /etc/nginx/mime.types;
	default_type application/octet-stream;

	access_log /var/log/nginx/access.log;
	error_log /var/log/nginx/error.log;

	gzip on;
    	server {
		listen 443 ssl;
		# 证书文件路径
		ssl_certificate PATH_TO_YOUR_CERT;
		# 私钥文件路径
		ssl_certificate_key PATH_TO_YOUR_KEY;
		ssl_session_timeout 5m;
                # SSL 版本
		ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
		ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:HIGH:!aNULL:!MD5:!RC4:!DHE;
		ssl_prefer_server_ciphers on;
        	server_name YOUR_DOMAIN_NAME;
		
		location / {
			proxy_pass http://localhost;
			proxy_set_header Host $host;
			proxy_set_header X-Real-IP $remote_addr;
			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header X-Forwarded-Proto https;
		}
    	}
}

```

有几点需要注意：

- ssl_protocols 和 ssl_ciphers 要根据证书实际支持的版本以及密码suite来填
- ssl_certificate nginx的证书跟httpd的还有点差异，实际上是由两个证书(`root_bundle.crt`, `*.crt`)组成的文件，同时必须让 `root_bundle.crt` 出现在前面，两个证书之间得有一个换行。
  - 腾讯云的SSL控制台有下载入口，可以根据不同的应用类型下载对应的证书；如果证书是从名为 nginx 的入口下载的可以直接用了，否则得手动拼接一下证书（注意腾讯云的证书后面没有换行😭）
  - 按照nginx的[指引](http://nginx.org/en/docs/http/configuring_https_servers.html) `cat www.example.com.crt bundle.crt > www.example.com.chained.crt`

编辑保存配置文件之后先测试一下文件有没有语法错误

```shell
sudo nginx -t -c /usr/share/nginx/nginx.conf
```

确认无误之后可以启动nginx

```shell
# 启动
sudo nginx -c /usr/share/nginx/nginx.conf
# 重启
# sudo nginx -s reload -c /usr/share/nginx/nginx.conf
# sudo netstat -lntp 
# 可以看到nginx已经在监听443端口了
```

最后通过浏览器访问https，可以看到左上角出现一个小锁头了，真是可喜可贺，可喜可贺。

### 使用 nginx 容器

除了直接在服务器上部署nginx以外，还可以通过容器部署反向代理。具体的操作方法跟上面提到的流程差不多，需要在Dockerfile里把证书和nginx.conf[拷贝到镜像里](https://hub.docker.com/_/nginx)：


```Dockerfile
FROM nginx
COPY nginx.conf /etc/nginx/nginx.conf
# 还有证书
```

如果被代理的服务也是容器化的，建议用docker-compose管理。这个方式有个好处就是可以利用docker自带的DNS，在nginx.conf的`proxy_pass` directive里可以直接用服务的名字作为域名，举个例子，假如被代理的是一个flask服务，名字是`my-flask-service`，在nginx.conf里可以直接写

```
proxy_pass http://my-flask-service
```

然后在docker-compose.yml里，nginx的部分需要depends_on `my-flask-service`。为了能让外部访问、记得在docker-compose.yml给nginx加端口映射。

如果被代理的服务是在宿主机上，有以下办法可以让nginx容器能访问宿主机的服务：

- 让容器[使用宿主机的网络](https://stackoverflow.com/a/48547074/8706476)。docker run的时候给一个参数 `--net=host`，nginx.conf 直接使用 localhost，也不需要加端口映射（亲测好用）；
- 对于mac/win的docker，或者是[20.01以后版本的docker](https://github.com/moby/moby/pull/40007#issue-499875390)，可以使用域名`http://host.docker.internal`访问宿主机（没试过）。20.01版本以前的linux docker没有这个功能


## httpd单独启用HTTPS

其实 httpd 可以 启用https功能，而不需要 nginx。默认情况下SSL模块是没有开启的，可以 ls mods-enabled 看到下面没有ssl.conf
。实际上SSL模块的配置文件在 mods-available 下面。在ubuntu上对httpd启用/关闭功能需要通过 `a2enmod/a2ensite`、`a2dismod/a2dissite`来执行。

```shell
sudo a2enmod ssl # 启用SSL模块。之后 ls mods-enabled 就可以看到新增的 ssl.conf
# 然后需要启用 https site
sudo a2ensite default-ssl
# 编辑 default-ssl.conf
vim sites-enabled/default-ssl.conf 
```

编辑default-ssl.conf的以下内容

```apache
#   SSL Engine Switch:
#   Enable/Disable SSL for this virtual host.
SSLEngine on # 确保这个要打开

#   A self-signed (snakeoil) certificate can be created by installing
#   the ssl-cert package. See
#   /usr/share/doc/apache2/README.Debian.gz for more info.
#   If both key and certificate are stored in the same file, only the
#   SSLCertificateFile directive is needed.
SSLCertificateFile      PATH_TO_YOUR_CERT # 证书文件的路径
SSLCertificateKeyFile   PATH_TO_YOUR_KEY # 证书文件私钥的路径

#   Server Certificate Chain:
#   Point SSLCertificateChainFile at a file containing the
#   concatenation of PEM encoded CA certificates which form the
#   certificate chain for the server certificate. Alternatively
#   the referenced file can be the same as SSLCertificateFile
#   when the CA certificates are directly appended to the server
#   certificate for convinience.
SSLCertificateChainFile PATH_TO_YOUR_CERT_CHAIN # bundle.crt的路径
```

保存之后重启下httpd，然后通过浏览器访问https就可以看到小锁头了。

```shell
sudo systemctl restart apache2
```