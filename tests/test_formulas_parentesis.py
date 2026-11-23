"""SPAR01..SPAR04: los paréntesis de las fórmulas dibujadas (`grafcet.view.norm`) no cambian el valor al leerlas (V2-E9)."""
import unittest

from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import IdGenerator
from grafcet.notation import a_nucleo
from grafcet.view import norm


def editor():
    ed = Editor(new_grafcet_document("par"), ids=IdGenerator("p-"))
    for nombre in ("a", "b", "c"):
        ed.add_variable(nombre, "input", {"kind": "int"})
    for nombre in ("p", "q"):
        ed.add_variable(nombre, "input", {"kind": "bool"})
    ed.add_step("g", "0", True, at=(240, 100))
    return ed


def significado(ed, texto):
    expr, diag = ed._make_expr(ed.model, a_nucleo(texto, [s["label"] for s in ed.model["steps"]], [v["name"] for v in ed.model["variables"]]), None)
    assert diag is None and expr["mode"] == "executable", (texto, diag)
    return expr["meaning"]


def dibujado(m, ed=None):
    """Lo que se dibuja de un significado, con los nombres de las variables y de la etapa (como en la ventana)."""
    nombres = {x["id"]: x.get("name") or x["label"] for x in ((ed or EDITOR).model["variables"] + (ed or EDITOR).model["steps"])}
    return "".join(s["t"] for s in norm(m, False, nombres))


def al_usuario(texto):
    """Lo dibujado, escrito como lo teclearía quien lo lee (para volver a interpretarlo): − → -, · → * y, en lógica, · → AND y + → OR."""
    return texto.replace("−", "-").replace("·", " * ")


def al_usuario_logico(texto):
    return texto.replace("·", " AND ").replace(" + ", " OR ")


EDITOR = editor()


class Parentesis(unittest.TestCase):
    def test_SPAR01_los_hijos_derechos_no_asociativos_llevan_parentesis_y_los_demas_no(self):
        """REQ-EXP-01: `a − (b + c)`, `a / (b · c)` y `a · (b / c)` se dibujan con paréntesis; `a − b + c`, `(a + b) − c`, `a · (b + c)` y los asociativos, como siempre."""
        ed = editor()
        esperado = {
            "a - (b + c)": "a − (b + c)",
            "a - b + c": "a − b + c",
            "(a + b) - c": "a + b − c",
            "a - (b - c)": "a − (b − c)",
            "a - b - c": "a − b − c",
            "a / (b * c)": "a/(b·c)",
            "a / b * c": "a/b·c",
            "a / (b / c)": "a/(b/c)",
            "a * (b + c)": "a·(b + c)",
            "a * (b / c)": "a·(b/c)",
            "a * b * c": "a·b·c",
            "a * (b * c)": "a·b·c",
            "a + (b + c)": "a + b + c",
            "a + (b - c)": "a + b − c",
            "a - b * c": "a − b·c",
            "(a - b) * c": "(a − b)·c",
            "-(a + b)": "−(a + b)",
            "-a": "−a",
            "-a + b": "−a + b",
        }
        for texto, dibujo in esperado.items():
            with self.subTest(texto=texto):
                self.assertEqual(dibujado(significado(ed, texto)), dibujo)

    def test_SPAR02_lo_dibujado_vuelve_a_dar_el_mismo_significado(self):
        """REQ-EXP-01: el texto dibujado de una fórmula aritmética, tecleado de nuevo, da el mismo árbol (ida y vuelta por el texto)."""
        ed = editor()
        for texto in ("a - (b + c)", "a - b + c", "a / (b * c)", "(a + b) - c", "a * (b + c)", "a * (b / c)", "a / (b / c)",
                      "a - (b - c)", "-(a + b)", "a - (b * c) - c", "(a - b) / (c - a)"):
            with self.subTest(texto=texto):
                m = significado(ed, texto)
                de_vuelta = significado(ed, al_usuario(dibujado(m)))
                self.assertEqual(de_vuelta, m, (texto, dibujado(m)))

    def test_SPAR03_la_base_de_un_retardo_lleva_parentesis_si_no_es_un_operando_simple(self):
        """REQ-TMP-03: `3s/(p + q)` se dibuja con paréntesis; una variable, una etapa, un flanco o una negación de un operando simple, sin ellos."""
        ed = editor()
        esperado = {
            "3s/(p OR q)": "3s/(p + q)",
            "3s/(p AND q)": "3s/(p·q)",
            "3s/(p OR q)/2s": "3s/(p + q)/2s",
            "3s/p": "3s/p",
            "p/2s": "p/2s",
            "3s/NOT p": "3s/p",
            "3s/NOT (p AND q)": "3s/(p·q)",
            "3s/↑p": "3s/↑p",
            "3s/X0": "3s/X0",
        }
        for texto, dibujo in esperado.items():
            with self.subTest(texto=texto):
                m = significado(ed, texto)
                self.assertEqual(dibujado(m).replace(" ", ""), dibujo.replace(" ", ""))
        # la negación de una suma lleva su paréntesis aunque la barra cubra todo
        self.assertTrue(dibujado(significado(ed, "3s/NOT (p AND q)")).startswith("3s/("))

    def test_SPAR04_un_retardo_dibujado_vuelve_a_dar_el_mismo_significado(self):
        """REQ-TMP-03: el texto dibujado de un retardo sobre una base compuesta, tecleado de nuevo, da el mismo árbol."""
        ed = editor()
        for texto in ("3s/(p OR q)", "3s/(p AND q)", "3s/(p OR q)/2s", "3s/p", "p/2s"):
            with self.subTest(texto=texto):
                m = significado(ed, texto)
                de_vuelta = significado(ed, al_usuario_logico(dibujado(m)))
                self.assertEqual(de_vuelta, m, (texto, dibujado(m)))


if __name__ == "__main__":
    unittest.main()
