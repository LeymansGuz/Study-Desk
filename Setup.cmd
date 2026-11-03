@echo off
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-app.ps1" -Action setup
if errorlevel 1 echo Setup did not finish. Read the message above; your data has been kept.
pause
