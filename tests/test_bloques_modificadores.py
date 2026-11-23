"""SP8M: operaciones puras del modelo del programador (E8, P3): modificadores NOT, ↑ y ↓ sobre una ficha, envolver, desenvolver
y contar huecos. Sin Qt más que el import del módulo.

REQ-EDT-02, REQ-EDT-09: ninguna operación cambia las funciones de texto; el texto que se obtiene es el mismo que sale con los
bloques puestos a mano (arrastrando) o leídos de un texto guardado.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from escritorio import bloques as B
    QT = True
except ImportError:
    QT = False

VARS = {"a": ("input", "bool"), "b": ("input", "bool"), "CT": ("internal", "int")}


def a():
    return B.var("a")


def y_ab():
    return B.nuevo("y", a=B.var("a"), b=B.var("b"))


def env(clase, hijo, **campos):
    return B.nuevo(clase, a=hijo, **campos)


def arbol(texto):
    return B.texto_a_arbol(texto, VARS, [])


def aplicar(raiz, ruta, *pulsaciones):
    for m in pulsaciones:
        raiz = B.alternar_modificador(raiz, ruta, m)
    return raiz


@unittest.skipUnless(QT, "requiere PySide6")
class Modificadores(unittest.TestCase):
    def test_SP8M01_las_seis_combinaciones_sobre_una_variable(self):
        """REQ-EDT-02, REQ-EDT-09: NOT, ↑ y ↓ en los dos órdenes: el orden en que se pulsan es el orden en que se aplican."""
        casos = {("no",): "NOT a", ("sube",): "↑a", ("baja",): "↓a",
                 ("no", "sube"): "↑(NOT a)", ("sube", "no"): "NOT ↑a",
                 ("no", "baja"): "↓(NOT a)", ("baja", "no"): "NOT ↓a"}
        for pulsadas, texto in casos.items():
            with self.subTest(pulsadas=pulsadas):
                r = aplicar(a(), (), *pulsadas)
                self.assertEqual(B.arbol_a_texto(r), texto)
                self.assertEqual(r, arbol(texto), "el mismo árbol que el del texto guardado")
                self.assertEqual(B.arbol_a_texto(arbol(B.arbol_a_texto(r))), texto, "ida y vuelta")

    def test_SP8M02_reaplicar_quita_y_el_otro_flanco_cambia(self):
        """REQ-EDT-02: NOT y el flanco, pulsados otra vez, se quitan; ↑ sobre una ficha con ↓ cambia el flanco sin tocar NOT."""
        r = aplicar(a(), (), "no", "sube")
        self.assertEqual(B.arbol_a_texto(aplicar(r, (), "no")), "↑a")
        self.assertEqual(B.arbol_a_texto(aplicar(r, (), "sube")), "NOT a")
        self.assertEqual(B.arbol_a_texto(aplicar(r, (), "baja")), "↓(NOT a)")
        self.assertEqual(B.arbol_a_texto(aplicar(r, (), "no", "sube")), "a")
        s = aplicar(a(), (), "sube", "no")
        self.assertEqual(B.arbol_a_texto(aplicar(s, (), "baja")), "NOT ↓a")
        self.assertEqual(aplicar(s, (), "sube", "no"), a())

    def test_SP8M03_sobre_un_grupo_y_un_retardo(self):
        """REQ-EDT-02: sobre un «y», un grupo o un retardo se obtiene el texto de siempre (NOT (a AND b), ↑(3s/a)…)."""
        r = aplicar(y_ab(), (), "no")
        self.assertEqual(B.arbol_a_texto(r), "NOT (a AND b)")
        self.assertEqual(B.arbol_a_texto(arbol("NOT (a AND b)")), B.arbol_a_texto(r))
        grupo = env("par", y_ab())
        self.assertEqual(B.arbol_a_texto(aplicar(grupo, (), "no")), "NOT (a AND b)")
        temp = env("temp", a(), t1="3s", t2="")
        self.assertEqual(B.arbol_a_texto(aplicar(temp, (), "sube")), "↑(3s/a)")
        self.assertEqual(B.arbol_a_texto(aplicar(temp, (), "no")), "NOT (3s/a)")
        self.assertEqual(B.arbol_a_texto(aplicar(temp, (), "no", "baja")), "↓(NOT (3s/a))")
        self.assertEqual(B.arbol_a_texto(aplicar(temp, (), "baja", "no")), "NOT ↓(3s/a)")

    def test_SP8M04_dentro_de_otro_bloque_y_la_ruta_se_conserva(self):
        """REQ-EDT-02: el modificador se aplica a la ficha de una ruta interior; sobre la ficha o sobre cualquier eslabón de su
        cadena da el mismo resultado, y la ruta del bloque más externo no cambia."""
        o = B.nuevo("o", a=y_ab(), b=B.var("a"))
        r = aplicar(o, ("a", "b"), "no")
        self.assertEqual(B.arbol_a_texto(r), "a AND NOT b OR a")
        self.assertEqual(B.cadena_modificadores(r, ("a", "b")), (("a", "b"), ["no"]))
        self.assertEqual(B.cadena_modificadores(r, ("a", "b", "a")), (("a", "b"), ["no"]), "desde la variable de dentro")
        r2 = aplicar(r, ("a", "b", "a"), "sube")  # pulsado con la variable seleccionada: se aplica a la ficha entera
        self.assertEqual(B.arbol_a_texto(r2), "a AND ↑(NOT b) OR a")
        self.assertEqual(B.cadena_modificadores(r2, ("a", "b")), (("a", "b"), ["no", "sube"]))
        self.assertEqual(o, aplicar(r2, ("a", "b"), "no", "sube"), "quitados los dos, el árbol de partida")

    def test_SP8M05_cadena_modificadores(self):
        """REQ-EDT-02: la cadena sube mientras el padre sea no, ↑ o ↓; devuelve la ruta del más externo y los modificadores
        de dentro afuera."""
        r = arbol("NOT ↑a")
        self.assertEqual(B.cadena_modificadores(r, ()), ((), ["sube", "no"]))
        self.assertEqual(B.cadena_modificadores(r, ("a",)), ((), ["sube", "no"]))
        self.assertEqual(B.cadena_modificadores(r, ("a", "a")), ((), ["sube", "no"]))
        self.assertEqual(B.cadena_modificadores(a(), ()), ((), []))
        y = B.nuevo("y", a=arbol("NOT a"), b=a())
        self.assertEqual(B.cadena_modificadores(y, ("a", "a")), (("a",), ["no"]))
        self.assertEqual(B.cadena_modificadores(y, ("b",)), (("b",), []), "un «y» no es modificador")

    def test_SP8M06_hueco_pendiente_con_modificador(self):
        """REQ-EDT-02: sobre un hueco, el modificador deja un bloque con su hueco («[NOT | pulsa o arrastra variable…]»); al
        quitarlo vuelve el hueco; rellenar el hueco conserva el modificador."""
        r = B.alternar_modificador(None, (), "no")
        self.assertEqual(r, B.nuevo("no", a=None))
        self.assertEqual(B.faltan(r), 1)
        self.assertEqual(B.arbol_a_texto(r), "NOT ?")
        relleno = B.soltar(r, ("a",), a())
        self.assertEqual(B.arbol_a_texto(relleno), "NOT a")
        self.assertIsNone(B.alternar_modificador(r, (), "no"))
        o = B.nuevo("o", a=None, b=a())
        self.assertEqual(B.alternar_modificador(B.alternar_modificador(o, ("a",), "sube"), ("a",), "sube"), o)

    def test_SP8M07_no_toca_el_original_ni_acepta_clases_ajenas(self):
        """REQ-EDT-02: las operaciones devuelven un árbol nuevo; una clase que no es modificador no hace nada."""
        origen = y_ab()
        copia = B.copy.deepcopy(origen)
        aplicar(origen, ("a",), "no", "sube")
        self.assertEqual(origen, copia)
        self.assertEqual(B.alternar_modificador(origen, (), "y"), origen)


@unittest.skipUnless(QT, "requiere PySide6")
class EnvolverDesenvolver(unittest.TestCase):
    def test_SP8M10_envolver_en_grupo_y_en_retardo(self):
        """REQ-EDT-02, REQ-EDT-09: «Envolver ( … )» y «temporizar» sobre un bloque dan el texto de los bloques puestos a mano."""
        r = B.envolver(y_ab(), (), "par")
        self.assertEqual(B.arbol_a_texto(r), "(a AND b)")
        self.assertEqual(r, arbol("(a AND b)"))
        o = B.nuevo("o", a=y_ab(), b=B.var("a"))
        self.assertEqual(B.arbol_a_texto(B.envolver(o, ("a",), "par")), "(a AND b) OR a")
        self.assertEqual(B.arbol_a_texto(B.envolver(a(), (), "temp")), "3s/a")
        manual = B.soltar(a(), (), B.nuevo("temp"))
        self.assertEqual(B.envolver(a(), (), "temp"), manual, "lo mismo que soltar «temporizar» sobre un bloque ocupado")

    def test_SP8M11_desenvolver_quita_parentesis_y_retardo(self):
        """REQ-EDT-02: «Quitar paréntesis» y «Quitar retardo» devuelven el bloque de dentro, y envolver y desenvolver se anulan."""
        r = arbol("(a AND b) OR a")
        self.assertEqual(B.arbol_a_texto(B.desenvolver(r, ("a",))), "a AND b OR a")
        t = arbol("3s/a")
        self.assertEqual(B.desenvolver(t, ()), a())
        self.assertEqual(B.desenvolver(B.envolver(r, ("b",), "par"), ("b",)), r)
        n = B.nuevo("no", a=B.nuevo("sube", a=a()))
        self.assertEqual(B.desenvolver(n, ()), B.nuevo("sube", a=a()))

    def test_SP8M12_lo_que_no_se_puede_no_cambia(self):
        """REQ-EDT-02: desenvolver una ficha o un «y» (varios huecos) y envolver con una clase sin hueco dejan el árbol igual."""
        self.assertEqual(B.desenvolver(a(), ()), a())
        self.assertEqual(B.desenvolver(y_ab(), ()), y_ab())
        self.assertEqual(B.envolver(a(), (), "var"), a())
        self.assertEqual(B.envolver(a(), (), "no"), B.nuevo("no", a=a()))
        self.assertEqual(B.desenvolver(B.nuevo("par", a=None), ()), None, "un grupo vacío desaparece y deja su hueco")


@unittest.skipUnless(QT, "requiere PySide6")
class ContarHuecos(unittest.TestCase):
    def test_SP8M20_faltan(self):
        """REQ-EDT-02: cuenta los huecos que la fórmula escribe como «?»: huecos vacíos y fichas sin nombre."""
        self.assertEqual(B.faltan(None), 0, "sin fórmula no hay nada que completar")
        self.assertEqual(B.faltan(B.nuevo("no", a=None)), 1)
        self.assertEqual(B.faltan(a()), 0)
        self.assertEqual(B.faltan(B.nuevo("y", a=None, b=None)), 2)
        self.assertEqual(B.faltan(B.nuevo("o", a=y_ab(), b=None, c=None)), 2)
        self.assertEqual(B.faltan(B.nuevo("no", a=B.nuevo("sube", a=None))), 1)
        self.assertEqual(B.faltan(B.nuevo("var", n=None)), 1)
        self.assertEqual(B.faltan(B.nuevo("cmp", n=None)), 1)
        self.assertEqual(B.faltan(B.nuevo("cmp", n="CT")), 0)
        self.assertEqual(B.faltan(B.nuevo("temp", a=None)), 1)
        self.assertEqual(B.faltan(B.nuevo("const", v=1)), 0)

    def test_SP8M21_coincide_con_los_interrogantes_del_texto(self):
        """REQ-EDT-02: el número de huecos es el de «?» que escribe `arbol_a_texto`."""
        for texto in ("a AND ?", "NOT ?", "↑?", "? OR ? OR a", "3s/?", "(? AND b) OR ?", "? > 3", "a"):
            with self.subTest(texto=texto):
                try:
                    r = B.texto_a_arbol(texto, VARS, [])
                except ValueError:
                    continue
                self.assertEqual(B.faltan(r), B.arbol_a_texto(r).count("?"), texto)


if __name__ == "__main__":
    unittest.main()
