@echo off
rem Remove our login entry and stop only the credit meter, not WorkBuddy.
call "%~dp0Start-Meter.bat" --uninstall
