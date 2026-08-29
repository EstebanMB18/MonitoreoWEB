@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File scripts\12_ejecutar_solo_payu_09am.ps1
pause
