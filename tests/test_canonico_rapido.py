"""SCAN01..SCAN02: `canonical._string` con el atajo de las cadenas sin nada que escapar (V2-E9, solo rendimiento) da lo mismo que la versión anterior, copiada aquí."""
import json
import unittest
from pathlib import Path
from random import Random
from unittest import mock
from zipfile import ZipFile

from grafcet import canonical
from grafcet.canonical import CanonicalError

REFERENCIA = Path(__file__).with_name("fixtures") / "referencia"


def _string_antes(s, out):
    out.append('"')
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        elif 0xD800 <= o <= 0xDFFF:
            raise CanonicalError("sustituto Unicode aislado")
        else:
            out.append(ch)
    out.append('"')


def resultado(f, s):
    out = []
    try:
        f(s, out)
    except CanonicalError as exc:
        return ("error", str(exc))
    return ("ok", "".join(out))


class CanonicoRapido(unittest.TestCase):
    def test_SCAN01_las_cadenas_dan_lo_mismo_con_y_sin_el_atajo(self):
        """REQ-DAT-05: cadenas al azar con comillas, barras, controles, sustitutos aislados, acentos y emojis se escriben (o se rechazan) igual que antes."""
        azar = Random(3)
        alfabeto = ['a', 'Z', '0', ' ', '-', '_', '.', '"', "\\", "\n", "\t", "\x00", "\x1f", "\x7f", "\x20", "ñ", "€", "😀", "\ud800", "\udfff", "\ud7ff", "\ue000"]
        casos = ["", "e-3b06cb7ec39e4c9cad6eeb7f3dd50d0e", '"', "\\", "\u2028", "\ud83d"]
        casos += ["".join(azar.choice(alfabeto) for _ in range(azar.randrange(0, 12))) for _ in range(3000)]
        for s in casos:
            self.assertEqual(resultado(canonical._string, s), resultado(_string_antes, s), repr(s))

    def test_SCAN02_el_texto_canonico_y_el_digest_de_un_documento_no_cambian(self):
        """REQ-DAT-05, REQ-DAT-08: el texto canónico y el digest de los documentos de GEMMA y de Linea larga coinciden con los de la versión anterior."""
        for nombre in ("guia_gemma.grafnet", "linea_larga.grafnet"):
            with ZipFile(REFERENCIA / nombre) as z:
                documentos = [json.loads(z.read(n)) for n in z.namelist() if n.startswith(("model-", "presentation-"))]
            self.assertTrue(documentos)
            for doc in documentos:
                nuevo = (canonical.canonical_text(doc), canonical.digest(doc))
                with mock.patch.object(canonical, "_string", _string_antes):
                    antes = (canonical.canonical_text(doc), canonical.digest(doc))
                self.assertEqual(nuevo, antes, nombre)


if __name__ == "__main__":
    unittest.main()
