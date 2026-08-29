$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

function Leer-SecretoPlano($prompt) {
    $sec = Read-Host $prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

$ecUser = Read-Host "Usuario eCollect"
$ecPass = Leer-SecretoPlano "Password eCollect"
$payuUser = Read-Host "Usuario PayU"
$payuPass = Leer-SecretoPlano "Password PayU"

@"
ECOLLECT_URL=https://www.e-collect.com/app_express/admin/eCollectIndex.aspx
ECOLLECT_USER=$ecUser
ECOLLECT_PASSWORD=$ecPass
PAYU_URL=https://secure.payulatam.com/login.zul
PAYU_USER=$payuUser
PAYU_PASSWORD=$payuPass
HEADLESS=true
USAR_SESION=true
LOGIN_AUTOMATICO=true
TIMEOUT_CARGA_SEGUNDOS=480
REINTENTOS_CONSULTA=4
UMBRAL_BAJA=0.70
UMBRAL_ALERTA=0.40
PROMEDIO_MINIMO_ALERTA=5
SHAREPOINT_SALIDA=
"@ | Set-Content ".env" -Encoding UTF8

Write-Host "Credenciales guardadas localmente en .env" -ForegroundColor Green
Write-Host "No suba .env a GitHub ni lo comparta." -ForegroundColor Yellow
