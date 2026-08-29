@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "Centro_Monitoreo_Compensar.py"
) else (
  start "" pyw "Centro_Monitoreo_Compensar.py"
)
