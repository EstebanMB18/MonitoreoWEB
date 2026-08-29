@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\07_ejecutar_dia_anterior.ps1"
pause
