# README

## Requirements

ruby:

```bash
# 先装上 rvm
curl -sSL https://get.rvm.io | bash -s stable
# 编辑 ~/.bashrc
# 注意是追加，不是覆盖
echo 'source /etc/profile.d/rvm.sh' >> ~/.bashrc
# 安装 ruby 3.1.0 
rvm install 3.1.3
# 设置当前 ruby 版本
rvm use 3.1.3
# 看下目前的 ruby 版本是不是新的
ruby -v
# 看下目前的 gem 用的是哪个
which gem
```

jekyll:

```bash
# 添加 TUNA 源并移除默认源
gem sources --add https://mirrors.tuna.tsinghua.edu.cn/rubygems/ --remove https://rubygems.org/
# 列出已有源
gem sources -l
# 应该只有 TUNA 一个
# 安装 Jekyll 和 bundler
gem install jekyll bundler
```

Node.js:

```bash
# 安装nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# 安装 node
# 不过 18.16.1 需要 glibc 2.28
# 可以通过执行 /lib/x86_64-linux-gnu/libc.so.6 查看 glibc 版本
# nvm install 18.16.1
nvm install 16.15.1
node -v
# 速度慢的一批，还得配置镜像，用阿里巴巴的
npm config set registry https://registry.npmmirror.com
# Gruntfile.js 需要这个
npm install -g grunt-cli
npm install
# 生成静态资源
grunt 
```

## Build

```shell
bundle config mirror.https://rubygems.org https://mirrors.tuna.tsinghua.edu.cn/rubygems
# 如果不是全新创建一个repo的话。。。
bundle install
bundle exec jekyll serve
```