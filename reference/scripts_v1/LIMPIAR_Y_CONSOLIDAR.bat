@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "from core.orchestrator import finalize; print(finalize())"
) else (
  py -3.12 -c "from core.orchestrator import finalize; print(finalize())"
)
pause
