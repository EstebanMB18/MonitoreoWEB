param(
    [string]$TaskName = "MonitoreoWEB - Cierre Diario",
    [string]$Time = "00:20"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_daily_closure.ps1"

if (-not (Test-Path $runner)) {
    throw "No existe runner: $runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument (
        "-NoProfile " +
        "-ExecutionPolicy Bypass " +
        "-File `"$runner`" " +
        "-ProjectRoot `"$projectRoot`""
    )

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $Time

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description (
        "Centro de Monitoreo V2 - " +
        "cierre historico diario y catch-up."
    ) `
    -Force

Write-Host ""
Write-Host "TAREA INSTALADA" -ForegroundColor Green
Write-Host "Nombre: $TaskName"
Write-Host "Hora:   $Time"
Write-Host "Runner: $runner"
