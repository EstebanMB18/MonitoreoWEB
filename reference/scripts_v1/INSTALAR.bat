@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title Instalar Centro de Monitoreo Compensar

echo ==========================================
echo   INSTALACION MONITOREO COMPENSAR
echo ==========================================
echo.

set "PYTHON_EXE="

REM 1. Si ya existe el entorno virtual, usarlo.
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
    echo [OK] Entorno virtual existente.
    goto :python_ok
)

REM 2. Intentar comando python.
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

REM Evitar alias de Microsoft Store que no sea un Python funcional.
if defined PYTHON_EXE (
    "%PYTHON_EXE%" --version >nul 2>&1
    if errorlevel 1 set "PYTHON_EXE="
)

REM 3. Intentar launcher py si existe.
if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=py -3.12"
        ) else (
            py --version >nul 2>&1
            if not errorlevel 1 set "PYTHON_EXE=py"
        )
    )
)

REM 4. Rutas comunes de Python 3.12/3.13 en Windows.
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python312\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python313\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python313\python.exe"

if not defined PYTHON_EXE (
    echo.
    echo ERROR: No se encontro una instalacion funcional de Python.
    echo.
    echo El instalador ya NO exige el comando "py".
    echo Se intento encontrar:
    echo   - python
    echo   - py / py -3.12
    echo   - Python 3.12/3.13 en rutas comunes de Windows
    echo.
    echo Instala Python 3.12 o 3.13 y vuelve a ejecutar INSTALAR.bat.
    echo Si usas el instalador oficial de Python, activa:
    echo   "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

:python_ok
echo [OK] Python detectado: %PYTHON_EXE%
echo.

REM Crear venv si todavía no existe.
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creando entorno virtual...
    if "%PYTHON_EXE%"=="py -3.12" (
        py -3.12 -m venv .venv
    ) else if "%PYTHON_EXE%"=="py" (
        py -m venv .venv
    ) else (
        "%PYTHON_EXE%" -m venv .venv
    )

    if errorlevel 1 (
        echo ERROR: No se pudo crear .venv
        pause
        exit /b 1
    )
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo ERROR: No se encontro el Python del entorno virtual.
    pause
    exit /b 1
)

echo [2/4] Actualizando pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/4] Instalando dependencias...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/4] Instalando Chromium de Playwright...
"%VENV_PY%" -m playwright install chromium
if errorlevel 1 goto :error

echo.
echo ==========================================
echo   INSTALACION TERMINADA CORRECTAMENTE
echo ==========================================
echo.
echo Ahora ejecuta ABRIR_MONITOREO.bat
pause
exit /b 0

:error
echo.
echo ERROR: La instalacion no pudo completarse.
echo Revisa el mensaje mostrado arriba.
pause
exit /b 1
