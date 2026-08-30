param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "runtime\logs\daily-closure"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $logDir |
Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "daily_closure_$stamp.log"

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
}
else {
    $python = "python"
}

$script = Join-Path $ProjectRoot "scripts\daily_closure.py"

try {
    "===== DAILY CLOSURE START =====" |
        Out-File `
            -FilePath $logFile `
            -Encoding utf8

    "PROJECT=$ProjectRoot" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    "PYTHON=$python" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    "START=$(Get-Date -Format o)" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    & $python `
        $script `
        --catch-up `
        --json `
        2>&1 |
        Tee-Object `
            -FilePath $logFile `
            -Append

    $exitCode = $LASTEXITCODE

    "EXIT_CODE=$exitCode" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    "END=$(Get-Date -Format o)" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    if ($exitCode -ne 0) {
        exit $exitCode
    }

    exit 0
}
catch {
    "ERROR=$($_.Exception.Message)" |
        Out-File `
            -FilePath $logFile `
            -Append `
            -Encoding utf8

    exit 1
}
