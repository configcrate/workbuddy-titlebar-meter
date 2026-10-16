# v0.2.1 — Windows 登录自启修复 / Windows login startup fix

## 中文

- Windows 自启改用当前用户“启动”文件夹快捷方式，明确指定 Python、脚本参数和工作目录；核验成功后清理本目录对应的旧注册表自启项，避免重复启动。
- 登录时遇到启动异常，最多每 10 秒重试一次、共 2 分钟；手动启动失败不等待。补充早期导入错误记录，日志覆盖同一个小文件，不会持续堆积。
- 异常退出释放单实例锁，允许后续重试正常启动。
- 使用原生 Unicode 快捷方式接口，兼容英文 Windows 上的中文路径，不依赖 PowerShell 创建快捷方式。
- 保留国内／国际版识别、积分缓存隔离、颜色及刷新设置，不修改 WorkBuddy 客户端。

### Windows 下载与升级

下载 `workbuddy-titlebar-meter-v0.2.1-windows-python.zip`，仍需 Python 3.10+（含 tkinter）。老用户先运行 `Start-Meter.bat --stop`，覆盖新版文件，保留自己的 `meter_config.json`，再运行 `Start-Meter.bat`，即可安装新自启入口并启动。无需管理员权限。

本地 39 项 Python 测试和 7 项助手路由断言通过；实际启动快捷方式已验证。用户反馈关闭重新打开后正常显示；没有以自动测试或该反馈代替完整重启登录验证。

**Mac 本次没有修改。** 为方便下载，此页沿用 v0.2.0 原始 Mac ZIP 及校验文件，文件名和内容保持不变：仅 Apple Silicon、macOS 26+ 测试版，未签名／未公证，Mac 用户无需因本次 Windows 修复升级。

## English

- Use a per-user Startup shortcut with explicit interpreter, arguments and working directory. Migrate this installation's old Run entry only after verifying the new shortcut.
- Retry failed login launches every 10 seconds for up to two minutes; manual launches fail promptly. Record early startup errors in one bounded, overwritten log.
- Release the single-instance lock after startup failure so retries can succeed. Existing regional routing and personal settings are preserved.
- Use native Unicode shortcut interfaces for Chinese paths on English Windows, without PowerShell-based shortcut creation.

**Upgrade on Windows:** stop the meter with `Start-Meter.bat --stop`, overwrite application files, keep your personal configuration, then run `Start-Meter.bat` again. Python 3.10+ with tkinter remains required. No administrator privileges needed.

39 Python tests and 7 helper-routing assertions passed locally. The real Startup shortcut was exercised, and the user confirmed visibility after closing/reopening; a complete OS restart/login was not independently verified.

**Mac is unchanged.** The original v0.2.0 Mac ZIP and checksum are reattached under their original names: Apple Silicon / macOS 26+ test build, unsigned and not notarized.

Built by [ConfigCrate](https://configcrate.com/). MIT License.
