"""Comprobación del argumento del instalador en un ejecutable, sin tocar Documentos reales."""
import subprocess


def comprobar(ejecutable, carpeta, entorno):
    try:
        resultado = subprocess.run([str(ejecutable), "--prueba-servidor-simulador"], cwd=carpeta,
                                   env=entorno, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: no se pudo comprobar la activación del servidor web: {exc}", flush=True)
        return False
    if resultado.returncode:
        print("ERROR: falló la activación del servidor web en el ejecutable empaquetado.", flush=True)
        return False
    print("Activación sin interfaz comprobada en el ejecutable, con Documentos temporales.", flush=True)
    return True
