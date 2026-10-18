#!/bin/zsh
cd "${0:A:h}"
if ! python3 tools/sony-device.py restore-home "$@"; then
  printf '\n若无线调试端口已经变化，请输入电视无线调试主页的 IP:端口：'
  read tv_address
  if [[ -n "$tv_address" ]]; then
    python3 tools/sony-device.py restore-home --serial "$tv_address"
  fi
fi
printf '\n按回车关闭窗口。'
read
