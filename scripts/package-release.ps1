param([string]$Version = '0.2.0')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Expected a numeric semantic version.' }
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$name = "workbuddy-titlebar-meter-v$Version-windows-python.zip"
$zip = Join-Path $dist $name
$files = @('meter.pyw','titlebar_meter.py','window_anchor.py','meter_core.py','wb_credits_helper.cjs',
           'Start-Meter.bat','Install-Autostart.bat','Uninstall-Autostart.bat','README.md','README.en.md','LICENSE')
$paths = @($files | ForEach-Object { Join-Path $root $_ })
$paths += Join-Path $root 'assets'
$paths += Join-Path $root 'docs'
Compress-Archive -LiteralPath $paths -DestinationPath $zip -Force
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $name" | Set-Content -LiteralPath "$zip.sha256" -Encoding ascii
Write-Output $zip
Write-Output "$zip.sha256"
