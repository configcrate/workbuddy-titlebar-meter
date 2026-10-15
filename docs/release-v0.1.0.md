# WorkBuddy Titlebar Meter v0.1.0

首次 Windows 发布：在 WorkBuddy 标题栏直接查看剩余积分，自动跟随主窗口。

- 一次启动，当前用户登录自启；关闭 WorkBuddy 后隐藏等待，下次打开恢复。
- 紧凑进度条、低积分颜色警示、失败与过期提示、悬停详情。
- 避开菜单和窗口按钮，不全局置顶，排除宠物／浏览器窗口。
- 中英文文档；当前界面仅中文。

**下载须知：Windows Python 便携包，需要 Python 3.10+（包含 Tcl/Tk），不是独立 EXE。** 不需要额外安装 Node.js；需已安装并登录 WorkBuddy。解压到固定可写目录，双击 Start-Meter.bat。

Mac 尚未实现，本次不包含 Mac 包。国际版账号、企业账号及浅色主题未完成验证／适配。

隐私：取数会在内存中读取本机登录令牌，仅向官方计费接口认证；令牌不写入缓存。非公开接口可能随客户端更新失效。

English: First Windows release. Python 3.10+ with Tcl/Tk and an installed, signed-in WorkBuddy are required. This is not a standalone EXE and has no macOS support. Extract into a permanent writable folder and run Start-Meter.bat. Credentials are accessed in memory for official billing requests only; no tokens are included in the release.

Built by [ConfigCrate](https://configcrate.com/).
