# WorkBuddy Titlebar Meter

[中文](README.md) · English

Show your remaining WorkBuddy credits in its title bar, without opening the account menu.

![Illustration of titlebar placement, using fictional sample values](assets/titlebar-preview.svg)

**Windows only. The current UI is Chinese. macOS is not implemented.** The image is an illustration, not an account screenshot.

## Install

1. Download the Windows Python ZIP from [Releases](https://github.com/configcrate/workbuddy-titlebar-meter/releases/latest).
2. Extract it into a permanent, user-writable folder.
3. Install [Python 3.10+](https://www.python.org/downloads/windows/) with Tcl/Tk, and install and sign in to WorkBuddy.
4. Run **Start-Meter.bat** once. It registers per-user login startup and starts the companion; no administrator access is needed.

This is a Python portable package, **not a standalone EXE installer**. No separate Node.js installation is required: the helper uses WorkBuddy's Electron runtime. To choose a specific interpreter, set `WORKBUDDY_METER_PYTHON` to a pythonw.exe with tkinter.

Keep the folder in place. After moving it, rerun Start-Meter.bat to update the startup path.

## Behavior

- Compact, fixed titlebar placement; follows window movement, resizing and maximize/restore.
- Hides when minimized, inactive, on another virtual desktop, or too narrow to avoid covering controls.
- Recognizes the actual WorkBuddy.exe main window, not browser titles or pet/tool windows.
- When WorkBuddy closes, the meter hides and stops fetching. A hidden Python watcher remains to reconnect on reopening.
- Refreshes every five minutes by default; it is polling, not live push.
- Low-credit orange/red warnings; stale or failed reads are gray and explicitly labeled as previous data.
- Single instance; no separate taskbar button, tray dashboard, or global always-on-top card.

Drag the text area to move WorkBuddy; double-click it to maximize/restore. Click the color square to change theme. Hover for details; right-click for refresh, interval, startup and exit controls.

## Remove

Run **Uninstall-Autostart.bat** to remove this tool's login entry and stop it, without closing WorkBuddy. Then delete the extracted folder. `python meter.pyw --stop` exits the current instance without removing autostart.

## Privacy and limitations

The helper reads WorkBuddy's local session, obtains the local storage key through a client native binding, decrypts the existing token **in memory**, and authenticates to the official billing endpoint. It does access credentials in memory; it does not claim otherwise.

No tokens are saved in config, cache or logs. No telemetry or data is sent to ConfigCrate. No DLL injection, app file changes or copies of WorkBuddy.exe. Network requests use the selected official billing host, www.workbuddy.cn or www.workbuddy.ai. Display-only cache and config overwrite two small files instead of accumulating snapshots.

The native binding and billing API are unofficial integration points and may break after WorkBuddy updates.

Tested with WorkBuddy 5.8.2 China edition and 150% DPI. International account support is unverified; enterprise accounts and light titlebars are not supported. There is no macOS/Linux version. See [Mac handoff](docs/MAC_HANDOFF.md).

## Tests

```powershell
python -m unittest test_meter test_native_lifecycle -v
python meter.pyw --diagnose
```

25 tests; the native lifecycle test creates only its own temporary windows, uses no account credentials, and makes no billing calls. See [QA notes](docs/QA.md).

Independent third-party software, not affiliated with or endorsed by WorkBuddy. MIT License.

Built by [ConfigCrate](https://configcrate.com/).
