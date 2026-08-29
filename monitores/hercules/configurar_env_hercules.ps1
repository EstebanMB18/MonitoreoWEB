param(
    [string]$DefaultSharePoint = "C:\Users\brand\OneDrive - Compensar\COORDINACION SOPORTE SOLUCIONES - Monitoreo diario\HERCULES"
)

$ErrorActionPreference = "Stop"

function Read-Required([string]$PromptText, [string]$DefaultValue = "") {
    if ([string]::IsNullOrWhiteSpace($DefaultValue)) {
        do {
            $value = Read-Host $PromptText
            if ([string]::IsNullOrWhiteSpace($value)) {
                Write-Host "Este dato es obligatorio." -ForegroundColor Yellow
            }
        } while ([string]::IsNullOrWhiteSpace($value))
        return $value.Trim()
    } else {
        $value = Read-Host "$PromptText [$DefaultValue]"
        if ([string]::IsNullOrWhiteSpace($value)) {
            return $DefaultValue
        }
        return $value.Trim()
    }
}

function Convert-SecureStringToPlainText([SecureString]$SecureString) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CONFIGURACION MONITOREO HERCULES" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$username = Read-Required "Usuario de Hercules"
$securePassword = Read-Host "Clave de Hercules" -AsSecureString
$password = Convert-SecureStringToPlainText $securePassword

if ([string]::IsNullOrWhiteSpace($password)) {
    throw "La clave de Hercules no puede quedar vacia."
}

$sharepoint = Read-Required "Ruta local SharePoint/OneDrive" $DefaultSharePoint

$headlessAnswer = Read-Host "Ejecutar sin abrir navegador visible? S/N [S]"
if ([string]::IsNullOrWhiteSpace($headlessAnswer)) { $headlessAnswer = "S" }
$headless = if ($headlessAnswer.Trim().ToUpper().StartsWith("N")) { "false" } else { "true" }

$envContent = @"
HERCULES_URL=https://sistemahercules.bienestarcompensar.com/
HERCULES_REPORT_URL=https://sistemahercules.bienestarcompensar.com/sistema.php/reportes/estadisticas#/

AUTO_LOGIN=true
HERCULES_USERNAME=$username
HERCULES_PASSWORD=$password

HEADLESS=$headless
TIMEOUT_MS=60000

# Diario para alertas/dashboard: hoy
HERCULES_DIAS_ATRAS_DIARIO=0

# Acumulado mensual: dia anterior
HERCULES_DIAS_ATRAS_ACUMULADO=1

# Ruta local de OneDrive/SharePoint sincronizada.
SHAREPOINT_SYNC_DIR=$sharepoint

# Vacio = mes actual segun la fecha del reporte acumulado.
MES_CONSOLIDAR=
"@

$envPath = Join-Path $PSScriptRoot ".env"
Set-Content -Path $envPath -Value $envContent -Encoding UTF8

Write-Host ""
Write-Host ".env creado/actualizado correctamente:" -ForegroundColor Green
Write-Host $envPath -ForegroundColor Green

if (-not (Test-Path $sharepoint)) {
    Write-Host ""
    Write-Host "ADVERTENCIA: La ruta SharePoint no existe en este momento:" -ForegroundColor Yellow
    Write-Host $sharepoint -ForegroundColor Yellow
    Write-Host "Verifica que OneDrive este sincronizado o corrige SHAREPOINT_SYNC_DIR en .env." -ForegroundColor Yellow
}
