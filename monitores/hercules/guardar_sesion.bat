@echo off
cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python ".\src\guardar_sesion.py"
pause
