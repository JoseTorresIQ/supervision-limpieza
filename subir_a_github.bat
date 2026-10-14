@echo off
title Sincronizar con GitHub y Streamlit Cloud
color 0B
echo ===============================================================
echo     SINCRONIZAR CAMBIOS CON GITHUB Y STREAMLIT CLOUD
echo ===============================================================
echo.

set /p mensaje="Ingrese un mensaje para este cambio (o presione Enter): "
if "%mensaje%"=="" set mensaje=Actualizacion y mejoras del sistema

echo.
echo [1/3] Agregando archivos modificados...
git add .

echo.
echo [2/3] Registrando version en Git...
git commit -m "%mensaje%"

echo.
echo [3/3] Enviando a GitHub (push)...
git push origin main

echo.
if %errorlevel% equ 0 (
    echo ===============================================================
    echo  EXITO: Cambios subidos a GitHub correctamente.
    echo  Streamlit Cloud detectara este commit y actualizara
    echo  la aplicacion en la web / celular en menos de 1 minuto.
    echo ===============================================================
) else (
    echo ===============================================================
    echo  Hubo un detalle al enviar a GitHub.
    echo  Asegurese de haber configurado el repositorio remoto origin.
    echo ===============================================================
)
echo.
pause
