---
layout: post
title:  "Ubuntu安装各种包"
date:   2020-04-10 21:15:38 +0800
---
# Install packages on Ubuntu

## Perl Modules

Follow the steps [here](http://www.cpan.org/modules/INSTALL.html) to install perl modules. Type `cpan`:

```shell
# Optional. 
# Modify mirror
cpan[16]> o conf urllist
    urllist           
        0 [http://www.cpan.org/]
Type 'o conf' to view all configuration items


cpan[17]> o conf urllist pop http://www.cpan.org/
Please use 'o conf commit' to make the config permanent!


cpan[18]> o conf commit
commit: wrote '/home/ubuntu/.cpan/CPAN/MyConfig.pm'

cpan[20]> o conf urllist push http://mirrors.aliyun.com/CPAN/
Please use 'o conf commit' to make the config permanent!


cpan[21]> o conf commit
commit: wrote '/home/ubuntu/.cpan/CPAN/MyConfig.pm'

cpan[22]> o conf urllist
    urllist           
        0 [http://mirrors.aliyun.com/CPAN/]
Type 'o conf' to view all configuration items


cpan[23]> quit
```

```shell
# 1. Enable cpan. Press yes to continue
sudo cpan App::cpanminus
# 2. Install wanted modules.
sudo cpanm HTML::Entities
```

## Usage

[Scripts](https://stackoverflow.com/a/13161719/8706476) to convert HTML entities to characters:

```shell
curl http://cms.nuptzj.cn/about.php?file=about.php | perl -MHTML::Entities -pe 'decode_entities($_);' > about.php
```
## Docker 
[Installation guide](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-from-a-package)

### Get docker packages
- check **codename** of ubuntu distribution `lsb_release -c`
- determine **architecture** on which ubuntu is installed `uname -a`
- go to `https://download.docker.com/linux/ubuntu/dists`
- traverse directory for `{codename}/pool/stable/{arch}`
- download `containerd.io`, `docker-ce-cli` and `docker-ce.`

### Install package

```shell
sudo dpkg -i /path/to/package.deb
```

### Configure mirrors(optional)
Open `/etc/docker/daemon.json` and paste following content
```json
{
  "registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"]
}
```
Type commands to apply changes. **Note**: the second command will stop all running containers and not restart any containers.

```shell
systemctl daemon-reload
systemctl restart docker  # It will stop all running containers and not restart any containers.
```

### Permissons on /var/run/docker.sock

One may run `docker` commands without `sudo` and have the following problem

```
docker: Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Post http://%2Fvar%2Frun%2Fdocker.sock/v1.40/containers/create: dial unix /var/run/docker.sock: connect: permission denied.
```

Here gives the [solution](https://stackoverflow.com/a/48957722/8706476).

If it displays `groupadd: group 'docker' already exists`, simply adding access rights will solve.

```shell
sudo chmod 666 /var/run/docker.sock
```

### Usages

- pull images from repository `docker pull <name:tag>`
- list images in local storage `docker images`
- start a container with given image in background with ports mapped `docker run -itd -p 8080:80 <image:tag>`
- enter a container and interact with bash `docker exec -it <container-id> bash`
- stop a container `docker stop <container-id>`
- clean all stopped containers `docker containers prune`
