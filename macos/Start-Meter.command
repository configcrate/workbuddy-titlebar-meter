#!/bin/zsh
set -eu
APP="${0:A:h}/WorkBuddy Titlebar Meter.app"
if [[ ! -x "$APP/Contents/MacOS/meter" ]]; then
  print -u2 "未找到积分条程序：$APP"
  exit 1
fi
"$APP/Contents/MacOS/meter" --variant cn >/dev/null 2>&1 &!
"$APP/Contents/MacOS/meter" --variant ai >/dev/null 2>&1 &!
print "已启动国内版和国际版积分条。积分条在标题栏按钮左侧；切换到其他软件时仍会显示。右键积分条可设置自启、改为仅前台显示或退出。"
