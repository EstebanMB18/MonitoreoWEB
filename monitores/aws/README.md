# Monitoreo AWS optimizado

Proyecto organizado por **INTEROPPROD**, **MENSAJERÍA/CORPORATIVO** y **CSC**. Genera un Excel operativo completo y un HTML ejecutivo con alertas, gráficos y detalle técnico.

## Primera instalación
Ejecutar `scripts\instalar.bat`.

## Prueba sin AWS
Ejecutar `scripts\probar_demo.bat`.

## Monitoreo real
Ejecutar `scripts\ejecutar_monitoreo.bat`.

## Cortes automáticos
- Corte 1: día anterior 18:00 a día actual 09:00.
- Corte 2: 09:00 a 13:00.
- Corte 3: 13:00 a 18:00.

El bot calcula el corte según la hora. Para tareas de Windows, ejecutar como administrador `scripts\crear_tareas_windows.bat`.

## Correcciones incluidas
- Consultas de pagos alineadas con PayU, Ecollect y Receiver.
- OTP 408 se consulta en API Mensajería.
- Validar OTP 500 se consulta en el log corporativo correspondiente.
- Total sent usa `@type = REPORT` sin sumar Request Received.
- Mensajería incluye timeout, 502, 503, Cannot/Broker SD, SMS failed, errores 400 y exitosos 200.
- Alertas de replicador, TUP, pagos, MongoDB y errores 400 repetitivos.
- Excel con resumen, alertas, hojas separadas, tendencias y gráficos.
- HTML con paleta corporativa sobria, indicadores, gráficas y tablas detalladas.


## Salida oficial sin acumulación
En una ejecución real, el bot guarda y reemplaza siempre estos dos archivos:

- `C:\Users\brand\OneDrive - Compensar\COORDINACION SOPORTE SOLUCIONES - Monitoreo diario\AWS\Monitoreo_AWS.xlsx`
- `C:\Users\brand\OneDrive - Compensar\COORDINACION SOPORTE SOLUCIONES - Monitoreo diario\AWS\Dashboard_AWS.html`

Los nombres son permanentes. Cada nuevo monitoreo sobrescribe el anterior. Cierra el Excel si está abierto para permitir el reemplazo. La prueba demo continúa guardándose aparte en `salida\demo`.


## Programación diaria: 09:00, 13:00 y 17:00
Ejecute como administrador `scripts\crear_tareas_windows.bat`.

Se crean estas tareas:
- `Monitoreo AWS - 09 AM`: día anterior 18:00 a día actual 09:00.
- `Monitoreo AWS - 05 PM`: día actual 09:00 a 17:00.

Ambas reemplazan los archivos oficiales para evitar acumulación.
