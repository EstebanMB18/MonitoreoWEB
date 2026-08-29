param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("PASARELAS","AWS","HERCULES","TODOS")]
    [string]$Monitor,

    [ValidateSet("actual","acumulado-hoy","dia-anterior","fecha")]
    [string]$Modo = "actual",

    [ValidateSet("09","13","17")]
    [string]$Corte = "09",

    [string]$Fecha = "",
    [string]$HoraInicio = "00:00",
    [string]$HoraFin = "23:59",
    [switch]$SoloSiNoEjecutadoHoy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { $Python = "py" }
Set-Location $Root

function Get-OutputRoot {
    $cfgPath = Join-Path $Root "config\app.json"
    if (!(Test-Path $cfgPath)) { throw "No existe config\app.json" }
    $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
    return [Environment]::ExpandEnvironmentVariables($cfg.output_root)
}

function Get-RunId {
    param([string]$Corte)
    return "$(Get-Date -Format 'yyyyMMdd')_corte_$Corte"
}

function Get-StateDir {
    param([string]$Corte)
    $general = Join-Path (Get-OutputRoot) "GENERAL"
    return Join-Path $general ("state\automaticas\" + (Get-RunId $Corte))
}

function Write-MonitorState {
    param(
        [string]$Monitor,
        [string]$Estado,
        [int]$Rc,
        [datetime]$Inicio,
        [datetime]$Fin,
        [string]$Fuente,
        [bool]$FuenteActual
    )

    $dir = Get-StateDir $Corte
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $obj = [ordered]@{
        run_id = Get-RunId $Corte
        fecha = Get-Date -Format "yyyy-MM-dd"
        corte = $Corte
        monitor = $Monitor
        modo = $Modo
        estado = $Estado
        rc = $Rc
        inicio = $Inicio.ToString("o")
        fin = $Fin.ToString("o")
        fuente = $Fuente
        fuente_actual = $FuenteActual
    }

    $target = Join-Path $dir "$Monitor.json"
    $tmp = "$target.tmp"
    $obj | ConvertTo-Json -Depth 5 | Set-Content $tmp -Encoding UTF8
    Move-Item $tmp $target -Force

    Write-Host "ESTADO AUTOMATICO: $Monitor -> $Estado" -ForegroundColor Cyan
    Write-Host "RUN_ID: $($obj.run_id)"
}

function Get-ExpectedSource {
    param([string]$Monitor)
    $out = Get-OutputRoot

    switch ($Monitor) {
        "PASARELAS" {
            return Join-Path $out "ECOLLECT\resumen_verticales_diario.xlsx"
        }
        "AWS" {
            return Join-Path $out "GENERAL\data\aws_gerencial.json"
        }
        "HERCULES" {
            return Join-Path $out "HERCULES\HERCULES_RESUMEN_DIARIO.xlsx"
        }
        default { return "" }
    }
}

# Día anterior conserva el flujo TODOS porque en ese caso run.py sí controla
# todos los monitores dentro del mismo proceso y puede consolidar al final.
if ($Modo -eq "dia-anterior" -and $SoloSiNoEjecutadoHoy) {
    $general = Join-Path (Get-OutputRoot) "GENERAL"
    $stateDir = Join-Path $general "state"
    $marker = Join-Path $stateDir "day_before_last_run.txt"
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    $today = Get-Date -Format "yyyy-MM-dd"

    if (Test-Path $marker) {
        $last = (Get-Content $marker -Raw).Trim()
        if ($last -eq $today) {
            Write-Host "Día anterior ya fue ejecutado hoy ($today). Se omite." -ForegroundColor Yellow
            exit 0
        }
    }
}

$started = Get-Date

$argsRun = @(
    "$Root\run.py",
    "--monitor", $Monitor.ToLower(),
    "--modo", $Modo,
    "--corte", $Corte,
    "--hora-inicio", $HoraInicio,
    "--hora-fin", $HoraFin
)

if ($Fecha -and $Modo -eq "fecha") {
    $argsRun += @("--fecha", $Fecha)
}

# REGLA SPRINT 13.8:
# Las tareas automáticas individuales JAMÁS construyen General.
# Cada una termina y sale. GENERAL tiene su propia tarea coordinadora.
if ($Monitor -ne "TODOS") {
    $argsRun += "--no-finalize"
}

if ($Python -eq "py") {
    & py -3.12 @argsRun
    $rc = $LASTEXITCODE
}
else {
    & $Python @argsRun
    $rc = $LASTEXITCODE
}

$ended = Get-Date

if ($Monitor -ne "TODOS") {
    $source = Get-ExpectedSource $Monitor
    $fresh = $false

    if ($source -and (Test-Path $source)) {
        $mtime = (Get-Item $source).LastWriteTime
        $fresh = $mtime -ge $started.AddSeconds(-5)
    }

    if ($rc -eq 0 -and $fresh) {
        $state = "OK"
    }
    elseif ($rc -eq 0 -and -not $fresh) {
        $state = "STALE"
        $rc = 20
        Write-Host "ADVERTENCIA: $Monitor terminó sin publicar una fuente nueva del corte." -ForegroundColor Yellow
        Write-Host "Fuente esperada: $source"
    }
    else {
        $state = "ERROR"
    }

    Write-MonitorState `
        -Monitor $Monitor `
        -Estado $state `
        -Rc $rc `
        -Inicio $started `
        -Fin $ended `
        -Fuente $source `
        -FuenteActual $fresh
}

if ($rc -eq 0 -and $Modo -eq "dia-anterior" -and $SoloSiNoEjecutadoHoy) {
    $general = Join-Path (Get-OutputRoot) "GENERAL"
    $stateDir = Join-Path $general "state"
    $marker = Join-Path $stateDir "day_before_last_run.txt"
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    Set-Content $marker (Get-Date -Format "yyyy-MM-dd") -Encoding UTF8
}

exit $rc
