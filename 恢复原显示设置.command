#!/bin/zsh
cd "${0:A:h}"
if ! python3 tools/sony-display.py restore "$@"; then
  printf '\n请输入电视无线调试主页的当前 IP:端口：'
  read tv_address
  if [[ -n "$tv_address" ]]; then
    python3 tools/sony-display.py restore --serial "$tv_address"
  fi
fi
printf '\n按回车关闭窗口。'
read
