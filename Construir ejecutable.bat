@echo off
rem Construye la version portable para Windows del simulador (P-IMP-29): dist\GRAFCET\GRAFCET.exe.
rem Requiere Python 3.12, PySide6-Essentials y pyinstaller.
cd /d "%~dp0"
title Construir el simulador GRAFCET
python tools\construir_ejecutable.py
if errorlevel 1 (
  echo.
  echo No se pudo construir. Revise los mensajes de arriba.
) else (
  echo.
  echo La carpeta dist\GRAFCET es el programa: copiela entera y abra GRAFCET.exe.
)
pause
