# WorkBuddy Titlebar Meter

[中文](#中文说明) · [English](README.en.md)

![标题栏位置示意图，使用虚构示例数值](assets/titlebar-preview.svg)

## 中文说明

直接在 WorkBuddy 标题栏看剩余积分，不用再打开账户菜单。使用方式与 [Codex Titlebar Meter](https://github.com/configcrate/codex-titlebar-meter) 相同：一次启动，随后自动跟随主窗口。

**目前仅支持 Windows，界面为中文。Mac 版尚未实现。** 上图是位置示意，不是实际账号截图。

## 下载与安装

1. 在 [Releases](https://github.com/configcrate/workbuddy-titlebar-meter/releases/latest) 下载 `workbuddy-titlebar-meter-v0.1.0-windows-python.zip`。
2. 解压到一个固定、当前用户可写的文件夹。
3. 确保安装了 [Python 3.10+](https://www.python.org/downloads/windows/)（包含 Tcl/Tk），并已安装、登录 WorkBuddy。
4. 双击 **Start-Meter.bat**，自动注册当前用户登录自启并开始运行，无需管理员权限。

这版是 Python 便携包，**不是免 Python 的独立 EXE 安装包**。不需要另装 Node.js，取数使用 WorkBuddy 自带的 Electron 运行时。

安装后不要移动文件夹；移动后重新运行 Start-Meter.bat 更新自启路径。若需要指定 Python，可设置 `WORKBUDDY_METER_PYTHON` 为带 tkinter 的 pythonw.exe 完整路径。

## 自动跟随

- 固定在主窗口标题栏右侧空白区域，不是独立桌面卡片。
- 随移动、缩放、最大化／还原更新位置，支持高 DPI 和负坐标显示器。
- 最小化、切换其他软件或虚拟桌面时隐藏，不全局置顶。
- 关闭 WorkBuddy 后隐藏并停止取数；保留一个隐藏的 Python 等待进程，下次打开自动恢复。
- 按实际 WorkBuddy.exe 进程和窗口类型识别，排除宠物、小窗口和浏览器页面。
- 默认每 5 分钟刷新；这是定时读取，不是实时推送。
- 标题栏太窄时自动隐藏，不盖住菜单或最小化／关闭按钮。
- 重复启动不会叠出多条积分条。

## 操作

| 操作 | 效果 |
|---|---|
| 拖动文字区域 | 移动 WorkBuddy 主窗口 |
| 双击文字区域 | 最大化／还原主窗口 |
| 点击右侧色块 | 切换绿色、蓝色、紫色 |
| 悬停 | 查看完整积分、总额度、套餐和更新时间 |
| 右键 | 刷新、详情、刷新间隔、自启开关、退出 |

剩余不超过 20% 时变橙色，不超过 10% 时变红色。读取失败或数据过期时变灰，明确标注“上次／待更新”，不假装是最新数据；没有总额度时不伪造百分比。

## 卸载

双击 **Uninstall-Autostart.bat**，删除本工具的自启项并停止运行，不关闭 WorkBuddy。随后可以删除解压的文件夹。单独运行 `python meter.pyw --stop` 只退出本次运行，不删除自启设置。

## 隐私与原理

取数助手只读本机 WorkBuddy 登录态，调用客户端自带的原生绑定获得本机存储密钥，在内存中解密现有令牌，再向 WorkBuddy 官方计费接口认证并读取积分。

**它会在内存中读取登录令牌**，不能宣称“不读凭据”。不要求粘贴 Cookie 或 API Key，不把令牌落盘，不注入 DLL，不修改客户端文件，不复制 WorkBuddy.exe；没有遥测，不向 ConfigCrate 发送账号或积分。

- 仅访问已选择版本的官方计费域名 `www.workbuddy.cn` 或 `www.workbuddy.ai`。
- 配置和缓存分别覆盖 `meter_config.json`、`meter_state.json`，不会按刷新次数新增文件。
- 缓存只存积分、总额度、百分比、套餐及更新时间，不保存 uid、昵称或令牌。
- 异常日志覆盖同一个有大小上限的文件。
- 当前用户自启项：`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\WorkBuddyCredits`。

此方式依赖非公开客户端绑定和计费接口，WorkBuddy 更新可能导致失效。欢迎阅读源代码后再决定是否使用。

## 支持范围

- Windows 10/11，Python 3.10+（带 tkinter）。
- 已在 WorkBuddy 5.8.2 国内版、150% DPI 上验证真实取数和标题栏显示。
- 当前为深色标题栏、中文界面。国际版仅保留原取数分支，尚未进行真实账号验证；企业账号暂未适配。
- **不支持 macOS／Linux。** Mac 需要另写窗口吸附、自启、取数适配并在真实 Mac 上验证，不能直接运行这份 Windows 包。

## 开发与验证

```powershell
python -m unittest test_meter test_native_lifecycle -v
python meter.pyw --diagnose
```

25 项测试覆盖布局、数据校验、隐私缓存、生命周期和独立原生测试窗口。测试不使用你的登录态、不调用计费接口，不关闭正在工作的 WorkBuddy。[验证记录](docs/QA.md) · [Mac 测试交接](docs/MAC_HANDOFF.md)

独立第三方工具，与 WorkBuddy 官方无关，未获官方授权。MIT License。

Built by [ConfigCrate](https://configcrate.com/).
