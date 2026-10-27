@echo off
rem Simulador GRAFCET de escritorio (P-IMP-29) desde el codigo fuente. Requiere Python 3.12 y PySide6-Essentials.
rem La version portable, sin Python, se construye con "Construir ejecutable.bat" y queda en dist\GRAFCET.
cd /d "%~dp0"
title Simulador GRAFCET
echo Simulador GRAFCET: esta ventana se cierra sola al cerrar el simulador.
python escritorio\simulador.py %*
if errorlevel 1 (
  echo.
  echo No se pudo abrir. Si falta PySide6: python -m pip install --user PySide6-Essentials
  pause
)
