"""SP8F: ida y vuelta de las fórmulas por el programador de bloques (E8, red de seguridad de P0).

REQ-EDT-02, REQ-EDT-09: el texto guardado de una fórmula entra por `texto_a_arbol` y sale por `arbol_a_texto`. Cambiar el
aspecto del formulador no puede cambiar lo que significa ni lo que se guarda. Corpus: todas las expresiones de los
`.grafnet` de `tests/fixtures/` y de los ejemplos (`grafcet.examples.EJEMPLOS`, con los didácticos): 467 fórmulas.
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from escritorio.bloques import Programador, _etiquetas, arbol_a_texto, texto_a_arbol
    from escritorio.proyecto_archivo import abrir_grafnet
    from escritorio.sello import CLAVE
    from grafcet import expressions as ex
    from grafcet.builder import M
    from grafcet.examples import EJEMPLOS
    from grafcet.notation import a_nucleo, a_usuario, x_etapa
    from grafcet.persistence import open_model

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HUECO = "__hueco__"
# Fórmulas guardadas que el programador escribe distinto al pasarlas por bloques (texto guardado -> texto escrito): comillas
# innecesarias, duraciones en su unidad natural y el flanco de un nombre sin paréntesis. Es la conducta de hoy y no estropea
# nada (el panel no escribe al abrir, SP8F04). Si cambia el estilo de escritura, esta lista salta. 68 distintas, 71 usos.
NORMALIZACIONES = {
    '0.75s/(`Caja en T1`)': '750ms/(`Caja en T1`)',
    '0.75s/X2': '750ms/X2',
    '1.0s/X12': '1s/X12',
    '1.0s/X14': '1s/X14',
    '1.1s/X22': '1100ms/X22',
    '1.1s/X24': '1100ms/X24',
    '1.2s/X32': '1200ms/X32',
    '1.2s/X34': '1200ms/X34',
    '1.3s/X42': '1300ms/X42',
    '1.3s/X44': '1300ms/X44',
    '1.4s/X52': '1400ms/X52',
    '1.4s/X54': '1400ms/X54',
    '1.5s/X62': '1500ms/X62',
    '1.5s/X64': '1500ms/X64',
    '1.6s/X72': '1600ms/X72',
    '1.6s/X74': '1600ms/X74',
    '1.7s/X82': '1700ms/X82',
    '1.7s/X84': '1700ms/X84',
    '1.8s/X92': '1800ms/X92',
    '1.8s/X94': '1800ms/X94',
    '1.9s/X102': '1900ms/X102',
    '1.9s/X104': '1900ms/X104',
    '2.0s/X112': '2s/X112',
    '2.0s/X114': '2s/X114',
    '2.0s/X16': '2s/X16',
    '2.0s/X19': '2s/X19',
    '2.1s/X122': '2100ms/X122',
    '2.1s/X124': '2100ms/X124',
    '2.1s/X26': '2100ms/X26',
    '2.1s/X29': '2100ms/X29',
    '2.2s/X36': '2200ms/X36',
    '2.2s/X39': '2200ms/X39',
    '2.3s/X46': '2300ms/X46',
    '2.3s/X49': '2300ms/X49',
    '2.4s/X56': '2400ms/X56',
    '2.4s/X59': '2400ms/X59',
    '2.5s/X66': '2500ms/X66',
    '2.5s/X69': '2500ms/X69',
    '2.6s/X76': '2600ms/X76',
    '2.6s/X79': '2600ms/X79',
    '2.7s/X86': '2700ms/X86',
    '2.7s/X89': '2700ms/X89',
    '2.8s/X96': '2800ms/X96',
    '2.8s/X99': '2800ms/X99',
    '2.9s/X106': '2900ms/X106',
    '2.9s/X109': '2900ms/X109',
    '3.0s/X116': '3s/X116',
    '3.0s/X119': '3s/X119',
    '3.0s/X18': '3s/X18',
    '3.1s/X126': '3100ms/X126',
    '3.1s/X129': '3100ms/X129',
    '3.1s/X28': '3100ms/X28',
    '3.2s/X38': '3200ms/X38',
    '3.3s/X48': '3300ms/X48',
    '3.4s/X58': '3400ms/X58',
    '3.5s/X68': '3500ms/X68',
    '3.6s/X78': '3600ms/X78',
    '3.7s/X88': '3700ms/X88',
    '3.8s/X98': '3800ms/X98',
    '3.9s/X108': '3900ms/X108',
    '4.0s/X118': '4s/X118',
    '4.1s/X128': '4100ms/X128',
    'NOT `Paro`': 'NOT Paro',
    '`Parpadeo`': 'Parpadeo',
    '`Parpadeo` AND X34': 'Parpadeo AND X34',
    '`Parpadeo` AND X60': 'Parpadeo AND X60',
    '`Seta emergencia` AND ↑(`Rearme`)': '`Seta emergencia` AND ↑Rearme',
    '↑(`Marcha`) AND `Paro` AND `Seta emergencia`': '↑Marcha AND Paro AND `Seta emergencia`',
}
USOS_NORMALIZADOS = 71


def documentos():
    """(nombre, documento) de todos los proyectos del corpus."""
    out = []
    for ruta in sorted(FIXTURES.rglob("*.grafnet")):
        contenedor = abrir_grafnet(ruta, CLAVE)
        try:
            out.append((ruta.name, open_model(contenedor.raiz).doc))
        finally:
            contenedor.cerrar()
    for clave, (_, _, constructor) in EJEMPLOS.items():
        m, _layout = constructor()
        out.append((clave, m.doc if isinstance(m, M) else m))
    return out


def contexto(doc):
    return ({v["name"]: (v["role"], v["type"]["kind"]) for v in doc["variables"]},
            [x_etapa(s["label"]) for s in doc["steps"]])


def significado(texto, variables, etapas):
    """El significado que el núcleo da al texto del usuario (las referencias se comparan por nombre)."""
    def resuelve(clase, nombre):
        if (clase == "var" and nombre in variables) or nombre == HUECO:
            return nombre
        if clase == "step":
            return "etapa:" + nombre
        raise ex.Unresolved(clase, nombre)
    t = texto.strip().replace("?", HUECO)
    return ex.parse(a_nucleo(t, _etiquetas(list(etapas)), list(variables) + [HUECO]), resuelve)


def ida_y_vuelta(texto, variables, etapas):
    return arbol_a_texto(texto_a_arbol(texto, variables, etapas))


def _atomo(azar):
    return azar.choice(["a", "b", "c", "Q1", "M1", "X0", "X1", "X2", "1", "0", "?", "CT >= 3", "N = 0", "N != CT"])


def _formula(azar, prof):
    """Una fórmula al azar en notación de usuario (con los paréntesis que hacen falta)."""
    if prof == 0 or azar.random() < 0.25:
        return _atomo(azar)
    sub = lambda: _formula(azar, prof - 1)  # noqa: E731
    k = azar.choice(["and", "or", "not", "sube", "baja", "par", "t1", "t2", "t12", "and", "or"])
    if k in ("and", "or"):
        return f" {k.upper()} ".join(f"({sub()})" for _ in range(azar.choice([2, 2, 3])))
    if k == "not":
        return f"NOT ({sub()})"
    if k == "sube":
        return f"↑({sub()})"
    if k == "baja":
        return f"↓({sub()})"
    if k == "par":
        return f"({sub()})"
    d = azar.choice(["3s", "500ms", "1.5s", "200ms"])
    return {"t1": f"{d}/({sub()})", "t2": f"({sub()})/{d}", "t12": f"{d}/({sub()})/{d}"}[k]


@unittest.skipUnless(QT, "requiere PySide6")
class FormulasIdaYVuelta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.formulas = [(nom, d, a_usuario(e["text"])) for nom, d in documentos() for e in d["expressions"]]

    def test_SP8F01_corpus_completo(self):
        """REQ-EDT-02: el corpus son las 467 fórmulas de los .grafnet de pruebas y los ejemplos (si cambia, se revisa)."""
        self.assertEqual(len(self.formulas), 467)

    def test_SP8F02_todo_se_analiza_y_conserva_el_significado(self):
        """REQ-EDT-02, REQ-EDT-09: texto -> bloques -> texto da el mismo significado en el núcleo, en todas."""
        for nom, doc, t in self.formulas:
            variables, etapas = contexto(doc)
            with self.subTest(proyecto=nom, texto=t):
                escrito = ida_y_vuelta(t, variables, etapas)
                self.assertEqual(significado(escrito, variables, etapas), significado(t, variables, etapas))

    def test_SP8F03_idempotente_y_normalizaciones_conocidas(self):
        """REQ-EDT-02: escribir dos veces da lo mismo que escribir una; solo cambian las normalizaciones conocidas."""
        distintas = 0
        for nom, doc, t in self.formulas:
            variables, etapas = contexto(doc)
            escrito = ida_y_vuelta(t, variables, etapas)
            with self.subTest(proyecto=nom, texto=t):
                self.assertEqual(ida_y_vuelta(escrito, variables, etapas), escrito)
                self.assertEqual(NORMALIZACIONES.get(t, t), escrito)
                distintas += escrito != t
        self.assertEqual(distintas, USOS_NORMALIZADOS)

    def test_SP8F04_abrir_no_cambia_lo_guardado(self):
        """REQ-EDT-09: `poner` muestra el texto guardado como bloques sin emitir `cambiado` (no escribe nada al abrir)."""
        por_doc = {}
        for nom, doc, t in self.formulas:
            por_doc.setdefault(nom, (doc, []))[1].append(t)
        for nom, (doc, textos) in por_doc.items():
            variables, etapas = contexto(doc)
            p = Programador(lambda v=variables, e=etapas: (v, e))
            self.addCleanup(p.close)
            emitidas = []
            p.cambiado.connect(lambda *_: emitidas.append(1))
            for t in textos:
                p.poner(t)
            with self.subTest(proyecto=nom):
                self.assertEqual(emitidas, [])

    def test_SP8F05_al_azar_con_semilla_fija(self):
        """REQ-EDT-02, REQ-EDT-09: 10 000 fórmulas al azar (Y, O, NOT, flancos, grupos, retardos, comparaciones, constantes,
        huecos) son idempotentes y conservan su significado."""
        variables = {"a": ("input", "bool"), "b": ("input", "bool"), "c": ("input", "bool"), "Q1": ("output", "bool"),
                     "M1": ("internal", "bool"), "CT": ("internal", "int"), "N": ("input", "int")}
        etapas = ["X0", "X1", "X2"]
        azar = random.Random(20261123)
        hechas = 0
        for _ in range(10000):
            t = _formula(azar, 4)
            if t.strip() == "?":
                continue  # un hueco solo es «sin fórmula»: texto vacío, como hoy
            try:
                escrito = ida_y_vuelta(t, variables, etapas)
            except ValueError:
                continue  # texto que el analizador rechaza: no es de la prueba
            hechas += 1
            self.assertEqual(ida_y_vuelta(escrito, variables, etapas), escrito, t)
            self.assertEqual(significado(escrito, variables, etapas), significado(t, variables, etapas), t)
        self.assertGreater(hechas, 9000)


if __name__ == "__main__":
    unittest.main()
