# WorkBuddy Titlebar Meter

[中文](#中文说明) · [English](README.en.md)

![标题栏位置示意图，使用虚构示例数值](assets/titlebar-preview.svg)

## 中文说明

直接在 WorkBuddy 标题栏看剩余积分，不用再打开账户菜单。使用方式与 [Codex Titlebar Meter](https://github.com/configcrate/codex-titlebar-meter) 相同：一次启动，随后自动跟随主窗口。

**Windows 支持国内版及国际版；另提供 Apple Silicon、macOS 26+ 测试包。界面为中文。** 上图是位置示意，不是实际账号截图。

## 下载与安装

1. 在 [Releases](https://github.com/configcrate/workbuddy-titlebar-meter/releases/latest) 下载 `workbuddy-titlebar-meter-v0.2.0-windows-python.zip`。
2. 解压到一个固定、当前用户可写的文件夹。
3. 确保安装了 [Python 3.10+](https://www.python.org/downloads/windows/)（包含 Tcl/Tk），并已安装、登录 WorkBuddy。
4. 双击 **Start-Meter.bat**，自动注册当前用户登录自启并开始运行，无需管理员权限。

这版是 Python 便携包，**不是免 Python 的独立 EXE 安装包**。不需要另装 Node.js，取数使用 WorkBuddy 自带的 Electron 运行时。

安装后不要移动文件夹；移动后重新运行 Start-Meter.bat 更新自启路径。若需要指定 Python，可设置 `WORKBUDDY_METER_PYTHON` 为带 tkinter 的 pythonw.exe 完整路径。

### macOS 测试包

1. 下载 `workbuddy-titlebar-meter-v0.2.0-macos-arm64.zip`，用 macOS 自带解压工具解压。
2. 把整个文件夹放到固定位置，保持 `.app` 与 `Start-Meter.command` 在一起；双击 **Start-Meter.command**，分别启动国内版、国际版积分条。无需安装 Python。
3. 需要登录自启时，在对应积分条右键菜单中启用；首次启动**不会自动注册**。移位置前先关闭自启，移动后再启用。

这是用户在 **macOS 26 / Apple Silicon** 开发并测试的未签名、未公证版本，二进制最低系统为 **macOS 26**；不支持 Intel 或更旧系统。系统若阻止启动，请自行审查源码并决定是否运行，不要关闭系统安全保护。源码位于 [macos](macos)，构建脚本为 [build-macos.sh](scripts/build-macos.sh)（需要 Mac 与 Xcode 命令行工具）。

Mac 默认在宿主窗口在屏时显示，两版可同时显示；右键可改为“仅前台显示”。这是独立浮层，可能覆盖其他应用，和 Windows 的前台隐藏行为不同。Spaces、全屏、Stage Manager、外接屏和 Retina 等场景尚未完成全面验证。Mac 卸载时，分别关闭两版积分条的登录自启并退出，再删除解压目录。详见 [Mac 验证交接](docs/MAC_HANDOFF.md)。

## Windows 自动跟随

- 固定在主窗口标题栏右侧空白区域，不是独立桌面卡片。
- 随移动、缩放、最大化／还原更新位置，支持高 DPI 和负坐标显示器。
- 最小化、切换其他软件或虚拟桌面时隐藏，不全局置顶。
- 关闭 WorkBuddy 后隐藏并停止取数；保留一个隐藏的 Python 等待进程，下次打开自动恢复。
- 按实际 WorkBuddy.exe（国内）或 WorkBuddyAI.exe（国际）进程和窗口类型识别，排除宠物、小窗口和浏览器页面。
- 同时打开两版时，一条积分条跟随当前激活的客户端，强制读取该版本的账户，分区缓存，不会因另一版已登录而串积分。
- 默认每 5 分钟刷新；这是定时读取，不是实时推送。
- 标题栏太窄时自动隐藏，不盖住菜单或最小化／关闭按钮。
- 重复启动不会叠出多条积分条。

## Windows 操作

| 操作 | 效果 |
|---|---|
| 拖动文字区域 | 移动 WorkBuddy 主窗口 |
| 双击文字区域 | 最大化／还原主窗口 |
| 点击右侧色块 | 切换绿色、蓝色、紫色 |
| 悬停 | 查看完整积分、总额度、套餐和更新时间 |
| 右键 | 刷新、详情、刷新间隔、自启开关、退出 |

剩余不超过 20% 时变橙色，不超过 10% 时变红色。读取失败或数据过期时变灰，明确标注“上次／待更新”，不假装是最新数据；没有总额度时不伪造百分比。

## Windows 卸载与升级

双击 **Uninstall-Autostart.bat**，删除本工具的自启项并停止运行，不关闭 WorkBuddy。随后可以删除解压的文件夹。单独运行 `python meter.pyw --stop` 只退出本次运行，不删除自启设置。

从 v0.1.0 升级：先运行 `Start-Meter.bat --stop`，将新版文件覆盖到原文件夹，再运行 `Start-Meter.bat`。保留个人配置；旧的无版本标记缓存不会直接显示，首次使用将重新取数。

## 隐私与原理

取数助手只读本机 WorkBuddy 登录态，调用客户端自带的原生绑定获得本机存储密钥，在内存中解密现有令牌，再向 WorkBuddy 官方计费接口认证并读取积分。

**它会在内存中读取登录令牌**，不能宣称“不读凭据”。不要求粘贴 Cookie 或 API Key，不把令牌落盘，不注入 DLL，不修改客户端文件，不复制 WorkBuddy.exe；没有遥测，不向 ConfigCrate 发送账号或积分。

- 仅访问已选择版本的官方计费域名 `www.workbuddy.cn` 或 `www.workbuddy.ai`。
- Windows 配置覆盖 `meter_config.json`；国内／国际缓存分别覆盖 `meter_state_cn.json`、`meter_state_ai.json`，不会按刷新次数新增文件。旧 `meter_state.json` 不再读取，可自行删除。
- 缓存只存积分、总额度、百分比、套餐及更新时间，不保存 uid、昵称或令牌。
- 异常日志覆盖同一个有大小上限的文件。
- Windows 当前用户自启项：`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\WorkBuddyCredits`。Mac 使用各版本独立的当前用户 LaunchAgent；积分快照只留在内存。

此方式依赖非公开客户端绑定和计费接口，WorkBuddy 更新可能导致失效。欢迎阅读源代码后再决定是否使用。

## 支持范围

- Windows 10/11，Python 3.10+（带 tkinter）。
- Windows：WorkBuddy 5.8.2 国内版与 WorkBuddy AI 5.7.6 国际版；深色标题栏、中文界面。企业账号暂未适配。
- macOS：Apple Silicon、macOS 26+ 测试版，用户提供两版本的真实显示截图；本次 Windows 环境未重编译或运行 Mac 包。
- 不支持 Linux。Mac 包不是 Windows 包的直接移植，两平台的行为和安装方式有区别。

## 开发与验证

```powershell
python -m unittest test_meter test_native_lifecycle -v
node test_helper.cjs
python meter.pyw --diagnose
```

32 项 Python 测试与 7 项助手路由断言覆盖布局、数据校验、区域隔离、迟到响应、隐私缓存、生命周期和独立原生测试窗口。自动测试不使用你的登录态、不调用计费接口，不关闭正在工作的 WorkBuddy。[验证记录](docs/QA.md) · [Mac 测试交接](docs/MAC_HANDOFF.md)

独立第三方工具，与 WorkBuddy 官方无关，未获官方授权。MIT License。

macOS 初版开发与实机测试：[Saiaaax](https://github.com/Saiaaax)。

Built by [ConfigCrate](https://configcrate.com/).
