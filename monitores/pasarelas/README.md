# Monitoreo Verticales Pasarelas v8.1

Cambios principales:

- eCollect ahora **obligatoriamente descarga CSV**. No se usa HTML como fuente de datos.
- Si eCollect responde sin registros, se crea un CSV marcador `SIN_DATOS` para dejar 0 OK y $0.
- Si eCollect manda a la página pública/landing, el bot vuelve al link principal, hace login y reintenta la misma vertical.
- PayU ahora tiene diagnóstico más claro y script de prueba solo PayU.
- PayU detecta la pantalla de “sesión ya activa”, presiona Salir/Cerrar y vuelve a iniciar sesión automáticamente.

## Prueba recomendada

```powershell
cd "C:\Users\brand\OneDrive\Escritorio\Proyectos en ejecucion\Monitoreos\monitoreo_verticales_pasarelas_v8_1.1"
powershell -ExecutionPolicy Bypass -File scripts\00_instalar.ps1
powershell -ExecutionPolicy Bypass -File scripts\01_configurar_credenciales.ps1
powershell -ExecutionPolicy Bypass -File scripts\09_activar_modo_visible.ps1
```

Primero prueba PayU solo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\12_ejecutar_solo_payu_09am.ps1
```

Luego prueba completo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\04_ejecutar_web_09am.ps1
```

Si PayU falla, revisar `logs\payu_no_formulario_*.png/html` o `logs\payu_no_descarga_*.png/html`.


## Cambios v8.2
- eCollect exige CSV o marcador SIN_DATOS; no usa HTML como fuente.
- La respuesta roja de sin registros se detecta en 5 segundos.
- Corrección TUP desplazado a columna siguiente.
- Resumen general para pantallazo.
- Acumulado por corte en `data/historico/acumulado_por_corte.xlsx` y mensual en `data/mensual`.
- Copia final a SharePoint/OneDrive en la carpeta ECOLLECT, sobrescribiendo archivos finales.
