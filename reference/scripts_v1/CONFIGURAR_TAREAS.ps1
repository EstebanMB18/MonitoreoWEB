# SPRINT_13_8_AUTO_REV2_SCHEDULES_OK
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "RUN_TASK.ps1"
$GeneralRunner = Join-Path $PSScriptRoot "RUN_GENERAL.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

Write-Host "Eliminando tareas antiguas conocidas..." -ForegroundColor Cyan
$old = @(
"Monitoreo AWS - Corte 1","Monitoreo AWS - Corte 2","Monitoreo AWS - Corte 3",
"Monitoreo AWS - 09 AM","Monitoreo AWS - 01 PM","Monitoreo AWS - 05 PM",
"Monitoreo Verticales Dia Anterior","Monitoreo Verticales 0840","Monitoreo Verticales 1640",
"Monitoreo Hercules Diario","Monitoreo Hercules 09","Monitoreo Hercules 13","Monitoreo Hercules 17",
"Monitoreo Hercules 0905","Monitoreo Hercules 1305","Monitoreo Hercules 1705"
)
foreach($n in $old){
    Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
}
Get-ScheduledTask -TaskName "Compensar Monitoreo *" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false

# Monitores: cada uno hace SOLO su trabajo.
$tasks = @(
 @{M="PASARELAS"; C="09"; T="08:40"}, @{M="AWS"; C="09"; T="08:50"}, @{M="HERCULES"; C="09"; T="09:00"},
 @{M="PASARELAS"; C="13"; T="12:40"}, @{M="AWS"; C="13"; T="12:50"}, @{M="HERCULES"; C="13"; T="13:00"},
 @{M="PASARELAS"; C="17"; T="16:40"}, @{M="AWS"; C="17"; T="16:50"}, @{M="HERCULES"; C="17"; T="17:00"}
)

foreach($t in $tasks){
    $name = "Compensar Monitoreo $($t.M) $($t.C)"
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -Monitor $($t.M) -Modo actual -Corte $($t.C)"
    $action = New-ScheduledTaskAction -Execute $PowerShell -Argument $arg -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $t.T
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "Monitor independiente Compensar" -Force | Out-Null
    Write-Host "OK $name -> $($t.T)" -ForegroundColor Green
}

# GENERAL: tarea separada. Puede arrancar al corte y esperar marcadores.
$generalTasks = @(
    @{C="09"; T="09:05"},
    @{C="13"; T="13:05"},
    @{C="17"; T="17:05"}
)

foreach($t in $generalTasks){
    $name = "Compensar Monitoreo GENERAL $($t.C)"
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$GeneralRunner`" -Corte $($t.C)"
    $action = New-ScheduledTaskAction -Execute $PowerShell -Argument $arg -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $t.T
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "Coordinador General del mismo corte" -Force | Out-Null
    Write-Host "OK $name -> $($t.T)" -ForegroundColor Cyan
}

# Día anterior: sigue siendo TODOS dentro de un solo run.py.
$name = "Compensar Monitoreo DIA_ANTERIOR"
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -Monitor TODOS -Modo dia-anterior -Corte 09 -HoraInicio 00:00 -HoraFin 23:59 -SoloSiNoEjecutadoHoy"
$action = New-ScheduledTaskAction -Execute $PowerShell -Argument $arg -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "Monitoreo Compensar día anterior" -Force | Out-Null

Write-Host ""
Write-Host "ARQUITECTURA NUEVA:" -ForegroundColor Yellow
Write-Host "PASARELAS/AWS/HERCULES terminan de forma independiente."
Write-Host "GENERAL es una cuarta tarea y solo consolida el mismo corte."
Write-Host ""
Get-ScheduledTask -TaskName "Compensar Monitoreo *" | Select-Object TaskName,State
