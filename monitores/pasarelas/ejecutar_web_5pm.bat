@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\05_ejecutar_web_5pm.ps1"
pause
