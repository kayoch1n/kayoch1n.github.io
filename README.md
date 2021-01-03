# README

## Requirements

```shell
sudo apt-get install ruby
# 检查 ruby 版本
ruby -v
# 添加 TUNA 源并移除默认源
gem sources --add https://mirrors.tuna.tsinghua.edu.cn/rubygems/ --remove https://rubygems.org/
# 列出已有源, 应该只有 TUNA 一个
gem sources -l

# For ubuntu 18
sudo apt-get install ruby2.5-dev
sudo gem install jekyll bundler
```

## Build

```shell
# install missing gems.
bundle install
# build and serve
bundle exec jekyll serve -H 0.0.0.0 -P 5000
```