@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-Loader.ps1"
if errorlevel 1 echo Preparation failed. Read the error above; no game files were changed.
pause
