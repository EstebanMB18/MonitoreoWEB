@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File scripts\06_procesar_local_09am.ps1
pause
