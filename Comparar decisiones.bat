@echo off
rem Comparador de decisiones GRAFCET (P-IMP-21): cada cuestion abierta con su ejemplo, una vez por lectura.
rem Las respuestas se guardan en docs\decisiones.json. Requiere Python 3.12.
cd /d "%~dp0"
title Comparador de decisiones GRAFCET
echo Comparador de decisiones GRAFCET: se abrira el navegador.
echo Para detenerlo, cierre esta ventana.
python tools\banco_de_pruebas.py --port 8766 --abrir --comparar
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Si el puerto 8766 esta ocupado, cierre la ventana del banco de pruebas.
  pause
)