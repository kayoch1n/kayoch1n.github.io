---
toc: true
layout: "post"
catalog: true
title:  "nginx HTTPS 反向代理"
date:   2022-03-14 12:10:38 +0800
subtitle: "元気を出さないと、ご飯もおいしくないよ"
header-img: "img/sz-transmission-tower-2.jpg"
categories: 
  - blog
tags:
  - ubuntu 
  - https
  - nginx
---

# nginx HTTPS 反向代理

本文使用了腾讯云CVM（ubuntu）作为服务器，SSL证书同样来自腾讯云。

实现目标如下：
- 在80端口启动一个没有HTTPS的httpd作为后台服务，但是不让外部访问80（可以通过腾讯云安全组限制）；
- 在443端口启动nginx反向代理，将外部请求导流到本地80端口的httpd。

## Prerequisite

首先得有一个有效的证书，为了说明效果、先不要用自己签的。

一般来说需要三个文件：证书(.crt)、私钥(.key)和 root_bundle.crt(也不知道中文该叫啥)。可以用腾讯云上面免费的（虽然只有一年）。

先把上面三个文件通过scp命令传输到ubuntu上的用户目录并且解压。

```shell
scp *.zip ubuntu@xxx.xxx.xxx.xxx:~/
# 输入密码就可以
```

## httpd
然后安装httpd，在ubuntu上其实是叫apache2。


```shell
sudo apt-get install apache2 -y
# 这个时候访问80端口会发现是HTTP
```

ubuntu httpd 的配置文件在 /etc/apache2/apache2.conf 默认情况下SSL模块是没有开启的，可以 ls mods-enabled 看到下面没有ssl.conf
。实际上SSL模块的配置文件在 mods-available 下面

### (番外篇)单独使用HTTPS的httpd

在说明如何配置nginx之前，先来看下不使用nginx的https反代、怎么单独使用httpd的https功能。在ubuntu上对httpd启用/关闭功能需要通过 `a2enmod/a2ensite`、`a2dismod/a2dissite`来执行。

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

## nginx

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

这里的nginx在安装完成之后并没有马上起来，估计是因为80端口被httpd占用掉了，先不管。nginx 默认的配置文件在 /etc/nginx/nginx.conf ，不过我打算用自己的配置文件/usr/share/nginx/nginx.conf

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

- ssl_protocols 和 ssl_ciphers 要根据证书实际支持的版本以及加密算法来填
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

## MISC

- https://www.supereasy.com/how-to-configure-nginx-as-a-https-reverse-proxy-easily/
