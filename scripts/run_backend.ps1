$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "No se encontró el Python de Nexus: $Python"
}

Write-Host "NEXUS BACKEND" -ForegroundColor Cyan
Write-Host "Python: $Python"

& $Python -m uvicorn api.app:app `
    --host 127.0.0.1 `
    --port 8000
