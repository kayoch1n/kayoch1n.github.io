---
layout: post
title:  "Ubuntu从deb包安装docker"
date:   2020-03-24 21:15:38 +0800
---
## Docker on Ubuntu
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

### Usages

- pull images from repository `docker pull <name:tag>`
- list images in local storage `docker images`
- start a container with given image in background with ports mapped `docker run -itd -p 8080:80 <image:tag>`
- enter a container and interact with bash `docker exec -it <container-id> bash`
- stop a container `docker stop <container-id>`
- clean all stopped containers `docker containers prune`
