# Ejecuta las pruebas de la suite (todas, o las de un módulo / nombre) sin escribir nada en el repositorio.
# Uso, desde la raíz:   powershell -File propuesta/herramientas/correr_pruebas.ps1 [-Modulo test_aula_cambios.py] [-Nombre SAUC19]
param([string]$Modulo = "test*.py", [string]$Nombre = "")
$py = "C:\Users\yrqiq\Desktop\IA SGE\venv-grafcet\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QPA_FONTDIR = "C:/Windows/Fonts"
$argumentos = @("-m", "unittest", "discover", "-s", "tests", "-t", "tests", "-p", $Modulo)
if ($Nombre) { $argumentos += @("-k", $Nombre) }
& $py @argumentos
