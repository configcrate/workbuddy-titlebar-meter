@echo off
setlocal
cd /d "%~dp0"
set "PYW="
if defined WORKBUDDY_METER_PYTHON call :try "%WORKBUDDY_METER_PYTHON%"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do call :try "%%~fD\pythonw.exe"
call :try "%USERPROFILE%\miniconda3\pythonw.exe"
call :try "%USERPROFILE%\anaconda3\pythonw.exe"
call :try "%ProgramData%\miniconda3\pythonw.exe"
call :try "%ProgramData%\anaconda3\pythonw.exe"
for /d %%D in ("C:\Python*") do call :try "%%~fD\pythonw.exe"
if not defined PYW (
  for /f "delims=" %%P in ('where pythonw 2^>nul') do call :try "%%P"
)
if not defined PYW (
  for /f "delims=" %%P in ('py -3 -c "import sys,pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))" 2^>nul') do call :try "%%P"
)
if not defined PYW (
  echo No Python 3.10+ with tkinter found.
  echo Install Python from https://www.python.org/downloads/windows/
  echo Include Tcl/Tk, then run Start-Meter.bat again.
  pause
  exit /b 1
)
set "MODE=--install"
if /i "%~1"=="--uninstall" set "MODE=--uninstall"
if /i "%~1"=="--stop" set "MODE=--stop"
start "" /B "%PYW%" "%~dp0meter.pyw" %MODE%
exit /b 0

:try
if defined PYW exit /b
if "%~1"=="" exit /b
if exist "%~1" (
  "%~1" -c "import sys,tkinter; assert sys.version_info >= (3,10)" >nul 2>nul
  if not errorlevel 1 set "PYW=%~1"
)
exit /b
