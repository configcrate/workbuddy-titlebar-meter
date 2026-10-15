# v0.2.0 — Windows 国际版支持与 macOS 26+ 测试包

直接在 WorkBuddy 标题栏查看剩余积分，无需反复打开账号菜单。

## 中文

- **修复 Windows 国际版不显示**：识别 WorkBuddy AI 主窗口，自动跟随当前激活的国内／国际客户端。
- **避免串积分**：按宿主版本读取对应登录态和官方接口；两版独立缓存，切换时不沿用另一版数据，旧请求返回也不会覆盖新版本。
- 保留颜色、刷新间隔、登录自启和一键退出，不修改 WorkBuddy 原文件。
- 集成 **macOS / Apple Silicon / macOS 26+ 测试版**，支持国内、国际两个客户端；附 Swift 源码与构建脚本。
- 更新中英文安装、升级、卸载、隐私及验证说明。

### 下载哪个？

- Windows：`workbuddy-titlebar-meter-v0.2.0-windows-python.zip`。需要 Python 3.10+（含 tkinter）；解压后双击 `Start-Meter.bat`，会注册当前用户登录自启。
- Mac：`workbuddy-titlebar-meter-v0.2.0-macos-arm64.zip`。**仅 Apple Silicon、macOS 26 及以上**；解压后保持 `.app` 与 `Start-Meter.command` 相邻，双击后者。无需 Python，登录自启在积分条右键菜单中手动启用。
- `.sha256` 是校验文件，不是安装包。

Windows 老用户：先运行 `Start-Meter.bat --stop`，覆盖新版文件，保留个人配置，再运行 `Start-Meter.bat`。旧缓存首次不显示，将重新取数。

### 验证与限制

Windows 国内版 5.8.2 与国际版 5.7.6 真实取数和显示均通过；32 项 Python 测试与 7 项助手路由断言通过。Mac 包为用户在 Mac 上开发并确认显示的原始测试包，本次未在 Windows 上重新编译或运行。

Mac 包未签名、未公证，不支持 Intel 或更旧 macOS；Spaces、全屏、Stage Manager、外接屏和 Retina 仍需更多实测。默认在宿主窗口在屏时显示，可右键改为仅前台；其浮层可能覆盖其他应用，与 Windows 行为不同。

两平台界面目前均为中文。使用本机登录令牌在内存中请求对应 WorkBuddy 官方计费接口，不要求 API Key，不上传账号到 ConfigCrate，不修改客户端文件。非官方集成可能随客户端更新失效。

## English

- Fix Windows international-client discovery (`WorkBuddyAI.exe`). One meter follows the active China/international client.
- Route requests by host executable, isolate regional caches and reject mismatched or delayed responses. Untagged legacy caches are ignored.
- Add user-provided **Apple Silicon / macOS 26+ test build**, Swift source and build script, with bilingual documentation.

**Windows:** download the `windows-python.zip`, install Python 3.10+ with tkinter, then run `Start-Meter.bat`. Existing users: stop the meter first, overwrite application files, keep personal config, then restart it.

**Mac:** download the `macos-arm64.zip`, extract it and run `Start-Meter.command` beside the `.app`. No Python needed. Login startup is opt-in from each meter's menu. Unsigned and not notarized; no Intel or pre-macOS-26 support. Advanced window/display scenarios need more testing. The original user-provided Mac ZIP is published without rebuilding it on Windows.

Both Windows editions were checked with real accounts; 32 Python tests and 7 helper routing assertions passed locally. The UI is currently Chinese. This independent third-party tool uses local credentials in memory to call the matching official billing endpoint; no telemetry or client-file modifications.

Built by [ConfigCrate](https://configcrate.com/). MIT License.
