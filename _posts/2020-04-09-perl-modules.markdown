---
layout: post
title:  "ubuntu安装Perl模块"
date:   2020-04-09 23:15:38 +0800
---

# Install perl modules on Ubuntu

## Installation

Follow the steps [here](http://www.cpan.org/modules/INSTALL.html) to install perl modules.

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