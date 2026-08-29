@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\04_ejecutar_web_09am.ps1"
pause
