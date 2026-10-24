@echo off
rem Lanzador del banco de pruebas GRAFCET (provisional; no es el producto final). Requiere Python 3.12.
cd /d "%~dp0"
title Banco de pruebas GRAFCET
echo Banco de pruebas GRAFCET: se abrira el navegador.
echo Para detenerlo, cierre esta ventana.
python tools\banco_de_pruebas.py --port 8766 --abrir
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Si el puerto 8766 esta ocupado, cierre la otra ventana del banco.
  pause
)
