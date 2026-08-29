$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT
$env:PYTHONPATH = $ROOT
.\venv\Scripts\python.exe -m src.main --modo guardar-sesion-payu
