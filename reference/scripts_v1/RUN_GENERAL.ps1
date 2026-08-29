# SPRINT_13_8_AUTO_REV2_TIMEOUT30_POLL30_OK
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("09","13","17")]
    [string]$Corte
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { $Python = "py" }
Set-Location $Root

function Get-OutputRoot {
    $cfg = Get-Content (Join-Path $Root "config\app.json") -Raw | ConvertFrom-Json
    return [Environment]::ExpandEnvironmentVariables($cfg.output_root)
}

$runId = "$(Get-Date -Format 'yyyyMMdd')_corte_$Corte"
$stateDir = Join-Path (Get-OutputRoot) "GENERAL\state\automaticas\$runId"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$required = @("PASARELAS","AWS","HERCULES")
$waitMinutes = 30
if ($env:GENERAL_WAIT_MINUTES) {
    [int]::TryParse($env:GENERAL_WAIT_MINUTES, [ref]$waitMinutes) | Out-Null
}

$deadline = (Get-Date).AddMinutes($waitMinutes)

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " GENERAL AUTOMATICO - $runId" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Esta tarea NO ejecuta ni vuelve a publicar monitores."
Write-Host "Solo espera los estados del mismo corte y consolida GENERAL."
Write-Host ""

$lastSignature = ""
$lastReminder = Get-Date "2000-01-01"

while ((Get-Date) -lt $deadline) {
    $missing = @()

    foreach ($m in $required) {
        $p = Join-Path $stateDir "$m.json"
        if (-not (Test-Path $p)) {
            $missing += $m
        }
    }

    if ($missing.Count -eq 0) {
        break
    }

    $signature = ($missing -join ",")
    $now = Get-Date

    # Log solo si cambia el conjunto pendiente o cada 5 minutos.
    if ($signature -ne $lastSignature -or (($now - $lastReminder).TotalMinutes -ge 5)) {
        Write-Host ("GENERAL esperando: " + ($missing -join ", ")) -ForegroundColor Yellow
        $lastSignature = $signature
        $lastReminder = $now
    }

    Start-Sleep -Seconds 30
}

$states = @{}
foreach ($m in $required) {
    $p = Join-Path $stateDir "$m.json"

    if (Test-Path $p) {
        try {
            $states[$m] = Get-Content $p -Raw | ConvertFrom-Json
        }
        catch {
            $states[$m] = $null
        }
    }
    else {
        $states[$m] = $null
    }
}

Write-Host ""
Write-Host "Estado del corte:" -ForegroundColor Cyan
foreach ($m in $required) {
    $s = $states[$m]
    if ($null -eq $s) {
        Write-Host "  $m -> NO FINALIZADO / TIMEOUT" -ForegroundColor Red
    }
    elseif ($s.estado -eq "OK" -and $s.fuente_actual) {
        Write-Host "  $m -> OK · fuente actual" -ForegroundColor Green
    }
    else {
        Write-Host "  $m -> $($s.estado) · fuente_actual=$($s.fuente_actual)" -ForegroundColor Red
    }
}

# El fresh-after del corte coincide con el inicio de Verticales: 20 minutos antes.
# Rechaza sin ambigüedad archivos del corte anterior/día anterior.
$today = Get-Date
$hour = [int]$Corte
$cutoff = Get-Date -Year $today.Year -Month $today.Month -Day $today.Day -Hour $hour -Minute 0 -Second 0
$freshAfter = $cutoff.AddMinutes(-20).ToString("o")

Write-Host ""
Write-Host "Generando SOLO Dashboard General..." -ForegroundColor Cyan
Write-Host "Fresh-after: $freshAfter"

$argsRun = @(
    "$Root\run.py",
    "--finalize-only",
    "--corte", $Corte,
    "--fresh-after", $freshAfter,
    "--selected", "PASARELAS,AWS,HERCULES"
)

if ($Python -eq "py") {
    & py -3.12 @argsRun
    $rc = $LASTEXITCODE
}
else {
    & $Python @argsRun
    $rc = $LASTEXITCODE
}

$summary = [ordered]@{
    run_id = $runId
    corte = $Corte
    generado = (Get-Date).ToString("o")
    fresh_after = $freshAfter
    general_rc = $rc
    monitores = $states
}

$target = Join-Path $stateDir "GENERAL.json"
$tmp = "$target.tmp"
$summary | ConvertTo-Json -Depth 10 | Set-Content $tmp -Encoding UTF8
Move-Item $tmp $target -Force

if ($rc -eq 0) {
    Write-Host ""
    Write-Host "GENERAL DEL CORTE GENERADO." -ForegroundColor Green
    Write-Host "No se tocaron nuevamente los dashboards de AWS/PASARELAS/HERCULES."
}
else {
    Write-Host "GENERAL terminó con código $rc." -ForegroundColor Red
}

exit $rc
