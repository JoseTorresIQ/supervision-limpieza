@echo off
title SISTEMA DE SUPERVISION DE LIMPIEZA DE EDIFICIOS (CLEANFACILITY PRO)
cd /d "%~dp0"

echo ===============================================================================
echo     CLEANFACILITY PRO - SUPERVISION DE LIMPIEZA DE EDIFICIOS (PERU)
echo     ISSA CIMS - OSHA - LEY 29783 (SST) - ISO 9001:2015
echo ===============================================================================

set "PY_CMD="

REM 1. Probar Python 3.10 si existe
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" -c "import streamlit" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
)

REM 2. Probar Python 3.12 si existe
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import streamlit" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

REM 3. Probar comando 'python' generico en PATH
if "%PY_CMD%"=="" (
    python -c "import streamlit" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

REM 4. Probar 'py' launcher
if "%PY_CMD%"=="" (
    py -3.10 -c "import streamlit" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.10"
)
if "%PY_CMD%"=="" (
    py -3.12 -c "import streamlit" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.12"
)

REM Si no se encontro, usar python por defecto
if "%PY_CMD%"=="" set "PY_CMD=python"

echo Iniciando servidor local en http://localhost:8502 ...
"%PY_CMD%" -m streamlit run app.py --server.headless=false --server.port=8502 --theme.primaryColor="#0284C7" --theme.backgroundColor="#FFFFFF" --theme.secondaryBackgroundColor="#F8FAFC" --theme.textColor="#0F172A"

if errorlevel 1 (
    echo.
    echo ===============================================================================
    echo [AVISO] Reinstalando dependencias en el entorno seleccionado...
    echo ===============================================================================
    "%PY_CMD%" -m pip install -r requirements.txt
    echo Reintentando ejecutar la aplicacion...
    "%PY_CMD%" -m streamlit run app.py --server.headless=false --server.port=8502
)

pause
