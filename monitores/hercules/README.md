# Monitoreo Hércules · SharePoint

Proyecto para automatizar el monitoreo de Hércules con este flujo:

1. Descarga el reporte de **hoy** para validar alertas y generar el dashboard diario.
2. Copia el Excel de hoy a SharePoint como `HERCULES_DIARIO.xlsx`.
3. Descarga el reporte del **día anterior** para cargarlo al acumulado mensual.
4. Actualiza `HERCULES_ACUMULADO_YYYY_MM.xlsx` sin duplicar fechas.
5. Genera `DASHBOARD_HERCULES.html` con dos pestañas:
   - **Diario**: muestra el día actual.
   - **Mensual**: muestra el acumulado mensual.
6. Copia dashboard y archivos finales a SharePoint sincronizado por OneDrive.

## Archivos que deja en SharePoint

En la ruta configurada en `.env`:

- `HERCULES_DIARIO.xlsx`  
  Excel original descargado para el día actual. Se sobrescribe en cada ejecución.

- `HERCULES_RESUMEN_DIARIO.xlsx`  
  Resumen procesado del día actual. Se sobrescribe en cada ejecución.

- `DASHBOARD_HERCULES.html`  
  Dashboard con pestañas Diario y Mensual. Se sobrescribe en cada ejecución.

- `HERCULES_ACUMULADO_YYYY_MM.xlsx`  
  Acumulado mensual. Se crea un archivo por mes. Si se ejecuta varias veces, reemplaza la misma `Fecha_Reporte` para no duplicar.

## Configuración

1. Copia `.env.example` como `.env`.
2. Edita `.env`:

```env
HERCULES_USERNAME=TU_USUARIO
HERCULES_PASSWORD=TU_CLAVE

# Diario para alertas/dashboard: hoy
HERCULES_DIAS_ATRAS_DIARIO=0

# Acumulado mensual: día anterior
HERCULES_DIAS_ATRAS_ACUMULADO=1

SHAREPOINT_SYNC_DIR=C:\Users\brand\OneDrive - Compensar\COORDINACION SOPORTE SOLUCIONES - Monitoreo diario\HERCULES
```


## Instalación fácil para usuarios no técnicos

Para una persona que no sabe programar, el flujo recomendado es:

1. Descomprimir el ZIP.
2. Dar doble clic en:

```text
instalar_configurar_hercules.bat
```

Ese instalador:
- crea `.venv`
- instala dependencias
- instala Chromium de Playwright
- pregunta usuario y clave de Hércules una sola vez
- crea `.env`
- guarda la sesión
- deja listo el proyecto

Después, para ejecutar manualmente, puede usar:

```text
ejecutar_hercules_facil.bat
```

o:

```text
ejecutar_hercules.bat
```


## Primera instalación manual

```powershell
cd "C:\Users\brand\OneDrive\Escritorio\Proyectos en ejecucion\Monitoreos\monitoreo_hercules_sharepoint"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
notepad .env
python .\src\guardar_sesion.py
```

## Ejecución manual

```powershell
.\ejecutar_hercules.bat
```

## Tarea automática

Para programar o actualizar la tarea de Windows:

```powershell
$project = "C:\Users\brand\OneDrive\Escritorio\Proyectos en ejecucion\Monitoreos\monitoreo_hercules_sharepoint"
$bat = "$project\ejecutar_hercules_silencioso.bat"

$action = New-ScheduledTaskAction `
  -Execute "cmd.exe" `
  -Argument "/c `"$bat`"" `
  -WorkingDirectory $project

$trigger9 = New-ScheduledTaskTrigger -Daily -At 9:00AM
$trigger17 = New-ScheduledTaskTrigger -Daily -At 5:00PM

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable

Register-ScheduledTask `
  -TaskName "Monitoreo Hercules Diario" `
  -Action $action `
  -Trigger @($trigger9, $trigger17) `
  -Settings $settings `
  -Description "Ejecuta monitoreo automático de Hércules y actualiza SharePoint" `
  -Force
```

Para probarla:

```powershell
Start-ScheduledTask -TaskName "Monitoreo Hercules Diario"
Get-ScheduledTaskInfo -TaskName "Monitoreo Hercules Diario"
```

## Limpieza aplicada

Esta versión evita dejar archivos innecesarios:

- No crea logs en archivo.
- No guarda capturas PNG de diagnóstico.
- No genera HTML técnico adicional.
- El Excel diario local se sobrescribe en `downloads\hercules_diario.xlsx`.
- El resumen local se sobrescribe en `reports\resumen_hercules_diario.xlsx`.
- El dashboard local se sobrescribe en `reports\dashboard_hercules.html`.
- El Excel temporal usado para acumulado se borra después de actualizar el mensual.


## Tareas Windows actualizadas

Para evitar choque con AWS, ahora usa:

```text
09:05
13:05
17:05
```

Ejecuta:

```text
crear_tareas_windows_hercules_905.bat
```

Para revisar:

```text
revisar_tareas_hercules.bat
```

El BAT silencioso deja un único archivo de diagnóstico:

```text
ultima_ejecucion_tarea.txt
```

Ese archivo se sobrescribe en cada ejecución y sirve para saber por qué falló la tarea si Windows no muestra el error.

## Ajuste dashboard

El flujo ahora sube el dashboard dos veces si es necesario:

1. Apenas termina el reporte diario de hoy.
2. Después de actualizar el acumulado mensual.

Así el dashboard diario queda en SharePoint aunque falle la parte del acumulado.
