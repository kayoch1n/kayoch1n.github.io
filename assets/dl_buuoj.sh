#!/bin/bash

url=$1

if [[ -z $url ]]; then
  echo "[0益0] missing url" ;
  exit -1
fi

filename=`echo $url | awk -F'[/?]' '{print $(NF-1)}'`

wget $url -O $filename
echo $filename > current

file $filename
checksec $filename

gdb $filename
