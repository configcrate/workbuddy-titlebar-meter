"""Per-user Startup shortcut; no elevation, scheduled task or client changes."""
import json
import os
import subprocess

DESCRIPTION = "ConfigCrate WorkBuddy Titlebar Meter"


def shortcut_path():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", "ConfigCrate WorkBuddy Meter.lnk")


def _shell_link(path, target="", arguments="", directory="", write=False):
    # Paths are passed as environment data, never interpolated into PowerShell code.
    command = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:WB_LINK_PATH)
if ($env:WB_LINK_WRITE -eq '1') {
    $link.TargetPath = $env:WB_LINK_TARGET
    $link.Arguments = $env:WB_LINK_ARGS
    $link.WorkingDirectory = $env:WB_LINK_DIRECTORY
    $link.Description = 'ConfigCrate WorkBuddy Titlebar Meter'
    $link.WindowStyle = 7
    $link.Save()
}
@{target=$link.TargetPath; arguments=$link.Arguments; directory=$link.WorkingDirectory;
  description=$link.Description} | ConvertTo-Json -Compress
'''
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                             "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    env = dict(os.environ, WB_LINK_PATH=path, WB_LINK_TARGET=target,
               WB_LINK_ARGS=arguments, WB_LINK_DIRECTORY=directory, WB_LINK_WRITE="1" if write else "0")
    result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                            env=env, capture_output=True, timeout=20, creationflags=0x08000000)
    if result.returncode:
        raise OSError("Could not configure the per-user Startup shortcut")
    return json.loads(result.stdout.decode("utf-8-sig"))


def details():
    path = shortcut_path()
    if not os.path.isfile(path):
        return None
    try:
        return _shell_link(path)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def arguments(script):
    return subprocess.list2cmdline([os.path.abspath(script), "--autostart"])


def matches(info, executable, script):
    return bool(info and info.get("description") == DESCRIPTION
                and os.path.normcase(info.get("target", "")) == os.path.normcase(os.path.abspath(executable))
                and info.get("arguments") == arguments(script)
                and os.path.normcase(info.get("directory", "")) == os.path.normcase(os.path.dirname(os.path.abspath(script))))


def install(executable, script):
    path = shortcut_path()
    if os.path.exists(path):
        info = details()
        if not info or info.get("description") != DESCRIPTION:
            raise OSError("Startup shortcut exists but is not owned by this tool")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    info = _shell_link(path, os.path.abspath(executable), arguments(script),
                       os.path.dirname(os.path.abspath(script)), write=True)
    if not matches(info, executable, script):
        raise OSError("Startup shortcut verification failed")


def remove(executable, script):
    if matches(details(), executable, script):
        os.remove(shortcut_path())
