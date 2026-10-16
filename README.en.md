# WorkBuddy Titlebar Meter

[中文](README.md) · English

Show your remaining WorkBuddy credits in its title bar, without opening the account menu.

![Illustration of titlebar placement, using fictional sample values](assets/titlebar-preview.svg)

**Windows: China and international editions. macOS: Apple Silicon, macOS 26+ test build. The UI is Chinese.** The image is an illustration, not an account screenshot.

## Install

1. Download the Windows Python ZIP from [Releases](https://github.com/configcrate/workbuddy-titlebar-meter/releases/latest).
2. Extract it into a permanent, user-writable folder.
3. Install [Python 3.10+](https://www.python.org/downloads/windows/) with Tcl/Tk, and install and sign in to WorkBuddy.
4. Run **Start-Meter.bat** once. It registers per-user login startup and starts the companion; no administrator access is needed.

This is a Python portable package, **not a standalone EXE installer**. No separate Node.js installation is required: the helper uses WorkBuddy's Electron runtime. To choose a specific interpreter, set `WORKBUDDY_METER_PYTHON` to a pythonw.exe with tkinter.

Keep the folder in place. After moving it, rerun Start-Meter.bat to update the startup path.

### macOS test build

Download `workbuddy-titlebar-meter-v0.2.0-macos-arm64.zip` from Releases and extract with macOS Archive Utility. Keep the `.app` beside `Start-Meter.command` in a permanent folder, then double-click the command file to start both regional companions. No Python is required. Login startup is opt-in, separately enabled in each meter's context menu; disable it before moving or deleting the folder.

This user-provided build was developed and tested on **Apple Silicon / macOS 26**, and requires **macOS 26 or later**. No Intel or older-macOS support is claimed. It is unsigned and not notarized. If macOS blocks it, review the source and decide whether to use it; do not disable system protections. Source: [macos](macos); build on a Mac with Xcode command-line tools using [build-macos.sh](scripts/build-macos.sh).

Unlike Windows, the Mac companion defaults to showing whenever the host window is on-screen; both editions can be visible at once. It is a floating overlay and can overlap other apps. Its menu offers a foreground-only mode. Spaces, full screen, Stage Manager, external displays and Retina still need broader testing. To remove it, disable each edition's login startup, quit both companions and delete the folder. See [Mac handoff](docs/MAC_HANDOFF.md).

## Windows behavior

- Compact, fixed titlebar placement; follows window movement, resizing and maximize/restore.
- Hides when minimized, inactive, on another virtual desktop, or too narrow to avoid covering controls.
- Recognizes WorkBuddy.exe (China) and WorkBuddyAI.exe (international), not browser titles or pet/tool windows.
- With both editions open, one meter follows the active client. Requests are forced to that edition, with separate tagged caches and stale-response guards.
- When WorkBuddy closes, the meter hides and stops fetching. A hidden Python watcher remains to reconnect on reopening.
- Refreshes every five minutes by default; it is polling, not live push.
- Low-credit orange/red warnings; stale or failed reads are gray and explicitly labeled as previous data.
- Single instance; no separate taskbar button, tray dashboard, or global always-on-top card.

Drag the text area to move WorkBuddy; double-click it to maximize/restore. Click the color square to change theme. Hover for details; right-click for refresh, interval, startup and exit controls.

## Windows removal and upgrade

Run **Uninstall-Autostart.bat** to remove this tool's login entry and stop it, without closing WorkBuddy. Then delete the extracted folder. `python meter.pyw --stop` exits the current instance without removing autostart.

To upgrade from v0.1.0: run `Start-Meter.bat --stop`, overwrite the application files with the new package, then run `Start-Meter.bat`. Keep your configuration. Untagged legacy snapshots are not reused; a fresh read is required.

## Privacy and limitations

The helper reads WorkBuddy's local session, obtains the local storage key through a client native binding, decrypts the existing token **in memory**, and authenticates to the official billing endpoint. It does access credentials in memory; it does not claim otherwise.

No tokens are saved in config, cache or logs. No telemetry or data is sent to ConfigCrate. No DLL injection, app file changes or copies of WorkBuddy.exe. Network requests use the selected official billing host, www.workbuddy.cn or www.workbuddy.ai. Windows overwrites one config and two regional caches (`meter_state_cn.json`, `meter_state_ai.json`) instead of accumulating snapshots; legacy `meter_state.json` is ignored. Mac keeps snapshots in memory and uses separate per-user LaunchAgents for opt-in login startup.

Windows login startup uses `ConfigCrate WorkBuddy Meter.lnk` in the current user's Startup folder, with explicit interpreter, arguments and working directory. Installation migrates this folder's old registry Run entry. Failed login launches retry every 10 seconds for up to two minutes; early errors overwrite one bounded `meter_error.log` rather than accumulating logs. Manual launches fail promptly instead of retrying.

The native binding and billing API are unofficial integration points and may break after WorkBuddy updates.

Windows client versions: WorkBuddy 5.8.2 China and WorkBuddy AI 5.7.6 international. Enterprise accounts and light titlebars are not supported. Mac screenshots and test notes were supplied by the user; the Mac package was not rebuilt or executed on this Windows machine. No Linux version.

## Tests

```powershell
python -m unittest test_meter test_native_lifecycle test_startup -v
node test_helper.cjs
python meter.pyw --diagnose
```

39 Python tests and 7 helper-routing assertions, including temporary Unicode shortcuts, startup migration safety and bounded login retries. The automated tests use no account credentials or billing calls; native lifecycle tests create only their own temporary windows. See [QA notes](docs/QA.md).

Independent third-party software, not affiliated with or endorsed by WorkBuddy. MIT License.

Initial macOS implementation and on-device testing: [Saiaaax](https://github.com/Saiaaax).

Built by [ConfigCrate](https://configcrate.com/).
