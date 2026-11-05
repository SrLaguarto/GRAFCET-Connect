"""Vuelve a sellar proyectos .grafnet con la clave de distribución.

Uso:  python tools/resellar.py --archivo-clave RUTA ARCHIVO.grafnet [ARCHIVO_O_CARPETA ...]

(También vale la variable de entorno GRAFCONNECT_CLAVE_SELLO, como en tools/construir_ejecutable.py.)
Una carpeta aporta todos sus .grafnet, sin recursividad. Para cada archivo:
- válido con la clave de distribución: «ya sellado para la distribución», no se hace nada;
- válido con la clave pública de desarrollo: se escribe una copia con el contenido idéntico y el sello nuevo en
  `sellados_1.0/` junto al original (el original no se toca; una copia anterior se sustituye de forma atómica);
- con cualquier otro sello: «sello no válido: no se toca».
No se imprime nunca la clave ni nada derivado de ella.
"""
import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from tools.clave_construccion import ErrorClave, obtener_clave  # noqa: E402
from escritorio.sello import CLAVE_DESARROLLO  # noqa: E402
from grafcet.contenedor import ErrorContenedor, guardar_atomico, resellar, sello_valido  # noqa: E402

SUBCARPETA = "sellados_1.0"


def archivos_de(rutas: list[str]) -> list[Path]:
    """Los .grafnet indicados; de una carpeta, los que tiene directamente."""
    salida = []
    for texto in rutas:
        ruta = Path(texto)
        if ruta.is_dir():
            salida.extend(sorted(p for p in ruta.glob("*.grafnet") if p.is_file()))
        else:
            salida.append(ruta)
    return salida


def resellar_archivo(ruta: Path, clave: bytes) -> str:
    """Devuelve 'ya', 'resellado', 'invalido' o 'error'; escribe el mensaje de cada caso."""
    try:
        datos = ruta.read_bytes()
        if sello_valido(datos, clave):
            print(f"{ruta.name}: ya sellado para la distribución")
            return "ya"
        if not sello_valido(datos, CLAVE_DESARROLLO):
            print(f"{ruta.name}: sello no válido: no se toca")
            return "invalido"
        nuevo = resellar(datos, clave)
        if not sello_valido(nuevo, clave):
            raise ErrorContenedor("el resultado no verifica")
        destino = ruta.parent / SUBCARPETA / ruta.name
        guardar_atomico(destino, nuevo)
    except (OSError, ErrorContenedor) as exc:
        print(f"{ruta.name}: no se pudo procesar ({exc})")
        return "error"
    print(f"{ruta.name}: resellado en {SUBCARPETA}/{ruta.name}")
    return "resellado"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vuelve a sellar proyectos .grafnet con la clave de distribución.")
    ap.add_argument("--archivo-clave", help="archivo externo con la clave (≥ 32 bytes, fuera del repositorio)")
    ap.add_argument("rutas", nargs="+", help="archivos .grafnet o carpetas que los contienen")
    args = ap.parse_args(argv)
    try:
        clave = obtener_clave(RAIZ, args.archivo_clave)
    except ErrorClave as exc:
        print(f"ERROR: {exc}")
        return 2
    cuenta = {"ya": 0, "resellado": 0, "invalido": 0, "error": 0}
    for ruta in archivos_de(args.rutas):
        cuenta[resellar_archivo(ruta, clave)] += 1
    print(f"\nResumen: {cuenta['resellado']} resellados, {cuenta['ya']} ya sellados para la distribución, "
          f"{cuenta['invalido']} con sello no válido, {cuenta['error']} con error")
    return 1 if cuenta["invalido"] or cuenta["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
