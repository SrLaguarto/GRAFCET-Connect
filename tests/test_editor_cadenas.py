"""Edición del dibujo (encargo A2): mover varios elementos a la vez, equidistanciar alturas de las cadenas, quitar solo la
acción o la orden señalada con Supr, la orden de forzado como ficha de la paleta y las barras de simultaneidad (Y).

Las pruebas del núcleo (SEDI220..) no necesitan Qt: `Editor.move_many`, `Editor.equidistribute` y `Editor.chains`, y el
enlazado de las barras (`bar_link`). Las de la interfaz (SEDI230..) se omiten si PySide6 no está instalado y usan la
plataforma «offscreen»: ejercen los gestos de `Edicion` (`prensar`, `mover`, `soltar`, `menu`, `colocar`, `sobrevolar`,
`doble`, `borrar`) sobre un dibujo real. Ninguna es oráculo del documento 11: comprueban que el editor usa las operaciones
de grafcet/editor.py, que solo cambia la presentación donde se dice y que cada gesto es una sola operación de deshacer.
"""
import copy
import os
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import S, records, session  # noqa: E402

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.editor import Editor, new_grafcet_document  # noqa: E402
from grafcet.ids import IdGenerator  # noqa: E402
from grafcet.model import validate_model  # noqa: E402
from grafcet.view import layout_from_presentation  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path("C:/Windows/Fonts").is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    from PySide6.QtCore import QMimeData, QPointF, QRectF, QSettings, Qt
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

DY = 80  # la distancia estándar entre una etapa y su transición (escritorio.edicion.DY)


# ------------------------------------------------------------------------------------------------------ ayudas del núcleo
def nuevo():
    return Editor(new_grafcet_document("m"), ids=IdGenerator("x"))


def entradas(ed, *nombres):
    return {n: ed.add_variable(n, "input", {"kind": "bool"}) for n in nombres}


def posiciones(ed):
    return layout_from_presentation(ed.presentation)


def etiquetas(doc):
    """Nombre de cada elemento (variable, etapa, parcial, macroetapa, transición): los ID del editor no se comparan."""
    out = {v["id"]: v["name"] for v in doc["variables"]}
    for coll in ("steps", "partials"):
        out.update({x["id"]: x["label"] for x in doc[coll]})
    out.update({x["id"]: x["label"] for x in doc["hierarchy"]["macros"]})
    out.update({t["id"]: t.get("label", t["id"]) for t in doc["transitions"]})
    return out


def corrida(doc, guion, init=None):
    """Simula `doc` con el guion [(segundos, {entrada: valor})]: la situación (con nombres) tras cada instante y las
    transiciones que franquea cada evolución."""
    res = validate_model(doc)
    assert res.can_simulate, [str(d) for d in res.diagnostics]
    nombre = etiquetas(doc)
    por_nombre = {v["name"]: v["id"] for v in doc["variables"]}
    s = session(res.model, init={por_nombre[k]: v for k, v in (init or {}).items()},
                batches=[(t * S, 0, {por_nombre[k]: v for k, v in ch.items()}) for t, ch in guion])
    situaciones = [sorted(nombre[i] for i in s.z.situation)]
    for t, _ in guion:
        s.advance_to(t * S)
        situaciones.append(sorted(nombre[i] for i in s.z.situation))
    return situaciones, [sorted(nombre[t] for t in r["cleared"]) for r in records(s, "evolucion")]


def cadena_lineal(y=(60, 170, 253, 305, 470, 530), x=0):
    """0 -t1- 1 -t2- 2 -t3-> (0): tres etapas y tres transiciones con distancias verticales irregulares; t3 vuelve a 0."""
    ed = nuevo()
    entradas(ed, "a", "b", "c")
    s0 = ed.add_step("g", "0", True, at=(x, y[0]))
    t1, _ = ed.add_transition("g", "a", pre=[s0], at=(x, y[1]), label="t1")
    s1 = ed.add_step("g", "1", at=(x, y[2]))
    ed.connect(t1, s1)
    t2, _ = ed.add_transition("g", "b", pre=[s1], at=(x, y[3]), label="t2")
    s2 = ed.add_step("g", "2", at=(x, y[4]))
    ed.connect(t2, s2)
    t3, _ = ed.add_transition("g", "c", pre=[s2], post=[s0], at=(x, y[5]), label="t3")
    return ed, {"s0": s0, "t1": t1, "s1": s1, "t2": t2, "s2": s2, "t3": t3}


class MoverVariosEnElNucleo(unittest.TestCase):
    def test_SEDI220_mover_varios_en_una_sola_operacion_y_deshacerla_entera(self):
        """REQ-EDT-03, REQ-EDT-05, REQ-EDT-14: `move_many` mueve etapas, transiciones, barras y acciones sueltas a la vez, con
        el estilo de los enlaces que se le diga, en UNA operación de deshacer que no cambia el modelo ni su revisión; un ID
        que no existe rechaza todo sin dejar nada en el historial."""
        ed, i = cadena_lineal()
        barra = ed.add_bar("Y", (40, 200), 200)
        d1 = ed.add_draft_action((100, 60))
        d2 = ed.add_draft_action((100, 60), {"grupo": "k1", "orden": 0})
        d3 = ed.add_draft_action((100, 60), {"grupo": "k1", "orden": 1})
        enlace = f"{i['t1']}|{i['s0']}|pre"
        ed.set_link_style(enlace, {"route": {"laneX": "100", "exitY": "100", "entryY": "130"}, "arrows": {"flow": {"visible": True}}})
        revision, modelo = ed.revision, copy.deepcopy(ed.model)
        antes, n = copy.deepcopy(ed.presentation), len(ed.undo_stack)
        ed.move_many({i["s0"]: (20, 80), i["t1"]: (20, 160), barra: (60, 220), d1: (120, 80), d2: (140, 100), d3: (140, 100)},
                     {enlace: {"route": {"laneX": "120", "exitY": "120", "entryY": "150"}}, f"{i['t2']}|{i['s1']}|pre": None})
        self.assertEqual(len(ed.undo_stack), n + 1, "una sola operación")
        pos = posiciones(ed)
        self.assertEqual((pos[i["s0"]], pos[i["t1"]], pos[i["s1"]]), ((20.0, 80.0), (20.0, 160.0), (0.0, 253.0)))
        b = next(x for x in ed.bars() if x["id"] == barra)
        self.assertEqual((b["x"], b["y"], b["ancho"]), ("60", "220", "200"), "la barra se mueve y conserva su ancho")
        sueltas = {d["id"]: (d["x"], d["y"]) for d in ed.draft_actions()}
        self.assertEqual(sueltas, {d1: ("120", "80"), d2: ("140", "100"), d3: ("140", "100")})
        self.assertEqual(ed.link_styles()[enlace], {"route": {"laneX": "120", "exitY": "120", "entryY": "150"}},
                         "el estilo nuevo sustituye al anterior")
        self.assertEqual((ed.model, ed.revision), (modelo, revision), "solo presentación")
        ed.undo()
        self.assertEqual((ed.presentation, len(ed.undo_stack)), (antes, n), "deshacer devuelve todo de una vez")
        ed.redo()
        self.assertEqual(posiciones(ed)[i["s0"]], (20.0, 80.0))
        # un ID que no existe: se rechaza todo, sin historial
        ed.undo()
        n, antes = len(ed.undo_stack), copy.deepcopy(ed.presentation)
        with self.assertRaises(DiagnosticError) as exc:
            ed.move_many({i["s0"]: (999, 999), "no-existe": (1, 1)})
        self.assertEqual(exc.exception.diagnostics[0].code, "D-REF")
        self.assertEqual((ed.presentation, len(ed.undo_stack)), (antes, n))

    def test_SEDI221_mover_varios_crea_la_posicion_que_falta_y_quita_estilos(self):
        """REQ-EDT-03, REQ-EDT-14: un elemento sin posición guardada (por ejemplo un recinto vacío) la recibe al moverse; un
        estilo de enlace puesto a None desaparece; no se crea un `linkStyles` vacío si no hay estilos que cambiar."""
        ed = nuevo()
        s0 = ed.add_step("g", "0", True)
        ed.move_many({s0: (40, 60)})
        self.assertEqual(posiciones(ed), {s0: (40.0, 60.0)})
        self.assertNotIn("linkStyles", ed.presentation)
        ed.set_link_style("x|y|pre", {"route": {"middleY": "100"}})
        ed.move_many({s0: (40, 80)}, {"x|y|pre": None})
        self.assertEqual(ed.link_styles(), {})


class EquidistanciarEnElNucleo(unittest.TestCase):
    def test_SEDI222_cadena_lineal_con_distancias_irregulares_queda_a_la_distancia_estandar(self):
        """REQ-EDT-03, REQ-EDT-14: una cadena de etapas y transiciones con distancias irregulares queda con la misma
        distancia estándar entre niveles consecutivos, el primer nivel donde estaba el más alto, la x de cada elemento sin
        cambiar y todo en la rejilla; es UNA operación de deshacer, solo presentación (el modelo no cambia), y aplicada otra
        vez no hace nada. El enlace que vuelve (t3 a la etapa 0) no cuenta para los niveles."""
        ed, i = cadena_lineal(x=40)
        modelo, revision = copy.deepcopy(ed.model), ed.revision
        diagnosticos = [str(d) for d in ed.validate().diagnostics]
        antes, n = copy.deepcopy(ed.presentation), len(ed.undo_stack)
        movidos = ed.equidistribute([i["s1"]], DY)
        pos = posiciones(ed)
        orden = ["s0", "t1", "s1", "t2", "s2", "t3"]
        self.assertEqual([pos[i[k]][1] for k in orden], [60.0, 140.0, 220.0, 300.0, 380.0, 460.0])
        self.assertEqual({pos[i[k]][0] for k in orden}, {40.0}, "la x no cambia")
        self.assertEqual(sorted(movidos), sorted(i[k] for k in orden[1:]), "solo se mueve lo que cambia de altura")
        self.assertTrue(all(y % 20 == 0 for _, y in pos.values()), "en la rejilla")
        self.assertEqual(len(ed.undo_stack), n + 1, "una sola operación de deshacer")
        self.assertEqual((ed.model, ed.revision), (modelo, revision), "el modelo no cambia")
        self.assertEqual([str(d) for d in ed.validate().diagnostics], diagnosticos)
        self.assertEqual(Editor._index(ed.model).keys(), Editor._index(modelo).keys())
        despues, pila = copy.deepcopy(ed.presentation), len(ed.undo_stack)
        self.assertEqual(ed.equidistribute([i["s1"]], DY), [], "idempotente: la segunda vez no cambia nada")
        self.assertEqual(ed.equidistribute(None, DY), [])
        self.assertEqual((ed.presentation, len(ed.undo_stack)), (despues, pila), "ni siquiera una operación vacía")
        ed.undo()
        self.assertEqual((ed.presentation, len(ed.undo_stack)), (antes, n))

    def test_SEDI223_la_cadena_se_alcanza_desde_cualquier_elemento_enlace_o_parcial_y_las_aisladas_no_cuentan(self):
        """REQ-EDT-03, REQ-EDT-14: la cadena de un elemento es la componente conexa de etapas, macroetapas y transiciones
        enlazados dentro de su parcial; se alcanza desde cualquiera de sus elementos, desde un enlace (por cualquier extremo) o
        desde su parcial; con `None`, todas; una etapa o una transición sin enlaces no es una cadena y no se toca. Cada cadena
        conserva su primer nivel."""
        ed, i = cadena_lineal(x=0)
        j = {}
        j["u0"] = ed.add_step("g", "7", True, at=(400, 100))
        j["tu"], _ = ed.add_transition("g", "a", pre=[j["u0"]], at=(400, 190), label="tu")
        j["u1"] = ed.add_step("g", "8", at=(400, 233))
        ed.connect(j["tu"], j["u1"])
        sola = ed.add_step("g", "9", at=(700, 33))
        casilla, _ = ed.add_transition("g", "a", pre=[sola], at=(700, 77), label="tz")
        suelta, _ = ed.add_transition("g", "a", at=(900, 17), label="tf")  # una transición sin ningún enlace
        cadenas = ed.chains()
        self.assertEqual(sorted(len(c) for c in cadenas), [2, 3, 6], "tres cadenas: la lineal, la de dos y la de tres")
        self.assertEqual(ed.chains([i["t2"]]), ed.chains([f"{i['t2']}|{i['s2']}|post"]), "por un enlace")
        self.assertEqual(sorted(ed.chains([i["s2"]])[0]), sorted(i[k] for k in ("s0", "t1", "s1", "t2", "s2", "t3")))
        self.assertEqual(ed.chains(["g"]), cadenas, "por el parcial: todas las suyas")
        self.assertEqual([sorted(c) for c in ed.chains([sola])], [sorted([sola, casilla])], "una etapa y su transición ya son una")
        self.assertEqual(ed.chains([suelta]), [], "una transición sin enlaces no es una cadena")
        antes = posiciones(ed)
        ed.equidistribute([j["tu"]], DY)  # solo la cadena de 7-tu-8
        despues = posiciones(ed)
        self.assertEqual({k for k in despues if despues[k] != antes[k]}, {j["tu"], j["u1"]}, "solo se mueve lo de esa cadena")
        self.assertEqual((despues[j["u0"]], despues[j["tu"]], despues[j["u1"]]), ((400.0, 100.0), (400.0, 180.0), (400.0, 260.0)),
                         "el primer nivel se queda donde está (en la rejilla): la etapa 7 estaba en 100")
        self.assertTrue(all(despues[k] == antes[k] for k in i.values()), "la otra cadena, intacta")
        ed.equidistribute(None, DY)
        pos = posiciones(ed)
        self.assertEqual([pos[i[k]][1] for k in ("s0", "t1", "s1", "t2", "s2", "t3")], [60.0, 140.0, 220.0, 300.0, 380.0, 460.0])
        self.assertEqual((pos[sola], pos[casilla]), ((700.0, 40.0), (700.0, 120.0)), "la de 9-tz, un nivel cada una")
        self.assertEqual(pos[suelta], (900.0, 17.0), "la transición sin enlaces no es una cadena: no se toca")
        self.assertEqual(ed.equidistribute(None, DY), [], "idempotente")

    def test_SEDI224_una_etapa_con_muchas_acciones_aumenta_la_distancia_con_el_nivel_siguiente(self):
        """REQ-EDT-03, REQ-ACT-01: lo que sobresale por debajo de una etapa (`extent`, el alto de sus acciones en columna) pide
        más separación con el nivel siguiente: la suma de lo que sobresale arriba y abajo y el margen, en múltiplos de la
        rejilla y nunca menos que la distancia estándar; los demás niveles no cambian; idempotente."""
        ed, i = cadena_lineal(y=(60, 100, 150, 400, 450, 500))
        ext = {i["s1"]: (22, 134), i["t2"]: (12, 12), i["t1"]: (12, 12)}  # tres acciones en columna: llegan a 134 por debajo
        ed.equidistribute(None, DY, extent=ext, margin=8, grid=20)
        pos = posiciones(ed)
        ys = [pos[i[k]][1] for k in ("s0", "t1", "s1", "t2", "s2", "t3")]
        self.assertEqual(ys, [60.0, 140.0, 220.0, 380.0, 460.0, 540.0], "de la etapa 1 a t2: 8 + 134 + 12 = 154, a 160")
        self.assertTrue(ys[3] - ys[2] >= 134 + 12 + 8, "no se solapan con lo del nivel siguiente")
        self.assertEqual([b - a for a, b in zip(ys, ys[1:])], [80.0, 80.0, 160.0, 80.0, 80.0])
        n = len(ed.undo_stack)
        self.assertEqual(ed.equidistribute(None, DY, extent=ext, margin=8, grid=20), [])
        self.assertEqual(len(ed.undo_stack), n)
        # una etapa cuyas acciones caben (una fila: 22 por debajo) no cambia la distancia estándar
        ed2, i2 = cadena_lineal(y=(60, 100, 150, 400, 450, 500))
        ed2.equidistribute(None, DY, extent={i2["s1"]: (22, 42), i2["t2"]: (12, 12)}, margin=8, grid=20)
        pos2 = posiciones(ed2)
        self.assertEqual([pos2[i2[k]][1] for k in ("s0", "t1", "s1", "t2", "s2", "t3")], [60, 140, 220, 300, 380, 460])

    def test_SEDI225_alternativas_y_simultaneidad_con_barras_a_mitad_de_la_distancia(self):
        """REQ-EDT-03, REQ-MOD-03: las ramas de una alternativa quedan al mismo nivel; en una simultaneidad, las etapas de una
        misma barra también, y cada barra va a mitad de la distancia que le toca, en la rejilla, con su x y su ancho sin
        cambiar; la barra se alcanza por su ID y no cambia los enlaces del modelo."""
        ed = nuevo()
        entradas(ed, "p", "q", "r")
        s0 = ed.add_step("g", "0", True, at=(100, 17))
        ta, _ = ed.add_transition("g", "p", pre=[s0], at=(100, 55), label="ta")
        a, b = ed.add_step("g", "A", at=(60, 130)), ed.add_step("g", "B", at=(260, 160))
        c = ed.add_step("g", "C", at=(100, 400))
        bar1 = ed.add_bar("Y", (0, 90), 300)
        bar2 = ed.add_bar("Y", (0, 330), 300)
        tb, _ = ed.add_transition("g", "q", at=(100, 365), label="tb")
        ed.bar_link(bar1, "arriba", ta)
        for x in (a, b):
            ed.bar_link(bar1, "abajo", x)
            ed.bar_link(bar2, "arriba", x)
        ed.bar_link(bar2, "abajo", tb)
        ed.connect(tb, c)
        tc, _ = ed.add_transition("g", "r", pre=[c], post=[s0], at=(100, 450), label="tc")
        modelo = copy.deepcopy(ed.model)
        movidos = ed.equidistribute([bar1], DY)
        pos = posiciones(ed)
        niveles = [pos[k][1] for k in (s0, ta, a, b, tb, c, tc)]
        self.assertEqual(niveles, [20.0, 100.0, 180.0, 180.0, 260.0, 340.0, 420.0], "A y B al mismo nivel; 20 es la rejilla")
        self.assertEqual({pos[k][0] for k in (a, b)}, {60.0, 260.0}, "la x de cada uno no cambia")
        barras = {x["id"]: x for x in ed.bars()}
        self.assertEqual([(barras[k]["x"], barras[k]["ancho"]) for k in (bar1, bar2)], [("0", "300"), ("0", "300")])
        self.assertEqual([barras[bar1]["y"], barras[bar2]["y"]], ["140", "220"],
                         "cada barra, justo a mitad de los niveles de sus elementos de arriba y de abajo")
        self.assertIn(bar1, movidos)
        self.assertEqual(ed.model, modelo, "los enlaces del modelo no cambian")
        self.assertEqual(ed.equidistribute(None, DY), [], "idempotente")
        # una barra con su hueco par aunque la distancia haya crecido por lo que sobresale
        ed.equidistribute(None, DY, extent={a: (22, 94), ta: (12, 12), tb: (12, 12)}, margin=8, grid=20)
        pos = posiciones(ed)
        hueco = pos[tb][1] - pos[a][1]
        self.assertEqual((hueco, hueco % 40), (120.0, 0.0), "8 + 94 + 12 = 114, y la barra de abajo lo pide par: 120")
        barras = {x["id"]: x for x in ed.bars()}
        self.assertEqual(Fraction(barras[bar2]["y"]), pos[a][1] + hueco / 2)

    def test_SEDI226_el_enlace_de_realimentacion_y_las_rutas_manuales(self):
        """REQ-EDT-03, REQ-EDT-14: el enlace que vuelve hacia arriba no cuenta para los niveles (una repetición de secuencia no
        pone la etapa de destino debajo de su origen); de la ruta manual de un enlace con un extremo que se mueve se descartan
        las alturas absolutas (exitY, entryY, middleY) y se conserva laneX; una ruta que no se toca, igual; todo se deshace."""
        ed = nuevo()
        entradas(ed, "p")
        etapas = [ed.add_step("g", str(k), k == 0, at=(0, y)) for k, y in enumerate((60, 120, 200, 300))]
        ts = []
        for k in range(3):
            t, _ = ed.add_transition("g", "p", pre=[etapas[k]], at=(0, (70, 160, 250)[k]), label=f"t{k + 1}")
            ed.connect(t, etapas[k + 1])
            ts.append(t)
        retorno, _ = ed.add_transition("g", "p", pre=[etapas[3]], post=[etapas[1]], at=(0, 330), label="t4")
        mover = f"{retorno}|{etapas[1]}|post"
        quieta = f"{ts[0]}|{etapas[0]}|pre"
        ed.set_link_style(mover, {"route": {"laneX": "-60", "exitY": "400", "entryY": "90"}, "arrows": {"flow": {"visible": True}}})
        ed.set_link_style(quieta, {"route": {"middleY": "65"}})
        ed.equidistribute(None, DY)
        pos = posiciones(ed)
        self.assertEqual([pos[k][1] for k in (etapas[0], ts[0], etapas[1], ts[1], etapas[2], ts[2], etapas[3], retorno)],
                         [60.0, 140.0, 220.0, 300.0, 380.0, 460.0, 540.0, 620.0],
                         "siete niveles: el enlace t4 -> 1 es de realimentación y no cuenta")
        self.assertEqual(ed.link_styles()[mover], {"route": {"laneX": "-60"}, "arrows": {"flow": {"visible": True}}},
                         "sin las alturas absolutas; sigue la vía por la izquierda y la flecha")
        self.assertNotIn(quieta, ed.link_styles(), "t1 y la etapa 0 se movieron: su ruta de altura también se descarta")
        ed.undo()
        self.assertEqual(ed.link_styles()[mover]["route"]["exitY"], "400")
        self.assertEqual(ed.link_styles()[quieta], {"route": {"middleY": "65"}})

    def test_SEDI227_una_cadena_sin_enlaces_con_otras_partes_y_los_parciales_no_se_mezclan(self):
        """REQ-EDT-03, REQ-JER-04: un enlace entre elementos de parciales distintos no los une en una cadena (cada una se reparte
        dentro de su parcial); la expansión de una macroetapa y el raíz, a su altura cada una; el primer nivel de cada cadena
        se conserva."""
        ed = nuevo()
        entradas(ed, "p")
        a = ed.add_step("g", "A", True, at=(0, 60))
        mac = ed.add_macro("g", "M", at=(0, 300))
        t, _ = ed.add_transition("g", "p", pre=[a], post=[mac.macro], at=(0, 150), label="t")
        k = ed.add_step(mac.partial, "K", at=(300, 530))
        ed.move(mac.entry, 300, 400)
        ed.move(mac.exit, 300, 700)
        te, _ = ed.add_transition(mac.partial, "p", pre=[mac.entry], post=[k], at=(300, 440), label="te")
        ts, _ = ed.add_transition(mac.partial, "p", pre=[k], post=[mac.exit], at=(300, 600), label="ts")
        self.assertEqual(sorted(len(c) for c in ed.chains()), [3, 5], "la del raíz (A, t, M) y la de la expansión")
        ed.equidistribute(None, DY)
        pos = posiciones(ed)
        self.assertEqual([pos[x][1] for x in (a, t, mac.macro)], [60.0, 140.0, 220.0])
        self.assertEqual([pos[x][1] for x in (mac.entry, te, k, ts, mac.exit)], [400.0, 480.0, 560.0, 640.0, 720.0],
                         "la expansión conserva su primer nivel (400)")
        self.assertEqual(ed.chains([mac.partial])[0], ed.chains([mac.entry])[0])
        raiz = ed.chains(["g"])
        self.assertEqual([sorted(c) for c in raiz], [sorted([a, t, mac.macro])], "el parcial raíz: solo la suya")


    def test_SEDI234_un_enlace_dibujado_hacia_arriba_que_no_cierra_ningun_ciclo_cuenta_como_descendente(self):
        """REQ-EDT-03, REQ-EDT-14: solo es de realimentación el enlace que vuelve hacia arriba Y cierra un ciclo; si una transición
        está dibujada por encima de su etapa anterior pero no hay ciclo, queda debajo de ella (un enlace mal dibujado), y volver
        a equidistanciar no cambia nada (con el enlace tratado como de realimentación quedaba al mismo nivel que su etapa)."""
        ed = nuevo()
        entradas(ed, "p")
        s0 = ed.add_step("g", "0", True, at=(0, 200))
        t, _ = ed.add_transition("g", "p", pre=[s0], at=(0, 100), label="t")  # por encima de la etapa de la que sale
        s1 = ed.add_step("g", "1", at=(0, 300))
        ed.connect(t, s1)
        ed.equidistribute(None, DY)
        pos = posiciones(ed)
        self.assertEqual([pos[k][1] for k in (s0, t, s1)], [100.0, 180.0, 260.0], "desde el más alto, un nivel cada uno")
        self.assertEqual(ed.equidistribute(None, DY), [])

    def test_SEDI235_equidistanciar_cualquier_grafo_deja_la_x_en_la_rejilla_sin_tocar_el_modelo_y_es_idempotente(self):
        """REQ-EDT-03, REQ-EDT-14: con cientos de grafos al azar (varias etapas, transiciones con varias etapas antes y después,
        ciclos, barras Y y O con cualquier unión, posiciones cualesquiera y acciones que piden más altura), equidistanciar deja
        la x de cada elemento, lo movido en la rejilla, el modelo y su revisión intactos, ningún elemento enlazado a la misma
        altura que su pareja, y aplicado otra vez no hace nada (ni una operación vacía)."""
        import random
        rng = random.Random(20260430)
        for caso in range(250):
            ed = nuevo()
            entradas(ed, "p")
            n = rng.randint(2, 7)
            pasos = [ed.add_step("g", str(k), k == 0, at=(rng.choice(range(0, 600, 20)), rng.choice(range(0, 600, 10))))
                     for k in range(n)]
            ts = []
            for k in range(rng.randint(1, 8)):
                pre, post = rng.sample(pasos, rng.randint(1, min(2, n))), rng.sample(pasos, rng.randint(0, min(2, n)))
                t, _ = ed.add_transition("g", "p", pre=pre, post=post, label=f"t{k + 1}",
                                         at=(rng.choice(range(0, 600, 20)), rng.choice(range(0, 600, 10))))
                ts.append(t)
            for _ in range(rng.randint(0, 2)):
                b = ed.add_bar(rng.choice("YO"), (rng.choice(range(0, 400, 20)), rng.choice(range(0, 600, 10))), 200)
                for _ in range(rng.randint(0, 3)):
                    try:
                        ed.bar_link(b, rng.choice(["arriba", "abajo"]), rng.choice(pasos + ts))
                    except DiagnosticError:  # (el mismo elemento dos veces en la barra)
                        pass
            extension = {s: (22, rng.choice([22, 42, 78, 134])) for s in pasos if rng.random() < 0.4}
            extension.update({t: (12, 12) for t in ts})
            antes, modelo, revision = posiciones(ed), copy.deepcopy(ed.model), ed.revision
            movidos = ed.equidistribute(None, DY, extent=extension)
            despues = posiciones(ed)
            self.assertEqual((ed.model, ed.revision), (modelo, revision), caso)
            self.assertTrue(all(despues[i][0] == antes[i][0] for i in antes), caso)
            self.assertTrue(all(despues[i][1] % 20 == 0 for i in movidos if i in despues), caso)
            self.assertTrue(all(Fraction(b["y"]) % 20 == 0 for b in ed.bars() if b["id"] in movidos), caso)
            for t in ed.model["transitions"]:
                for e in t["preRefs"] + t["postRefs"]:
                    self.assertNotEqual(despues[e][1], despues[t["id"]][1], f"{caso}: enlazados a la misma altura")
            presentacion, pila = copy.deepcopy(ed.presentation), len(ed.undo_stack)
            self.assertEqual(ed.equidistribute(None, DY, extent=extension), [], caso)
            self.assertEqual((ed.presentation, len(ed.undo_stack)), (presentacion, pila), caso)


class BarrasEnElNucleo(unittest.TestCase):
    """Las barras de simultaneidad (Y): lo que `bar_link` deja en el modelo (enlaces normales de las transiciones, que son lo
    que simula el motor) con cada combinación de elementos por encima y por debajo."""

    @staticmethod
    def nombres(ed, ids):
        n = etiquetas(ed.model)
        return [n[i] for i in ids]

    def test_SEDI228_bar_link_enlaza_todas_las_parejas_aunque_alguna_sea_un_borrador(self):
        """REQ-MOD-03, REQ-EDT-14: unir un elemento a una barra enlaza en el modelo CADA pareja (arriba, abajo), también si
        otra pareja del mismo gesto queda como borrador (dos etapas, D-ALTERNANCIA): antes la primera pareja que daba un
        borrador hacía que no se enlazaran las demás y el elemento colgaba de la barra en el dibujo sin estar enlazado en el
        modelo (no se activaba). Vale con cualquier orden de unión."""
        for orden in (("X", "t2"), ("t2", "X")):
            ed = nuevo()
            entradas(ed, "p")
            x = ed.add_step("g", "X", True, at=(100, 60))
            t2, _ = ed.add_transition("g", "p", at=(300, 60), label="t2")
            a, b, c = (ed.add_step("g", n, at=(xx, 300)) for n, xx in (("A", 100), ("B", 300), ("C", 500)))
            barra = ed.add_bar("Y", (100, 180), 500)
            nodo = {"X": x, "t2": t2}
            for k in orden:  # arriba, mezclando una etapa y una transición
                ed.bar_link(barra, "arriba", nodo[k])
            n = len(ed.undo_stack)
            avisos = [ed.bar_link(barra, "abajo", e) for e in (a, b, c)]
            self.assertEqual(len(ed.undo_stack), n + 3)
            self.assertEqual(self.nombres(ed, ed.get(t2)["postRefs"]), ["A", "B", "C"], f"orden {orden}: la transición activa las tres")
            self.assertEqual(sorted((d["fromRef"], d["toRef"]) for d in ed.model["draftLinks"]), sorted((x, e) for e in (a, b, c)),
                             "y la etapa de arriba deja un borrador por pareja (etapa con etapa)")
            self.assertEqual({v.code for v in avisos if v}, {"D-ALTERNANCIA"})
            self.assertIn("D-ALTERNANCIA", {d.code for d in ed.validate().diagnostics}, "el borrador se diagnostica")
            # quitar la etapa de la barra deja los borradores fuera y la transición con sus tres etapas
            ed.bar_unlink(barra, x)
            self.assertEqual((ed.model["draftLinks"], self.nombres(ed, ed.get(t2)["postRefs"])), ([], ["A", "B", "C"]))
            ed.undo()
            self.assertEqual(len(ed.model["draftLinks"]), 3)

    def test_SEDI229_una_transicion_sobre_una_barra_activa_todo_lo_que_cuelga_de_ella(self):
        """REQ-MOD-03, REQ-MOD-07, REQ-JER-04, REQ-JER-05, REQ-SIM-03: una transición con una barra Y debajo y de ella una
        macroetapa, una etapa y una encapsulante (y una etapa de su recinto, de otro parcial): el modelo deja los cuatro en
        `postRefs` y el motor los activa a la vez al franquearla, sin diagnósticos, estén en el parcial que estén."""
        ed = nuevo()
        entradas(ed, "marcha", "paro")
        s0, s1 = ed.add_step("g", "0", True, at=(100, 60)), ed.add_step("g", "1", at=(100, 220))
        t1, _ = ed.add_transition("g", "marcha", pre=[s0], post=[s1], at=(100, 140), label="t1")
        t2, _ = ed.add_transition("g", "paro", pre=[s1], at=(100, 300), label="t2")
        mac = ed.add_macro("g", "M1", at=(100, 460))
        e4 = ed.add_step("g", "4", at=(300, 460))
        h = ed.add_step("g", "H", at=(500, 460))
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R1")
        i5 = ed.add_step(rec.partial, "5", at=(700, 460))
        ed.set_activation(i5)
        barra = ed.add_bar("Y", (100, 380), 700)
        ed.bar_link(barra, "arriba", t2)
        for x in (mac.macro, e4, h, i5):
            ed.bar_link(barra, "abajo", x)
        self.assertEqual(self.nombres(ed, ed.get(t2)["postRefs"]), ["M1", "4", "H", "5"])
        self.assertEqual((ed.model["draftLinks"], ed.validate().diagnostics), ([], []))
        situaciones, franqueos = corrida(ed.model, [(1, {"marcha": True}), (2, {"marcha": False}), (3, {"paro": True})],
                                         {"marcha": False, "paro": False})
        self.assertEqual(situaciones[2], ["1"])
        self.assertEqual(franqueos, [["t1"], ["t2"]])
        self.assertTrue({"4", "H", "5", "E1"} <= set(situaciones[3]),
                        f"activa las cuatro cosas de debajo (la macroetapa por su entrada E1): {situaciones[3]}")
        self.assertNotIn("1", situaciones[3])

    def test_SEDI230_una_barra_sobre_una_transicion_exige_todas_las_etapas_de_arriba(self):
        """REQ-MOD-03, REQ-SEM-02: varias etapas por encima de una barra Y y una transición debajo: la transición solo se
        franquea con todas las etapas activas (sincronización) y deja un único camino debajo; mientras falta una, no."""
        ed = nuevo()
        entradas(ed, "p", "q")
        x = ed.add_step("g", "X", True, at=(500, 60))
        a, b = ed.add_step("g", "A", True, at=(100, 60)), ed.add_step("g", "B", at=(300, 140))
        c = ed.add_step("g", "C", at=(200, 400))
        tq, _ = ed.add_transition("g", "q", pre=[x], post=[b], at=(500, 100), label="tq")
        t, _ = ed.add_transition("g", "p", at=(200, 340), label="t")
        barra = ed.add_bar("Y", (100, 260), 300)
        for e in (a, b):
            ed.bar_link(barra, "arriba", e)
        ed.bar_link(barra, "abajo", t)
        ed.connect(t, c)
        self.assertEqual(self.nombres(ed, ed.get(t)["preRefs"]), ["A", "B"])
        self.assertEqual(ed.validate().diagnostics, [])
        situaciones, franqueos = corrida(
            ed.model, [(1, {"p": True}), (2, {"p": False}), (3, {"q": True}), (4, {"q": False}), (5, {"p": True})],
            {"p": False, "q": False})
        self.assertEqual(situaciones, [["A", "X"], ["A", "X"], ["A", "X"], ["A", "B"], ["A", "B"], ["C"]],
                         "con p y solo A activa no se franquea; con A y B, sí, y queda solo C")
        self.assertEqual(franqueos, [["tq"], ["t"]])

    def test_SEDI231_dos_transiciones_sobre_una_barra_son_dos_enlaces_independientes(self):
        """REQ-MOD-03: lo que `bar_link` crea con transiciones por encima de una barra y una etapa por debajo son los enlaces
        normales de cada transición (cada una activa la etapa por su cuenta): no hay sincronización de transiciones. Se
        documenta lo que hay hoy; qué debería significar es una decisión de producto, no del editor."""
        ed = nuevo()
        entradas(ed, "p", "q")
        a, b = ed.add_step("g", "A", True, at=(100, 60)), ed.add_step("g", "B", True, at=(300, 60))
        c = ed.add_step("g", "C", at=(200, 300))
        ta, _ = ed.add_transition("g", "p", pre=[a], at=(100, 140), label="ta")
        tb, _ = ed.add_transition("g", "q", pre=[b], at=(300, 140), label="tb")
        barra = ed.add_bar("Y", (100, 200), 300)
        for t in (ta, tb):
            ed.bar_link(barra, "arriba", t)
        ed.bar_link(barra, "abajo", c)
        self.assertEqual((ed.get(ta)["postRefs"], ed.get(tb)["postRefs"], ed.model["draftLinks"]), ([c], [c], []))
        situaciones, franqueos = corrida(ed.model, [(1, {"p": True}), (2, {"p": False}), (3, {"q": True})],
                                         {"p": False, "q": False})
        self.assertEqual(situaciones, [["A", "B"], ["B", "C"], ["B", "C"], ["C"]], "cada transición, por su lado")
        self.assertEqual(franqueos, [["ta"], ["tb"]])

    def test_SEDI232_dos_etapas_a_cada_lado_de_una_barra_no_ejecutan_y_se_diagnostican(self):
        """REQ-MOD-03, REQ-EDT-09: una barra entre etapas sin transición (o entre transiciones) deja borradores no ejecutables
        (D-ALTERNANCIA, un diagnóstico que impide simular); la etapa sigue colgando de la barra en el dibujo."""
        ed = nuevo()
        entradas(ed, "p")
        a, b = ed.add_step("g", "A", True, at=(100, 60)), ed.add_step("g", "B", True, at=(300, 60))
        c, d = ed.add_step("g", "C", at=(100, 300)), ed.add_step("g", "D", at=(300, 300))
        barra = ed.add_bar("Y", (100, 200), 300)
        for e in (a, b):
            ed.bar_link(barra, "arriba", e)
        avisos = [ed.bar_link(barra, "abajo", e) for e in (c, d)]
        self.assertEqual([v.code for v in avisos], ["D-ALTERNANCIA", "D-ALTERNANCIA"])
        self.assertEqual(len(ed.model["draftLinks"]), 4, "cuatro parejas, cuatro borradores")
        res = ed.validate()
        self.assertFalse(res.can_simulate)
        self.assertEqual({x.code for x in res.diagnostics}, {"D-ALTERNANCIA"})
        self.assertEqual((ed.bars()[0]["arriba"], ed.bars()[0]["abajo"]), ([a, b], [c, d]))

    def test_SEDI233_desunir_y_borrar_la_barra_quitan_solo_sus_enlaces(self):
        """REQ-MOD-03, REQ-EDT-05: quitar un elemento de la barra quita sus enlaces con los del otro lado (y solo esos), borrar
        la barra quita todos los suyos y una macroetapa se une y se desune como una etapa; todo se deshace."""
        ed = nuevo()
        entradas(ed, "p")
        s0 = ed.add_step("g", "0", True, at=(100, 60))
        t, _ = ed.add_transition("g", "p", pre=[s0], at=(100, 140), label="t")
        mac = ed.add_macro("g", "M", at=(100, 300))
        a, b = ed.add_step("g", "A", at=(300, 300)), ed.add_step("g", "B", at=(500, 300))
        barra = ed.add_bar("Y", (100, 220), 500)
        ed.bar_link(barra, "arriba", t)
        for e in (mac.macro, a, b):
            ed.bar_link(barra, "abajo", e)
        self.assertEqual(ed.get(t)["postRefs"], [mac.macro, a, b])
        ed.bar_unlink(barra, mac.macro)
        self.assertEqual((ed.get(t)["postRefs"], ed.bars()[0]["abajo"]), ([a, b], [a, b]))
        ed.bar_unlink(barra, a)
        self.assertEqual(ed.get(t)["postRefs"], [b])
        ed.undo()
        ed.undo()
        self.assertEqual(ed.get(t)["postRefs"], [mac.macro, a, b])
        ed.delete_bar(barra)
        self.assertEqual((ed.get(t)["postRefs"], ed.get(t)["preRefs"], ed.bars()), ([], [s0], []))
        ed.undo()
        self.assertEqual(ed.get(t)["postRefs"], [mac.macro, a, b])
        ed.delete([a])  # una etapa que se borra sale de la barra y de la transición
        self.assertEqual((ed.get(t)["postRefs"], ed.bars()[0]["abajo"]), ([mac.macro, b], [mac.macro, b]))


# ------------------------------------------------------------------------------------------------------ la interfaz
SX = 100  # margen izquierdo del dibujo (escritorio.diagrama.SX): el punto del dibujo de x del modelo es SX + x


def centro(M, ident):
    from escritorio.diagrama import posiciones as pos_dibujo
    return QPointF(*pos_dibujo(M)[ident])


def centro_caja(w, aid):
    """El centro de la caja de una acción en el dibujo."""
    x, y, ancho, alto = next(c for c in w.diagrama.cajas_acciones if c["id"] == aid)["rect"]
    return QPointF(x + ancho / 2, y + alto / 2)


def centro_orden(w, fid):
    """El centro de la caja de una orden de forzado en el dibujo."""
    x, y, ancho, alto = next(c for c in w.diagrama.cajas_ordenes if c["id"] == fid)["rect"]
    return QPointF(x + ancho / 2, y + alto / 2)


class Mayus:
    """Un evento de ratón con Mayús pulsada."""

    def modifiers(self):
        return Qt.KeyboardModifier.ShiftModifier

    def buttons(self):
        return Qt.MouseButton.LeftButton


@unittest.skipUnless(QT, "PySide6 no está instalado")
class BaseQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from escritorio.ventana import Ventana
        self.w = Ventana(QSettings(str(Path(self.tmp.name) / "a.ini"), QSettings.Format.IniFormat),
                         Path(self.tmp.name) / "recup")

    def tearDown(self):
        self.w.a_ejecutar.setChecked(False)
        self.w.edicion = None  # sin preguntar al cerrar
        self.w.deleteLater()
        self.tmp.cleanup()

    def vacio(self):
        """Un grafcet nuevo sin cambios pendientes y con los diálogos sin bloquear: el de borrado confirma y el de nombre
        acepta el que se propone."""
        w = self.w
        if w.edicion is not None:
            w.edicion.ed.dirty = False
        w.nuevo()
        e = w.edicion
        e.ed.dirty = False
        e.confirmar_borrado = lambda plan: True
        e.pedir_texto = lambda titulo, etiqueta, actual: actual
        return w, e

    def soltar_ficha(self, tipo, p):
        """Suelta una ficha de la paleta en el punto p del dibujo (el evento que genera Qt al terminar el arrastre)."""
        mime = QMimeData()
        mime.setText(tipo)
        self.w.diagrama.dropEvent(QDropEvent(QPointF(self.w.diagrama.mapFromScene(p)), Qt.DropAction.CopyAction, mime,
                                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

    @staticmethod
    def estado(e):
        """Lo que deshacer y rehacer deben devolver tal cual: el modelo y la presentación."""
        return copy.deepcopy((e.ed.model, e.ed.presentation))

    @staticmethod
    def pos(e):
        return layout_from_presentation(e.ed.presentation)

    def cadena(self, e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=0, entradas=("marcha", "paro")):
        """Con los gestos del editor: etapas y transiciones alternas (la etapa de la primera fila es la inicial), enlazadas
        una con otra. `filas` da (y, etapa o None si es una transición)."""
        for n in entradas:
            if n not in {v["name"] for v in e.ed.model["variables"]}:
                e.nueva_variable(n, "input")
        ids = []
        for y, etapa in filas:
            ids.append(e.poner_etapa(QPointF(SX + x, y)) if etapa is not None else e.poner_transicion(QPointF(SX + x, y)))
        e.tipo_etapa(ids[0], True)
        for k, ident in enumerate(ids):
            if k:
                e.conectar(ids[k - 1], ident)
        for ident, n in zip([i for i, (_, et) in zip(ids, filas) if et is None], entradas):
            e.poner_condicion(ident, n)
        return ids

    def unir(self, e, a, lado_a, b, lado_b):
        """Arrastra del punto `lado_a` de `a` al punto `lado_b` de `b`, como el ratón."""
        from escritorio.diagrama import anclas
        pa = next(x for x in anclas(e.M, a) if x["lado"] == lado_a)["pos"]
        pb = next(x for x in anclas(e.M, b) if x["lado"] == lado_b)["pos"]
        e.prensar(pa)
        e.mover(pb)
        e.soltar(pb)

    def con_recinto(self):
        """Con gestos: una etapa H en el raíz y una encapsulante E0 con su recinto R, que lleva las etapas A y B (con una
        transición entre las dos). Devuelve la ventana, la edición y los ID."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        h = e.sel[0]
        e.colocar("encapsulante", QPointF(260, 300))
        e0 = e.sel[0]
        e.pedir_texto = lambda *a: "R"
        r = e.anadir_recinto(e0)
        c = cajas_parciales(e.M)[r]
        e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        a = e.sel[0]
        e.sel = [a]
        b = e.anadir_debajo()
        for sid, n in ((h, "H"), (e0, "E0"), (a, "A"), (b, "B")):
            self.assertIsNone(e.renombrar(sid, n))
        return w, e, {"h": h, "e0": e0, "r": r, "a": a, "b": b}


@unittest.skipUnless(QT, "PySide6 no está instalado")
class SuprSobreUnaAccion(BaseQt):
    def con_accion(self):
        w, e = self.vacio()
        e.pedir_accion = lambda sid, aid: None
        ids = self.cadena(e)
        s1 = ids[2]
        e.nueva_variable("Q00", "output")
        e.nueva_variable("Q01", "output")
        return w, e, ids, s1

    def test_SEDI240_supr_sobre_la_caja_de_una_accion_quita_solo_la_accion(self):
        """REQ-EDT-05, REQ-ACT-01: tras un clic en la caja de la acción de una etapa (la etapa queda seleccionada y la acción
        señalada), Supr quita solo esa acción (y su enlace con la etapa) y deja la etapa y las demás acciones; es una sola
        operación de deshacer. Vale con una acción del modelo y con un borrador unido a la etapa."""
        w, e, ids, s1 = self.con_accion()
        for n in ("Q00", "Q01"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        a0, a1 = e.ed.get(s1)["actionRefs"]
        p = centro_caja(w, a0)
        e.prensar(p)
        e.soltar(p)
        self.assertEqual((e.sel, e.accion), ([s1], a0), "el clic señala la acción y deja la etapa seleccionada")
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.assertTrue(e.borrar())
        self.assertIn(s1, [s["id"] for s in e.ed.model["steps"]], "la etapa sigue")
        self.assertEqual(e.ed.get(s1)["actionRefs"], [a1], "y su otra acción")
        self.assertNotIn(a0, [a["id"] for a in e.ed.model["actions"]])
        self.assertEqual((len(e.ed.undo_stack), e.sel, e.accion), (n + 1, [s1], None), "una sola operación")
        self.assertEqual([c["id"] for c in w.diagrama.cajas_acciones], [a1])
        e.deshacer()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        # un borrador unido a la etapa (sin completar): «Añadir…» lo deja señalado
        did = e.anadir_accion(s1)
        self.assertEqual((e.sel, e.accion), ([s1], did))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.draft_actions(), e.ed.get(s1)["actionRefs"], len(e.ed.undo_stack)), ([], [a0, a1], n + 1))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SEDI241_supr_con_la_etapa_seleccionada_o_varias_cosas_borra_lo_seleccionado(self):
        """REQ-EDT-05: para borrar la etapa hay que seleccionarla (un clic en la etapa deja de señalar la acción; también
        `seleccionar`); con otras cosas seleccionadas (lazo) o una acción suelta, Supr borra lo seleccionado como siempre; una
        acción suelta se quita ella sola."""
        w, e, ids, s1 = self.con_accion()
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        (a0,) = e.ed.get(s1)["actionRefs"]
        p = centro_caja(w, a0)
        e.prensar(p)
        e.soltar(p)
        self.assertEqual(e.accion, a0)
        c = centro(e.M, s1)
        e.prensar(c)  # un clic en la etapa: ya no hay acción señalada
        e.soltar(c)
        self.assertEqual((e.sel, e.accion), ([s1], None))
        n = len(e.ed.undo_stack)
        self.assertTrue(e.borrar())
        self.assertEqual((s1 in [s["id"] for s in e.ed.model["steps"]], e.ed.model["actions"], len(e.ed.undo_stack)),
                         (False, [], n + 1), "la etapa se lleva su acción")
        e.deshacer()
        e.prensar(p)  # señalar la acción otra vez y seleccionar la etapa con el panel de diagnósticos
        e.soltar(p)
        e.seleccionar([s1])
        self.assertEqual(e.accion, None)
        self.assertTrue(e.borrar())
        self.assertNotIn(s1, [s["id"] for s in e.ed.model["steps"]])
        e.deshacer()
        # con la etapa y su acción seleccionadas con el lazo, se borra todo lo seleccionado
        e.prensar(QPointF(10, 190))
        e.mover(QPointF(300, 250))
        e.soltar(QPointF(700, 250))
        self.assertTrue({s1, a0} <= set(e.sel), e.sel)
        self.assertTrue(e.borrar())
        self.assertNotIn(s1, [s["id"] for s in e.ed.model["steps"]])
        e.deshacer()
        # una acción suelta seleccionada se quita ella sola
        suelta = e.poner_accion_suelta(QPointF(700, 500))
        self.assertEqual(e.sel, [suelta])
        antes_etapas = [s["id"] for s in e.ed.model["steps"]]
        self.assertTrue(e.borrar())
        self.assertEqual(([s["id"] for s in e.ed.model["steps"]], e.ed.draft_actions()), (antes_etapas, []))

    def test_SEDI242_supr_sobre_una_orden_de_forzado_quita_solo_la_orden(self):
        """REQ-JER-02, REQ-EDT-05: un clic en la caja de una orden de forzado la selecciona (la etapa no) y Supr quita solo la
        orden, en una sola operación de deshacer, y la etapa sigue con sus acciones."""
        w, e, d = self.con_recinto()
        h, r, b = d["h"], d["r"], d["b"]
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "Q00"}))
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [b]}
        fid = e.forzar(h)
        antes, n = self.estado(e), len(e.ed.undo_stack)
        pc = centro_orden(w, fid)
        e.prensar(pc)
        e.soltar(pc)
        self.assertEqual((e.sel, e.accion), ([fid], None), "la orden, no la etapa")
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.model["forces"], len(e.ed.get(h)["actionRefs"]), h in [s["id"] for s in e.ed.model["steps"]]),
                         ([], 1, True))
        self.assertEqual((len(e.ed.undo_stack), e.sel), (n + 1, []))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        e.rehacer()
        self.assertEqual(e.ed.model["forces"], [])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class MoverVarios(BaseQt):
    def lazo(self, e, a, b, evento=None):
        e.prensar(a, evento)
        e.mover(QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2), evento)
        e.mover(b, evento)
        e.soltar(b, evento)

    def test_SEDI243_varios_seleccionados_se_mueven_juntos_desde_el_primer_clic(self):
        """REQ-EDT-02, REQ-EDT-05: tras seleccionar con el lazo varios elementos (etapas, transiciones, una barra, acciones
        sueltas con su grupo y el marco de un recinto vacío), pulsar uno de ellos no deshace la selección y arrastrar los
        mueve a todos juntos, conservando sus posiciones relativas y a la rejilla; es UNA sola operación de deshacer, y solo
        cambia la presentación."""
        w, e = self.vacio()
        e.pedir_accion = lambda sid, aid: None
        ids = self.cadena(e)
        barra = e.poner_barra(QPointF(560, 380), "Y")
        g1 = e.poner_accion_suelta(QPointF(600, 520))
        g2 = e.poner_accion_suelta(QPointF(600 + 80, 520 + 11))  # pegada a la derecha de la primera: forman un grupo
        self.assertEqual(len(e._ids_grupo(g1)), 2)
        e.colocar("encapsulante", QPointF(900, 300))
        enc = e.sel[0]
        marco = e.anadir_recinto(enc)
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        elegidos = [*ids, barra, g1, g2, marco, enc]
        e.sel = list(elegidos)
        antes, pila, modelo = self.pos(e), len(e.ed.undo_stack), copy.deepcopy(e.ed.model)
        barras0 = {b["id"]: (b["x"], b["y"]) for b in e.ed.bars()}
        sueltas0 = {d["id"]: (d["x"], d["y"]) for d in e.ed.draft_actions()}
        pa = centro(e.M, ids[2])
        e.prensar(pa)
        self.assertEqual((e.sel, e.arrastre["tipo"]), (elegidos, "grupo"), "no se deshace la selección")
        e.mover(pa + QPointF(30, 20))
        e.mover(pa + QPointF(60, 40))
        self.assertEqual(self.pos(e), antes, "mientras se arrastra, el modelo no cambia: solo se dibuja")
        d_etapa = centro(e.M, ids[2]) - pa
        self.assertEqual((d_etapa.x(), d_etapa.y()), (60, 40), "lo dibujado ya va con el desplazamiento")
        e.soltar(pa + QPointF(60, 40))
        self.assertEqual(len(e.ed.undo_stack), pila + 1, "una sola operación de deshacer")
        despues = self.pos(e)
        for i in [*ids, marco, enc]:
            self.assertEqual((despues[i][0] - antes[i][0], despues[i][1] - antes[i][1]), (60, 40), i)
        self.assertEqual({i: (float(b["x"]) - float(barras0[i][0]), float(b["y"]) - float(barras0[i][1]))
                          for i, b in ((b["id"], b) for b in e.ed.bars())}, {barra: (60.0, 40.0)})
        self.assertEqual({d["id"]: (float(d["x"]) - float(sueltas0[d["id"]][0]), float(d["y"]) - float(sueltas0[d["id"]][1]))
                          for d in e.ed.draft_actions()}, {g1: (60.0, 40.0), g2: (60.0, 40.0)}, "el grupo suelto, entero")
        self.assertEqual(e.ed.model, modelo, "no cambia el modelo")
        self.assertEqual(e.sel, elegidos, "la selección sigue")
        e.deshacer()
        self.assertEqual((self.pos(e), len(e.ed.undo_stack)), (antes, pila))
        e.rehacer()
        self.assertEqual(self.pos(e)[ids[0]], (antes[ids[0]][0] + 60, antes[ids[0]][1] + 40))
        # a la rejilla: un arrastre de 33 × 17 se queda en 40 × 20
        e.deshacer()
        pa = centro(e.M, ids[2])
        e.prensar(pa)
        e.mover(pa + QPointF(33, 17))
        e.soltar(pa + QPointF(33, 17))
        self.assertEqual(self.pos(e)[ids[0]], (antes[ids[0]][0] + 40, antes[ids[0]][1] + 20))

    def test_SEDI244_un_clic_sin_mover_deja_solo_ese_elemento_y_mayus_sigue_sumando_y_quitando(self):
        """REQ-EDT-02: soltar sin haberse movido (un clic simple) sobre un miembro de la selección múltiple deja seleccionado solo
        ese elemento y no cambia nada; Mayús+clic sigue añadiendo y quitando sin arrastrar; el lazo con Mayús sigue
        ampliando; un arrastre que vuelve al punto de partida no toca nada y conserva la selección."""
        w, e = self.vacio()
        ids = self.cadena(e)
        e.sel = [ids[0], ids[1], ids[2]]
        antes, pila = self.pos(e), len(e.ed.undo_stack)
        p = centro(e.M, ids[2])
        e.prensar(p)
        self.assertEqual(e.sel, [ids[0], ids[1], ids[2]], "al pulsar, la selección sigue")
        e.mover(p + QPointF(2, 1))  # una sacudida que no llega a mover nada
        e.soltar(p + QPointF(2, 1))
        self.assertEqual((e.sel, self.pos(e), len(e.ed.undo_stack)), ([ids[2]], antes, pila), "el clic deja solo ese")
        # Mayús+clic suma y quita sin mover
        e.sel = [ids[0], ids[1]]
        e.prensar(centro(e.M, ids[2]), Mayus())
        e.soltar(centro(e.M, ids[2]), Mayus())
        self.assertEqual(e.sel, [ids[0], ids[1], ids[2]])
        e.prensar(centro(e.M, ids[1]), Mayus())
        e.soltar(centro(e.M, ids[1]), Mayus())
        self.assertEqual((e.sel, e.arrastre, len(e.ed.undo_stack)), ([ids[0], ids[2]], None, pila))
        # el lazo con Mayús amplía lo ya seleccionado
        self.lazo(e, QPointF(20, 270), QPointF(170, 330), Mayus())
        self.assertEqual(set(e.sel), {ids[0], ids[2], ids[3]})
        # mover y devolver al sitio: sin operación y con la selección
        e.sel = [ids[0], ids[1]]
        p = centro(e.M, ids[0])
        e.prensar(p)
        e.mover(p + QPointF(40, 40))
        e.mover(p)
        e.soltar(p)
        self.assertEqual((e.sel, self.pos(e), len(e.ed.undo_stack)), ([ids[0], ids[1]], antes, pila))
        # un solo elemento seleccionado se mueve como siempre (no es un grupo)
        e.sel = [ids[2]]
        e.prensar(centro(e.M, ids[2]))
        self.assertIsNone(e.arrastre.get("tipo"))
        e.soltar(centro(e.M, ids[2]))

    def test_SEDI245_si_lo_que_se_mueve_queda_encima_de_algo_que_no_se_mueve_vuelve_a_su_sitio(self):
        """REQ-EDT-02, REQ-EDT-05: el mismo aviso de solape que al mover un elemento: si el resultado de mover varios deja algo
        encima de un elemento que no se mueve, no cambia nada, vuelven a su sitio con el aviso y no hay operación de deshacer;
        entre ellos no cuenta (conservan sus posiciones relativas)."""
        from escritorio.edicion import MSG_SOLAPE
        w, e = self.vacio()
        ids = self.cadena(e)
        e.colocar("etapa", QPointF(SX + 200, 220))  # una etapa suelta a la derecha de la 1
        quieta = e.sel[0]
        e.sel = [ids[0], ids[1], ids[2]]
        antes, pila = self.pos(e), len(e.ed.undo_stack)
        p = centro(e.M, ids[2])
        e.prensar(p)
        e.mover(p + QPointF(200, 0))  # la etapa 1 llegaría a x = 200, encima de la que está quieta
        self.assertNotEqual(w.diagrama.prohibidos, [], "se marca en rojo lo que no cabe")
        e.soltar(p + QPointF(200, 0))
        self.assertEqual((self.pos(e), len(e.ed.undo_stack), e.mensaje, e.mensaje_info), (antes, pila, MSG_SOLAPE, True))
        self.assertEqual(e.sel, [ids[0], ids[1], ids[2]], "y la selección sigue")
        # un desplazamiento a un hueco sí se hace, aunque pase cerca de la que está quieta antes
        e.prensar(p)
        e.mover(p + QPointF(200, 0))
        e.mover(p + QPointF(0, 120))
        self.assertEqual(w.diagrama.prohibidos, [], "al salir de encima, ya no se marca")
        e.soltar(p + QPointF(0, 120))
        self.assertEqual(self.pos(e)[ids[0]], (antes[ids[0]][0], antes[ids[0]][1] + 120))
        self.assertEqual(self.pos(e)[quieta], antes[quieta])

    def test_SEDI246_las_rutas_de_los_enlaces_con_los_dos_extremos_movidos_se_desplazan_con_ellos(self):
        """REQ-EDT-02, REQ-EDT-14: al mover un grupo, las rutas manuales (coordenadas absolutas laneX, exitY, entryY, middleY) de
        los enlaces cuyos dos extremos se mueven se desplazan con él, en la misma operación de deshacer; las de un enlace con
        un solo extremo movido se quedan como están (como con `move`)."""
        w, e = self.vacio()
        ids = self.cadena(e)
        entre, solo_uno = f"{ids[1]}|{ids[0]}|pre", f"{ids[3]}|{ids[2]}|pre"
        e.ed.set_link_style(entre, {"route": {"laneX": "40", "exitY": "100", "entryY": "130"}, "arrows": {"flow": {"visible": True}}})
        e.ed.set_link_style(solo_uno, {"route": {"middleY": "270"}})
        e.sel = [ids[0], ids[1], ids[2]]
        pila = len(e.ed.undo_stack)
        p = centro(e.M, ids[2])
        e.prensar(p)
        e.mover(p + QPointF(60, 40))
        e.soltar(p + QPointF(60, 40))
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual(e.ed.link_styles()[entre],
                         {"route": {"laneX": "100", "exitY": "140", "entryY": "170"}, "arrows": {"flow": {"visible": True}}})
        self.assertEqual(e.ed.link_styles()[solo_uno], {"route": {"middleY": "270"}}, "el de un extremo que no se movió, igual")
        e.deshacer()
        self.assertEqual(e.ed.link_styles()[entre]["route"], {"laneX": "40", "exitY": "100", "entryY": "130"})


@unittest.skipUnless(QT, "PySide6 no está instalado")
class EquidistanciarEnElDibujo(BaseQt):
    OPCION = "Equidistanciar alturas de la cadena"

    def test_SEDI247_el_menu_ofrece_equidistanciar_en_cada_elemento_de_la_cadena_y_en_el_hueco(self):
        """REQ-EDT-02, REQ-EDT-03: el botón derecho en una etapa, una transición o un enlace de una cadena ofrece «Equidistanciar
        alturas de la cadena», que deja todas las distancias a la estándar (DY, la de «Añadir debajo») en UNA operación de
        deshacer, sin cambiar el modelo; aplicado otra vez no hace nada ni apila operación; en el hueco, «Equidistanciar todo
        el lienzo» (tras «Nuevo grafcet parcial aquí»); sin cadenas (una etapa suelta) no se ofrece equidistanciar nada."""
        from escritorio.edicion import DY as DISTANCIA
        from escritorio.diagrama import enlaces
        w, e = self.vacio()
        self.assertEqual(DISTANCIA, DY)
        self.assertEqual([t for t, _ in e.menu(QPointF(600, 400))], ["Nuevo grafcet parcial aquí"],
                         "sin cadenas, un hueco no ofrece equidistanciar nada")
        e.colocar("etapa", QPointF(900, 60))
        suelta = e.sel[0]
        self.assertNotIn(self.OPCION, dict(e.menu(centro(e.M, suelta))), "una etapa suelta no es una cadena")
        ids = self.cadena(e, filas=((60, "0"), (180, None), (240, "1"), (420, None)))
        pos0, modelo, revision = self.pos(e), copy.deepcopy(e.ed.model), e.ed.revision
        # el menú de una etapa conserva lo suyo y añade la opción al final
        opciones = [t for t, _ in e.menu(centro(e.M, ids[2]))]
        self.assertEqual(opciones[:2], ["Añadir acción…", "Colocación de las acciones"])
        self.assertEqual(opciones[-1], self.OPCION)
        # una transición y un enlace: solo esa opción, y el clic derecho los selecciona
        self.assertEqual([t for t, _ in e.menu(centro(e.M, ids[1]))], [self.OPCION])
        self.assertEqual(e.sel, [ids[1]])
        enlace = next(r for r in enlaces(e.M) if r["tid"] == ids[3] and r["rol"] == "pre")
        (x0, y0), (x1, y1) = enlace["pts"][0], enlace["pts"][1]
        self.assertEqual([t for t, _ in e.menu(QPointF((x0 + x1) / 2, (y0 + y1) / 2))], [self.OPCION])
        self.assertEqual(e.sel, [enlace["id"]])
        # en el hueco: todo el lienzo
        self.assertEqual([t for t, _ in e.menu(QPointF(600, 400))],
                         ["Nuevo grafcet parcial aquí", "-", "Equidistanciar todo el lienzo"])
        # aplicar desde la transición
        n = len(e.ed.undo_stack)
        e.menu(centro(e.M, ids[1]))
        movidos = dict(e.menu(centro(e.M, ids[1])))[self.OPCION]()
        pos = self.pos(e)
        self.assertEqual([pos[i][1] for i in ids], [60.0, 140.0, 220.0, 300.0])
        self.assertEqual({pos[i][0] for i in ids}, {0.0}, "la x no cambia")
        self.assertEqual(sorted(movidos), sorted(ids[1:]))
        self.assertEqual((len(e.ed.undo_stack), e.mensaje_info, e.mensaje), (n + 1, True, "Alturas equidistanciadas"))
        self.assertEqual((e.ed.model, e.ed.revision), (modelo, revision), "solo presentación")
        self.assertEqual(pos[suelta], (800.0, 60.0), "la etapa suelta, donde estaba")
        # idempotente
        antes = self.estado(e)
        self.assertEqual(dict(e.menu(centro(e.M, ids[1])))[self.OPCION](), [])
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.mensaje), (antes, n + 1, "Las alturas ya estaban equidistanciadas"))
        e.deshacer()
        self.assertEqual((self.pos(e), len(e.ed.undo_stack)), (pos0, n))
        e.rehacer()
        self.assertEqual([self.pos(e)[i][1] for i in ids], [60.0, 140.0, 220.0, 300.0])

    def test_SEDI248_la_seleccion_y_todo_el_lienzo_equidistancian_las_cadenas_que_tocan(self):
        """REQ-EDT-02, REQ-EDT-03: con varios elementos seleccionados, el botón derecho en un hueco o en uno de ellos ofrece
        también «Equidistanciar la selección» (las cadenas que toca la selección, sin deshacer la selección); «todo el
        lienzo» las equidistancia todas, en una sola operación de deshacer cada vez."""
        w, e = self.vacio()
        a = self.cadena(e, filas=((60, "0"), (160, None), (260, "1"), (320, None)), x=0)
        b = self.cadena(e, filas=((100, "0"), (240, None), (280, "1"), (440, None)), x=400)
        e.sel = [a[1], a[2]]
        self.assertEqual([t for t, _ in e.menu(QPointF(800, 700))],
                         ["Nuevo grafcet parcial aquí", "-", "Equidistanciar la selección", "Equidistanciar todo el lienzo"])
        opciones = [t for t, _ in e.menu(centro(e.M, a[2]))]
        self.assertIn("Equidistanciar la selección", opciones)
        self.assertIn(self.OPCION, opciones)
        self.assertEqual(e.sel, [a[1], a[2]], "el botón derecho en uno de varios seleccionados no los deshace")
        n = len(e.ed.undo_stack)
        antes_b = {i: self.pos(e)[i] for i in b}
        dict(e.menu(QPointF(800, 700)))["Equidistanciar la selección"]()
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual([self.pos(e)[i][1] for i in a], [60.0, 140.0, 220.0, 300.0])
        self.assertEqual({i: self.pos(e)[i] for i in b}, antes_b, "la otra cadena no se toca")
        self.assertEqual(e.sel, [a[1], a[2]])
        e.sel = []
        dict(e.menu(QPointF(800, 700)))["Equidistanciar todo el lienzo"]()
        self.assertEqual(len(e.ed.undo_stack), n + 2)
        self.assertEqual([self.pos(e)[i][1] for i in b], [100.0, 180.0, 260.0, 340.0], "cada cadena conserva su primer nivel")
        e.deshacer()
        self.assertEqual({i: self.pos(e)[i] for i in b}, antes_b)

    def test_SEDI249_las_acciones_de_una_etapa_piden_mas_altura_y_no_se_solapan_con_el_nivel_siguiente(self):
        """REQ-EDT-02, REQ-ACT-01: una etapa con tres acciones en columna (que llegan hasta 134 por debajo de su centro) separa
        la transición siguiente más que la distancia estándar (lo que sobresalen, el texto de la transición y el margen,
        en pasos de rejilla); con la distancia estándar sola chocarían con el texto de la transición; las acciones, y las
        órdenes de forzado, viajan con su etapa; una etapa con una fila de acciones no cambia la distancia."""
        w, e = self.vacio()
        e.pedir_accion = lambda sid, aid: None
        ids = self.cadena(e, filas=((60, "0"), (180, None), (240, "1"), (420, None)))
        for n in ("Q00", "Q01", "Q02"):
            e.nueva_variable(n, "output")
            self.assertIsNone(e.poner_accion(ids[2], {"tipo": "continua", "variable": n}))
        e.colocar_acciones(ids[2], "columna")
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        # con la distancia estándar sola (sin lo que piden las acciones), la columna choca con el texto de la transición
        e.ed.equidistribute(None, DY)
        e.cambia()
        self.assertTrue([p for p in e._pares_solape(set(ids)) if ids[2] in p and ids[3] in p],
                        "con 80 de distancia, las acciones de la etapa 1 tocan a t2")
        e.deshacer()
        e.cambia()
        n = len(e.ed.undo_stack)
        e.equidistanciar([ids[0]])
        pos = self.pos(e)
        self.assertEqual([pos[i][1] for i in ids], [60.0, 140.0, 220.0, 380.0], "de la etapa 1 a t2: 134 + 12 + 8, a 160")
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.app.processEvents()
        self.assertFalse([p for p in e._pares_solape(set(ids)) if ids[2] in p and ids[3] in p], "ya no se tocan")
        cajas = [c for c in w.diagrama.cajas_acciones if c["etapa"] == ids[2]]
        self.assertEqual(len(cajas), 3)
        self.assertTrue(all(c["rect"][1] + c["rect"][3] + 12 + 8 <= pos[ids[3]][1] for c in cajas), "por encima de la transición")
        self.assertTrue(all(abs(c["rect"][0] - (pos[ids[2]][0] + SX + 22 + 26)) < 1 for c in cajas), "y siguen a su etapa")
        despues = self.estado(e)
        e.equidistanciar([ids[0]])
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (despues, n + 1), "idempotente con las acciones también")
        # una fila de acciones no cambia la distancia estándar
        e.deshacer()
        e.colocar_acciones(ids[2], "fila")
        n = len(e.ed.undo_stack)
        e.equidistanciar([ids[0]])
        self.assertEqual([self.pos(e)[i][1] for i in ids], [60.0, 140.0, 220.0, 300.0])

    def test_SEDI250_si_algo_quedaria_encima_de_otro_elemento_no_se_equidistancia_y_se_avisa(self):
        """REQ-EDT-02, REQ-EDT-05: si al equidistanciar un elemento de la cadena quedara encima de otro que no es de ella, no
        cambia nada (ni operación de deshacer ni marca de cambios) y se avisa en rojo; lo que ya se tocaba antes no cuenta."""
        from escritorio.edicion import MSG_EQUIDISTANCIA
        w, e = self.vacio()
        ids = self.cadena(e, filas=((60, "0"), (100, None), (140, "1"), (180, None)))
        e.colocar("etapa", QPointF(SX, 300))  # una etapa suelta justo donde caería la etapa 1 (y = 220) / t2 (y = 300)
        suelta = e.sel[0]
        e.ed.dirty = False
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.assertIsNone(e.equidistanciar([ids[0]]))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.ed.dirty), (antes, n, False))
        self.assertEqual((e.mensaje, e.mensaje_info), (MSG_EQUIDISTANCIA, False))
        # apartada, se equidistancia
        e.ed.move(suelta, 600, 300)
        e.cambia()
        self.assertEqual(sorted(e.equidistanciar([ids[0]])), sorted(ids[1:]))
        self.assertEqual([self.pos(e)[i][1] for i in ids], [60.0, 140.0, 220.0, 300.0])

    def test_SEDI251_con_una_barra_de_simultaneidad_cada_barra_va_a_mitad_y_se_guarda_y_se_abre(self):
        """REQ-EDT-02, REQ-EDT-03, REQ-DAT-01: una barra enlazada con el ratón entre una transición y dos etapas se alcanza
        desde la propia barra (su menú ofrece equidistanciar), queda a mitad de la distancia que le toca, no cambia los
        enlaces del modelo y el resultado se guarda y se abre tal cual."""
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        w, e = self.vacio()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (240, "1"), (300, None)), x=100)
        e.colocar("etapa", QPointF(SX + 20, 580))
        e.colocar("etapa", QPointF(SX + 260, 600))
        a, b = e.M["steps"][-2]["id"], e.M["steps"][-1]["id"]
        barra = e.poner_barra(QPointF(SX + 200, 440), "Y")
        self.unir(e, ids[3], "abajo", barra, "arriba")
        for x in (a, b):
            self.unir(e, x, "arriba", barra, "abajo")
        self.assertEqual(e.ed.get(ids[3])["postRefs"], [a, b])
        modelo = copy.deepcopy(e.ed.model)
        sobre = QPointF(SX + 200, 442)  # sobre la barra (de x = 140 a 260 en el modelo)
        self.assertEqual([t for t, _ in e.menu(sobre)], [self.OPCION])
        self.assertEqual(e.sel, [barra])
        dict(e.menu(sobre))[self.OPCION]()
        pos = self.pos(e)
        self.assertEqual([pos[i][1] for i in (*ids, a, b)], [60.0, 140.0, 220.0, 300.0, 380.0, 380.0], "a y b al mismo nivel")
        barra_y = float(next(x for x in e.ed.bars() if x["id"] == barra)["y"])
        self.assertEqual(barra_y, 340.0, "la barra, justo a mitad de t2 (300) y de las etapas (380)")
        self.assertEqual(e.ed.model, modelo)
        destino = Path(self.tmp.name) / "equidistanciado"
        e.guardar(destino)
        op = open_model(destino)
        e2 = Edicion.desde(op.doc, {}, "abierto", destino, op.presentations[0])
        self.assertEqual(layout_from_presentation(e2.ed.presentation), pos)
        self.assertEqual([(x["x"], x["y"], x["ancho"]) for x in e2.ed.bars()], [(x["x"], x["y"], x["ancho"]) for x in e.ed.bars()])
        self.assertEqual(e2.equidistanciar(None), [], "abierto, ya está equidistanciado")

    def test_SEDI252_lo_equidistanciado_no_cambia_lo_que_se_simula(self):
        """REQ-EDT-14, REQ-SIM-03: equidistanciar es solo presentación: el grafcet se simula igual antes y después, con los
        mismos diagnósticos y la misma revisión."""
        w, e = self.vacio()
        ids = self.cadena(e, filas=((60, "0"), (180, None), (240, "1"), (420, None)))
        e.conectar(ids[3], ids[0])
        diag = [str(d) for d in e.ed.validate().diagnostics]
        guion = [(1, {"marcha": True}), (2, {"marcha": False}), (3, {"paro": True})]
        antes = corrida(e.ed.model, guion, {"marcha": False, "paro": False})
        revision = e.ed.revision
        e.equidistanciar(None)
        self.assertEqual(corrida(e.ed.model, guion, {"marcha": False, "paro": False}), antes)
        self.assertEqual(([str(d) for d in e.ed.validate().diagnostics], e.ed.revision), (diag, revision))
        self.assertEqual([self.pos(e)[i][1] for i in ids], [60.0, 140.0, 220.0, 300.0], "con el retorno a la etapa 0")


@unittest.skipUnless(QT, "PySide6 no está instalado")
class FichaDeForzado(BaseQt):
    AVISO = "Una orden de forzado va asociada a una etapa: suéltela sobre una etapa"

    def test_SEDI253_la_orden_de_forzado_es_una_ficha_de_la_paleta_como_las_demas(self):
        """REQ-EDT-02, REQ-JER-02: la paleta ofrece «Forzado» (la orden de forzado: rectángulo doble con «G{ }») tras las
        fichas de jerarquía, con nombre, ayuda, icono y figura de arrastre como las otras; un clic solo muestra su ayuda y
        arrastrarla lleva su texto («forzado»); ocho fichas en dos columnas y cuatro filas."""
        from escritorio import propiedades
        w, e = self.vacio()
        pa = w.paleta
        textos = [pa.item(i).text() for i in range(pa.count())]
        self.assertEqual(textos[-1], "Forzado")
        self.assertEqual((textos[:7], pa.count(), pa.FILAS), (["Etapa", "Transición", "Simultaneidad", "Acción", "Macroetapa",
                                                              "Encapsulante", "Grafcet parcial"], 8, 4))
        self.assertEqual(pa.mimeData([pa.item(7)]).text(), "forzado")
        self.assertEqual(propiedades.COLOCABLES[-1], "forzado")
        self.assertEqual((propiedades.NOMBRES["forzado"], pa.item(7).toolTip()), ("Forzado", propiedades.AYUDAS["forzado"]))
        ayuda = propiedades.AYUDAS["forzado"]
        self.assertTrue("rectángulo doble" in ayuda and "etapa" in ayuda and "Doble clic" in ayuda and "Supr" in ayuda, ayuda)
        self.assertFalse(pa.item(7).icon().pixmap(80, 64).toImage().isNull())
        # la figura de arrastre lleva el rectángulo doble (dos contornos, uno más que la caja de una acción) y el punto bajo el
        # puntero es el centro de su lado izquierdo, como la ficha «Acción»
        pm, punto = propiedades.figura("forzado", 1.0, 1.0)
        self.assertTrue(pm.rect().contains(punto))
        self.assertGreater(pm.width(), pm.height(), "como la caja de una acción")
        self.assertLess(punto.x(), 8)

        def contornos(clave):
            """Cuántos trazos oscuros cruza, de arriba abajo, una vertical por el borde superior de la figura (a doble tamaño)."""
            img = propiedades.figura(clave, 2.0, 1.0)[0].toImage()
            oscuro = [img.pixelColor(100, y).alpha() > 100 and img.pixelColor(100, y).red() < 140 for y in range(26)]
            return sum(1 for k, v in enumerate(oscuro) if v and (k == 0 or not oscuro[k - 1]))
        self.assertEqual((contornos("forzado"), contornos("accion:continua")), (2, 1))
        # un clic en la ficha solo muestra su ayuda
        n = len(e.ed.undo_stack)
        pa.itemClicked.emit(pa.item(7))
        self.assertEqual((e.mensaje, e.mensaje_info, w.ayuda.text(), len(e.ed.undo_stack)),
                         (propiedades.AYUDAS["forzado"], True, propiedades.AYUDAS["forzado"], n))
        # arrastrar la ficha: el texto que viaja
        capturados = []

        class FalsoDrag:
            def __init__(self, origen):
                capturados.append(self)

            def setMimeData(self, m):
                self.texto = m.text()

            def setPixmap(self, pm):
                self.pm = pm

            def setHotSpot(self, p):
                self.punto = p

            def exec(self, *a):
                return Qt.DropAction.IgnoreAction
        from unittest import mock
        with mock.patch.object(propiedades, "QDrag", FalsoDrag):
            pa.setCurrentRow(7)
            pa.startDrag(Qt.DropAction.CopyAction)
        self.assertEqual([c.texto for c in capturados], ["forzado"])
        self.assertTrue(capturados[0].pm.rect().contains(capturados[0].punto))

    def test_SEDI254_soltar_la_ficha_sobre_una_etapa_abre_el_dialogo_y_crea_la_orden_asociada_a_ella(self):
        """REQ-EDT-02, REQ-JER-02, REQ-JER-03, REQ-EDT-05: arrastrar la ficha sobre una etapa la resalta como destino; soltarla
        sobre la etapa (o sobre una acción suya, o junto a su fila de acciones) abre el diálogo de la orden (parcial destino,
        forma y etapas, con nombres) y, al aceptar, crea la orden asociada a esa etapa en una sola operación de deshacer, la
        deja seleccionada y la dibuja en su rectángulo doble; la orden se edita con doble clic."""
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "Q00"}))
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        # sobrevolar: la etapa se recuadra como destino; en un hueco, no, pero se puede soltar (se avisa al soltar)
        ch = centro(e.M, h)
        self.assertTrue(e.sobrevolar("forzado", ch))
        self.assertIsNotNone(w.diagrama.destino)
        r1 = w.diagrama.destino.rect()
        self.assertEqual((r1.x(), r1.y(), r1.width(), r1.height()), (ch.x() - 22 - 4, ch.y() - 22 - 4, 52, 52))
        self.assertTrue(e.sobrevolar("forzado", QPointF(900, 700)))
        self.assertIsNone(w.diagrama.destino)
        self.assertTrue(e.sobrevolar("forzado", ch))
        self.assertIsNotNone(w.diagrama.destino)
        pedidas, respuesta = [], [{"destino": r, "forma": "explicit", "etapas": [b]}]
        e.pedir_forzado = lambda datos: pedidas.append(datos) or respuesta[0]
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.soltar_ficha("forzado", ch)
        self.assertIsNone(w.diagrama.destino, "al soltar se quita el recuadro")
        datos = pedidas[0]
        self.assertEqual((datos["origen"], datos["destinos"], datos["actual"]), ("H", [(r, "recinto R")], None))
        self.assertEqual(datos["etapas"], {r: [(a, "A"), (b, "B")]})
        (f,) = e.ed.model["forces"]
        self.assertEqual((f["sourceStepRef"], f["targetPartialRef"], f["targetKind"], f["targetSteps"]), (h, r, "explicit", [b]))
        self.assertEqual((len(e.ed.undo_stack), e.sel, e.mensaje_info), (n + 1, [f["id"]], True))
        self.assertEqual([(c["id"], c["etapa"]) for c in w.diagrama.cajas_ordenes], [(f["id"], h)])
        self.assertEqual(w.props.pagina, "orden")
        self.assertIn("Doble clic", w.props.l_vacio.text())
        e.deshacer()
        self.assertEqual((self.estado(e), w.diagrama.cajas_ordenes), (antes, []))
        # sobre una acción de la etapa y junto a su fila de acciones (a menos de IMAN_ACCION de su borde derecho)
        (caja,) = [c for c in w.diagrama.cajas_acciones if c["etapa"] == h]
        x, y, ancho, alto = caja["rect"]
        respuesta[0] = {"destino": r, "forma": "empty", "etapas": []}
        for punto in (QPointF(x + ancho / 2, y + alto / 2), QPointF(x + ancho + 10, y + alto / 2)):
            self.assertTrue(e.sobrevolar("forzado", punto))
            self.assertIsNotNone(w.diagrama.destino, punto)
            n = len(e.ed.undo_stack)
            self.soltar_ficha("forzado", punto)
            self.assertEqual((len(e.ed.undo_stack), e.ed.model["forces"][-1]["sourceStepRef"]), (n + 1, h))
            e.deshacer()
        lejos = QPointF(x + ancho + 40, y + alto / 2)
        self.assertTrue(e.sobrevolar("forzado", lejos))
        self.assertIsNone(w.diagrama.destino, "a más de 16 del borde, ya no es de su fila")
        # doble clic en la orden: se edita con el diálogo (valores actuales) y el cambio es una operación
        respuesta[0] = {"destino": r, "forma": "explicit", "etapas": [a, b]}
        self.soltar_ficha("forzado", ch)
        fid = e.ed.model["forces"][0]["id"]
        respuesta[0] = {"destino": r, "forma": "current", "etapas": []}
        n = len(e.ed.undo_stack)
        self.assertTrue(e.doble(centro_orden(w, fid)))
        self.assertEqual(pedidas[-1]["actual"], {"destino": r, "forma": "explicit", "etapas": [a, b]})
        self.assertEqual((e.ed.model["forces"][0]["targetKind"], len(e.ed.undo_stack), e.sel), ("current", n + 1, [fid]))
        # conserva «Forzar un parcial…», «Editar orden…» y «Quitar orden» del menú
        self.assertIn("Forzar un parcial…", dict(e.menu(ch)))
        self.assertEqual([t for t, _ in e.menu(centro_orden(w, fid))], ["Editar orden de forzado…", "Quitar orden de forzado"])

    def test_SEDI255_soltar_la_ficha_donde_no_hay_etapa_cancelar_o_un_rechazo_no_cambian_nada(self):
        """REQ-EDT-02, REQ-JER-02, REQ-EDT-09: soltar la ficha en un hueco o sobre algo que no es una etapa (una transición, una
        macroetapa, una barra, un enlace, una acción suelta) no crea nada y avisa en rojo «Una orden de forzado va asociada a
        una etapa…»; cancelar el diálogo, no haber otro parcial al que forzar o un ciclo de forzado (D-JERARQUIA-CICLO) tampoco
        cambian nada, y avisan en rojo con el parpadeo de la etapa."""
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        mid = e.poner_macro(QPointF(900, 300))
        barra = e.poner_barra(QPointF(900, 600), "Y")
        suelta = e.poner_accion_suelta(QPointF(700, 700))
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "empty", "etapas": []}
        ts = [t["id"] for t in e.M["transitions"]]
        antes, n = self.estado(e), len(e.ed.undo_stack)
        puntos = {"hueco": QPointF(1100, 700), "transición": centro(e.M, ts[0]), "macroetapa": centro(e.M, mid),
                  "barra": QPointF(900, 602), "acción suelta": centro_caja(w, suelta)}
        for nombre, p in puntos.items():
            e.mensaje = ""
            self.soltar_ficha("forzado", p)
            self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n), nombre)
            self.assertEqual((e.mensaje, e.mensaje_info), (self.AVISO, False), nombre)
        # cancelar el diálogo
        e.pedir_forzado = lambda datos: None
        e.mensaje = ""
        self.soltar_ficha("forzado", centro(e.M, h))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        # un ciclo: A, del recinto, fuerza al raíz, que H ya fuerza al recinto
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "empty", "etapas": []}
        self.soltar_ficha("forzado", centro(e.M, h))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.pedir_forzado = lambda datos: {"destino": "g", "forma": "empty", "etapas": []}
        e.parpadeo.parar()
        self.soltar_ficha("forzado", centro(e.M, a))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info and "ciclo" in e.mensaje, e.mensaje)
        self.assertEqual(e.parpadeo.ids, {a})
        e.parpadeo.parar()
        # sin otro parcial no hay a quién forzar
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        solo = e.sel[0]
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.soltar_ficha("forzado", centro(e.M, solo))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue("otro parcial" in e.mensaje and not e.mensaje_info, e.mensaje)
        e.parpadeo.parar()


    def test_SEDI256_la_accion_de_una_etapa_de_la_seleccion_mueve_el_grupo_y_un_clic_la_senala(self):
        """REQ-EDT-02, REQ-ACT-01: con la etapa y sus acciones seleccionadas (lazo), pulsar la caja de una acción no deshace la
        selección: arrastrar mueve todo junto (las acciones viajan con su etapa) y un clic sin mover deja la etapa seleccionada
        con esa acción señalada, como siempre."""
        w, e = self.vacio()
        e.pedir_accion = lambda sid, aid: None
        ids = self.cadena(e)
        s1 = ids[2]
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        (aid,) = e.ed.get(s1)["actionRefs"]
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        e.prensar(QPointF(10, 10))
        e.mover(QPointF(300, 150))
        e.mover(QPointF(700, 340))
        e.soltar(QPointF(700, 340))
        self.assertTrue({*ids, aid} <= set(e.sel), e.sel)
        antes, pila = self.pos(e), len(e.ed.undo_stack)
        pc = centro_caja(w, aid)
        e.prensar(pc)
        self.assertEqual(e.arrastre["tipo"], "grupo")
        e.mover(pc + QPointF(40, 60))
        e.soltar(pc + QPointF(40, 60))
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        despues = self.pos(e)
        self.assertEqual({(despues[i][0] - antes[i][0], despues[i][1] - antes[i][1]) for i in ids}, {(40.0, 60.0)})
        c = centro_caja(w, aid)
        self.assertEqual((c.x() - pc.x(), c.y() - pc.y()), (40, 60), "la acción, con su etapa")
        # un clic sin mover: la etapa, con la acción señalada
        e.sel = list(ids)
        pc = centro_caja(w, aid)
        e.prensar(pc)
        e.soltar(pc)
        self.assertEqual((e.sel, e.accion, e.ver_accion, len(e.ed.undo_stack)), ([s1], aid, True, pila + 1))

    def test_SEDI257_las_ocho_fichas_se_ven_enteras_en_cuatro_filas_a_1366x768(self):
        """REQ-EDT-02, REQ-EDT-09: con la ficha «Forzado» la paleta pasó de tres a cuatro filas de 84 de alto (340 en total, sin
        barras de desplazamiento) y con «Grafcet parcial» llena la cuarta fila sin pasar a una quinta: las ocho fichas se ven
        enteras, en dos columnas, a 1366×768, con el panel de opciones de abajo por encima de su mínimo."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        self.app.processEvents()
        pa = w.paleta
        self.assertEqual((pa.FILAS, pa.gridSize().height(), pa.height(), pa.count()), (4, 84, 340, 8))
        zona = pa.viewport().rect()
        for i in range(pa.count()):
            self.assertTrue(zona.contains(pa.visualItemRect(pa.item(i))), pa.item(i).text())
        self.assertEqual(len({pa.visualItemRect(pa.item(i)).y() for i in range(pa.count())}), 4)
        self.assertEqual({pa.visualItemRect(pa.item(i)).center().x() // pa.gridSize().width() for i in range(pa.count())}, {0, 1})
        self.assertGreaterEqual(w.inferior.height(), w.props.minimumSizeHint().height())
        self.assertTrue(w.dock.isVisible() and w.diagrama.isVisible())
        self.assertFalse(pa.verticalScrollBar().isVisible(), "sin barra: no hace falta desplazarse")

    def test_SEDI267_la_paleta_se_encoge_en_ventanas_bajas_sin_subir_el_minimo_de_alto_de_la_ventana(self):
        """REQ-EDT-02, REQ-EDT-09: la paleta de cuatro filas pide su alto (340) pero se encoge hasta tres filas, con barra
        vertical y siempre en dos columnas: el mínimo de alto de la ventana de edición no pasa de 564 (el de antes de «Forzado»;
        con la paleta fija a cuatro filas era 648); a 1366×768 las ocho fichas siguen enteras y sin barra, y en la ventana más
        baja el dibujo y el panel inferior conservan su alto y se llega a «Forzado» desplazando."""
        w, e = self.vacio()
        pa = w.paleta
        ancho = pa.gridSize().width()

        def columnas():
            return {pa.visualItemRect(pa.item(i)).center().x() // ancho for i in range(pa.count())}

        def a_la_vista():
            return [pa.item(i).text() for i in range(pa.count()) if pa.viewport().rect().contains(pa.visualItemRect(pa.item(i)))]
        w.resize(1366, 768)
        w.show()
        self.app.processEvents()
        self.assertEqual((pa.sizeHint().height(), pa.minimumSizeHint().height()), (340, 256), "pide cuatro filas, baja a tres")
        self.assertEqual(w.dock.minimumSizeHint().height(), 256)
        self.assertLessEqual(w.minimumSizeHint().height(), 564, "el mínimo de la ventana de edición no sube por la paleta")
        # a 1366×768: las ocho fichas enteras, sin desplazarse, y el dibujo conserva (o gana) alto respecto del de antes
        self.assertEqual((pa.height(), len(a_la_vista()), pa.verticalScrollBar().isVisible()), (340, 8, False))
        self.assertEqual(columnas(), {0, 1})
        self.assertGreaterEqual(w.diagrama.height(), 192)
        self.assertGreaterEqual(w.inferior.height(), w.props.minimumSizeHint().height())
        # la ventana más baja posible: la paleta se encoge y sale su barra, pero siguen dos columnas y la ventana no crece
        w.resize(1000, 300)
        self.app.processEvents()
        self.assertEqual(w.height(), w.minimumSizeHint().height())
        self.assertLessEqual(w.height(), 564)
        self.assertEqual((pa.height(), pa.verticalScrollBar().isVisible()), (256, True))
        self.assertLess(len(a_la_vista()), 8)
        self.assertEqual((columnas(), pa.viewport().width() >= 2 * ancho), ({0, 1}, True), "la barra no deja una sola columna")
        self.assertGreaterEqual(w.diagrama.height(), 140, "como antes de la ficha: el dibujo no se aplasta")
        self.assertGreaterEqual(w.inferior.height(), w.props.minimumSizeHint().height())
        self.assertLessEqual(w.statusBar().geometry().bottom(), w.height() - 1)
        pa.scrollToItem(pa.item(7))
        self.app.processEvents()
        self.assertIn("Forzado", a_la_vista(), "desplazando se llega a la última ficha")
        # y al volver a una ventana alta, vuelven las ocho enteras
        w.resize(1366, 900)
        self.app.processEvents()
        self.assertEqual((pa.height(), len(a_la_vista()), pa.verticalScrollBar().isVisible()), (340, 8, False))

    def test_SEDI272_el_divisor_movido_a_mano_se_respeta_aunque_la_paleta_no_quepa_entera(self):
        """REQ-EDT-09, REQ-EDT-02: la paleta solo gana su alto completo mientras el divisor entre el dibujo y el panel inferior
        no se haya movido: si se arrastra para dar más sitio al panel, al pasar a Play y volver a Pausa el panel conserva su alto
        y la paleta se desplaza."""
        w, e = self.vacio()
        ids = self.cadena(e)
        e.conectar(ids[3], ids[0])  # cerrado en lazo, para poder pasar a Play
        w.resize(1366, 768)
        w.show()
        self.app.processEvents()
        pa = w.paleta
        self.assertEqual((w.vsplit.sizes(), pa.height()), ([340, 328], 340))
        w.vsplit.moveSplitter(w.vsplit.sizes()[0] - 40, 1)
        self.app.processEvents()
        movido = w.vsplit.sizes()
        self.assertEqual((movido, pa.height()), ([300, 368], 300))
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertTrue(w.cambiar_modo("editar"))
        self.app.processEvents()
        self.assertEqual((w.vsplit.sizes(), pa.height(), pa.verticalScrollBar().isVisible()), (movido, 300, True))


@unittest.skipUnless(QT, "PySide6 no está instalado")
class BarrasConElRaton(BaseQt):
    def montar(self, destino="raiz"):
        """t2 «paro» sobre una barra Y de la que cuelgan una macroetapa, una etapa y una tercera etapa (en el raíz, o en un
        recinto de una encapsulante, o en la expansión de la macroetapa), con los gestos del editor."""
        w, e = self.vacio()
        ids = self.cadena(e, x=0)  # 0 -marcha-> 1 -paro-> (t2)
        t2 = ids[3]
        mid = e.poner_macro(QPointF(SX + 100, 700))
        if destino == "recinto":
            e.colocar("encapsulante", QPointF(SX + 900, 460))
            h = e.sel[0]
            from escritorio.diagrama import cajas_parciales
            r = e.anadir_recinto(h)
            c = cajas_parciales(e.M)[r]
            e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
            dentro, otro = e.sel[0], h
        elif destino == "expansion":
            from escritorio.diagrama import cajas_parciales
            c = cajas_parciales(e.M)[e.ed.macro_info(mid).partial]
            e.colocar("etapa", QPointF(c["x0"] + 30, c["y1"] + 40))
            dentro = e.sel[0]
            e.colocar("etapa", QPointF(c["x1"] + 30, c["y1"] + 40))
            otro = e.sel[0]
        else:
            e.colocar("etapa", QPointF(SX + 300, 460))
            dentro = e.sel[0]
            e.colocar("etapa", QPointF(SX + 500, 460))
            otro = e.sel[0]
        barra = e.poner_barra(QPointF(SX + 200, 380), "Y")
        e.ed.resize_bar(barra, e.ed.bars()[0]["x"], 1000)
        e.cambia()
        return w, e, ids, mid, dentro, otro, barra

    def probar(self, e, ids, mid, dentro, otro, barra):
        """Une con el ratón t2 -> barra -> [macroetapa, dentro, otro] y comprueba el modelo, los diagnósticos y la simulación."""
        self.unir(e, ids[3], "abajo", barra, "arriba")
        for x in (mid, dentro, otro):
            self.unir(e, x, "arriba", barra, "abajo")
        n = e.nombres
        self.assertEqual({n[i] for i in e.ed.get(ids[3])["postRefs"]}, {n[mid], n[dentro], n[otro]})
        self.assertEqual((e.ed.model["draftLinks"], [d.code for d in e.ed.validate().diagnostics]), ([], []))
        sit, franqueos = corrida(e.ed.model, [(1, {"marcha": True}), (2, {"marcha": False}), (3, {"paro": True})],
                                 {"marcha": False, "paro": False})
        self.assertEqual(franqueos, [["t1"], ["t2"]])
        activas = set(sit[3])
        self.assertTrue({n[dentro], n[otro]} <= activas, activas)
        self.assertTrue(any(x.startswith("E") for x in activas), f"la macroetapa, por su entrada: {activas}")
        self.assertNotIn(n[ids[2]], activas)

    def test_SEDI258_una_transicion_unida_con_el_raton_a_una_barra_activa_todo_lo_de_debajo_en_cualquier_parcial(self):
        """REQ-MOD-03, REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-SIM-03: con los gestos del editor (arrastrar de punto de unión a
        punto de unión), una transición con una barra Y debajo y de ella una macroetapa y dos etapas deja los tres enlaces en el
        modelo, sin diagnósticos ni borradores, y el motor los activa a la vez al franquearla; igual si una de las etapas
        está en un recinto de una encapsulante o en la expansión de la macroetapa (otro parcial)."""
        for destino in ("raiz", "recinto", "expansion"):
            with self.subTest(destino):
                w, e, ids, mid, dentro, otro, barra = self.montar(destino)
                if destino != "raiz":
                    self.assertNotEqual(e.parcial_de(dentro), e.raiz, "la etapa está en otro parcial")
                self.probar(e, ids, mid, dentro, otro, barra)
                e.ed.dirty = False

    def test_SEDI259_la_barra_con_una_etapa_y_una_transicion_por_encima_no_pierde_los_enlaces_de_la_transicion(self):
        """REQ-MOD-03, REQ-EDT-02: con una etapa y una transición por encima de la misma barra (y varias etapas debajo), unidas
        con el ratón en el orden «etapa, transición, etapas», la transición sigue enlazada con todas las de abajo: antes el
        primer borrador (etapa con etapa) impedía enlazar las demás parejas y colgaban de la barra sin activarse. La etapa
        deja sus borradores y el diagnóstico D-ALTERNANCIA, que impide simular."""
        w, e = self.vacio()
        e.colocar("etapa", QPointF(SX + 0, 60))
        x = e.sel[0]
        e.colocar("transicion", QPointF(SX + 200, 60))
        t = e.sel[0]
        for ident, y in ((0, 380), (1, 380), (2, 380)):
            e.colocar("etapa", QPointF(SX + 100 + 200 * ident, y))
        a, b, c = [s["id"] for s in e.M["steps"]][-3:]
        barra = e.poner_barra(QPointF(SX + 300, 200), "Y")
        e.ed.resize_bar(barra, e.ed.bars()[0]["x"], 500)
        e.cambia()
        self.unir(e, x, "abajo", barra, "arriba")
        self.unir(e, t, "abajo", barra, "arriba")
        for s in (a, b, c):
            self.unir(e, s, "arriba", barra, "abajo")
        self.assertEqual(e.ed.get(t)["postRefs"], [a, b, c], "la transición activa las tres")
        self.assertEqual(sorted((d["fromRef"], d["toRef"]) for d in e.ed.model["draftLinks"]), sorted((x, s) for s in (a, b, c)))
        self.assertIn("D-ALTERNANCIA", {d.code for d in e.ed.validate().diagnostics})
        # desunir la etapa de arriba (Supr sobre su conector con la barra) deja el resto como debe
        e.sel = [f"{barra}|{x}|barra"]
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.model["draftLinks"], e.ed.get(t)["postRefs"], e.ed.bars()[0]["arriba"]), ([], [a, b, c], [t]))



@unittest.skipUnless(QT, "PySide6 no está instalado")
class GrafcetParcialSuelto(BaseQt):
    """Encargo C2, punto 1: un grafcet parcial suelto (que no es recinto ni expansión) se crea desde la paleta, y es destino de
    las órdenes de forzado como cualquier otro parcial."""
    NUEVO = "Nuevo grafcet parcial aquí"

    @staticmethod
    def libres(e):
        """Los parciales del modelo que no son el raíz: {nombre: ID}."""
        return {q["label"]: q["id"] for q in e.ed.model["partials"] if q["id"] != e.raiz}

    def test_SEDI280_la_ficha_grafcet_parcial_es_una_ficha_mas_de_la_paleta(self):
        """REQ-EDT-02, REQ-JER-02: la paleta ofrece «Grafcet parcial» (marco redondeado con «G») antes de «Forzado», con su
        nombre, su ayuda, su icono y la figura que se arrastra (el marco vacío, con su centro bajo el puntero); un clic solo
        muestra su ayuda y arrastrarla lleva su clave («parcial»); con ocho fichas la paleta sigue en cuatro filas de dos."""
        from unittest import mock
        from escritorio import propiedades
        from escritorio.diagrama import VACIO_H, VACIO_W
        w, e = self.vacio()
        pa = w.paleta
        textos = [pa.item(i).text() for i in range(pa.count())]
        self.assertEqual(textos[5:], ["Encapsulante", "Grafcet parcial", "Forzado"])
        self.assertEqual((pa.count(), pa.FILAS), (8, 4))
        self.assertEqual(pa.mimeData([pa.item(6)]).text(), "parcial")
        self.assertEqual(propiedades.COLOCABLES[-2:], ("parcial", "forzado"))
        self.assertEqual((propiedades.NOMBRES["parcial"], pa.item(6).toolTip()), ("Grafcet parcial", propiedades.AYUDAS["parcial"]))
        ayuda = propiedades.AYUDAS["parcial"]
        for frase in ("marco redondeado", "hueco", "G1", "Renombrar", "Forzado", "otro marco", "etapas y transiciones"):
            self.assertIn(frase, ayuda)
        # el icono: un marco redondeado (lados con tinta, esquinas sin ella) con la «G» dentro
        img = propiedades.icono("parcial").pixmap(64, 64).toImage()

        def tinta(x, y):
            return img.pixelColor(x, y).alpha() > 0
        self.assertTrue(tinta(32, 10) and tinta(5, 32) and tinta(32, 54) and tinta(59, 32), "los cuatro lados del marco")
        self.assertFalse(any(tinta(x, y) for x, y in ((5, 10), (59, 10), (5, 54), (59, 54))), "con las esquinas redondeadas")
        self.assertTrue(any(tinta(x, y) for x in range(22, 43) for y in range(22, 43)), "y la «G» dentro")
        # la figura que se arrastra: el marco vacío (VACIO_W × VACIO_H) con el centro bajo el puntero y el interior vacío
        pm, punto = propiedades.figura("parcial", 1.0, 1.0)
        self.assertEqual((punto.x(), punto.y()), (VACIO_W / 2 + 4, VACIO_H / 2 + 4))
        self.assertTrue(pm.rect().contains(punto))
        im = pm.toImage()
        self.assertEqual(im.pixelColor(punto.x(), punto.y()).alpha(), 0, "el interior del marco, vacío")
        self.assertGreater(im.pixelColor(punto.x(), 4).alpha(), 0, "su borde de arriba")
        # un clic en la ficha solo muestra su ayuda
        n = len(e.ed.undo_stack)
        pa.itemClicked.emit(pa.item(6))
        self.assertEqual((e.mensaje, e.mensaje_info, w.ayuda.text(), len(e.ed.undo_stack)),
                         (propiedades.AYUDAS["parcial"], True, propiedades.AYUDAS["parcial"], n))
        # arrastrarla: el texto que viaja
        capturados = []

        class FalsoDrag:
            def __init__(self, origen):
                capturados.append(self)

            def setMimeData(self, m):
                self.texto = m.text()

            def setPixmap(self, pm):
                self.pm = pm

            def setHotSpot(self, p):
                self.punto = p

            def exec(self, *a):
                return Qt.DropAction.IgnoreAction
        with mock.patch.object(propiedades, "QDrag", FalsoDrag):
            pa.setCurrentRow(6)
            pa.startDrag(Qt.DropAction.CopyAction)
        self.assertEqual([c.texto for c in capturados], ["parcial"])
        self.assertTrue(capturados[0].pm.rect().contains(capturados[0].punto))

    def test_SEDI281_soltar_la_ficha_en_un_hueco_crea_un_parcial_vacio_con_nombre_unico_y_su_marco(self):
        """REQ-EDT-02, REQ-JER-02, REQ-EDT-05: soltar «Grafcet parcial» en un hueco crea, en una sola operación de deshacer, un
        parcial nuevo y vacío (sin dueño: no es recinto ni expansión) con el primer nombre libre (G1, G2…), y su marco vacío
        centrado en el punto, cuya posición se guarda con el ID del parcial; queda seleccionado. Encima de un elemento o de
        otro marco no crea nada y avisa."""
        from escritorio.diagrama import VACIO_H, VACIO_W, cajas_parciales
        from escritorio.edicion import MSG_SOLAPE_PARCIAL
        from grafcet.view import Vista
        w, e = self.vacio()
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        antes, n = self.estado(e), len(e.ed.undo_stack)
        p = QPointF(500, 300)
        self.assertTrue(e.sobrevolar("parcial", p), "en un hueco se puede soltar")
        self.assertIsNone(w.diagrama.destino)
        self.soltar_ficha("parcial", p)
        self.assertEqual(list(self.libres(e)), ["G1"])
        g1 = self.libres(e)["G1"]
        parte = next(q for q in e.ed.model["partials"] if q["id"] == g1)
        self.assertEqual((parte["stepRefs"], parte["transitionRefs"], "ownerRef" in parte), ([], [], False))
        self.assertEqual(e.ed.partial_roles()[g1]["kind"], "root", "ni recinto ni expansión")
        self.assertEqual((len(e.ed.undo_stack), e.sel, e.mensaje_info), (n + 1, [g1], True))
        b = cajas_parciales(e.M)[g1]
        self.assertEqual((b["x1"] - b["x0"], b["y1"] - b["y0"]), (VACIO_W, VACIO_H))
        self.assertLessEqual(abs((b["x0"] + b["x1"]) / 2 - 500), 10, "centrado en el punto, en la rejilla")
        self.assertLessEqual(abs((b["y0"] + b["y1"]) / 2 - 300), 10)
        self.assertEqual(self.pos(e)[g1], (b["x0"] - SX, b["y0"]), "su posición, en la presentación, con el ID del parcial")
        marco = next(q for q in e.M["partials"] if q["id"] == g1)
        self.assertEqual((marco["kind"], marco["vacio"], marco["label"]), ("partial", True, "G1"))
        pura = Vista("x", "t", "", lambda: (e.ed.model, e.layout()), e.opciones)
        self.assertEqual(pura.model["partials"], [], "Vista (banco, comparador, simulador) no lleva el parcial vacío")
        hecho = self.estado(e)
        e.deshacer()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), self.libres(e)), (antes, n, {}))
        e.rehacer()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (hecho, n + 1))
        # el nombre es el primero libre: G2 después de G1 y, si G1 se renombra, «G1» vuelve a estar libre
        self.soltar_ficha("parcial", QPointF(900, 300))
        self.assertEqual(sorted(self.libres(e)), ["G1", "G2"])
        e.pedir_texto = lambda *a: "Lavado"
        self.assertEqual(e.renombrar_parcial(g1), "Lavado")
        e.pedir_texto = lambda titulo, etiqueta, actual: actual
        self.soltar_ficha("parcial", QPointF(500, 560))
        self.assertEqual(sorted(self.libres(e)), ["G1", "G2", "Lavado"])
        # encima de un elemento o de otro marco: no crea nada y avisa
        e.colocar("etapa", QPointF(1100, 600))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        for nombre, punto in (("encima de una etapa", QPointF(1130, 600)), ("encima de otro marco", QPointF(560, 320))):
            e.mensaje = ""
            self.assertFalse(e.sobrevolar("parcial", punto), nombre)
            self.assertTrue(w.diagrama.prohibidos, f"{nombre}: la caja, en rojo")
            self.soltar_ficha("parcial", punto)
            self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.mensaje, e.mensaje_info),
                             (antes, n, MSG_SOLAPE_PARCIAL, True), nombre)

    def test_SEDI282_el_marco_vacio_se_selecciona_se_mueve_se_rellena_y_se_renombra(self):
        """REQ-EDT-02, REQ-JER-02, REQ-EDT-05: el marco vacío de un parcial suelto se agarra por su borde (dentro no hay nada que
        agarrar), se arrastra con una sola operación de deshacer, recibe lo que se suelta dentro (que pasa a ser del parcial,
        y entonces el marco es el de sus etapas) y se renombra con el botón derecho o con doble clic en su borde; un nombre
        repetido se rechaza sin dejar nada a medias."""
        from escritorio.diagrama import cajas_parciales, elemento_en
        w, e = self.vacio()
        g1 = e.poner_parcial(QPointF(500, 300))
        b = cajas_parciales(e.M)[g1]
        borde = QPointF(b["x0"], b["y0"] + 50)
        e.seleccionar([])
        self.assertEqual(elemento_en(e.M, borde), g1)
        self.assertEqual(elemento_en(e.M, QPointF(b["x1"] - 45, b["y1"] + 4)), g1, "y su nombre, debajo")
        self.assertIsNone(elemento_en(e.M, QPointF(500, 300)), "dentro del marco, lejos del borde, no hay nada que agarrar")
        n = len(e.ed.undo_stack)
        e.prensar(borde)
        self.assertEqual(e.sel, [g1])
        e.mover(borde + QPointF(100, 0))
        e.mover(borde + QPointF(200, 40))
        e.soltar(borde + QPointF(200, 40))
        b2 = cajas_parciales(e.M)[g1]
        self.assertEqual((b2["x0"] - b["x0"], b2["y0"] - b["y0"], len(e.ed.undo_stack)), (200, 40, n + 1), "una sola operación")
        e.deshacer()
        self.assertEqual(cajas_parciales(e.M)[g1], b)
        e.rehacer()
        # se rellena soltando una etapa dentro: es del parcial y el marco pasa a ser el de la etapa
        c = cajas_parciales(e.M)[g1]
        dentro = QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2)
        self.assertEqual(e.parcial_en(dentro), g1)
        self.soltar_ficha("etapa", dentro)
        s = e.sel[0]
        self.assertEqual(e.parcial_de(s), g1)
        self.assertFalse(next(q for q in e.M["partials"] if q["id"] == g1).get("vacio"), "ya tiene etapas: lo dibuja Vista")
        c = cajas_parciales(e.M)[g1]
        # renombrar con el botón derecho en su borde: pide el nombre con el actual de propuesta
        preguntas = []
        e.pedir_texto = lambda *a: preguntas.append(a) or "Lavado"
        n = len(e.ed.undo_stack)
        opciones = e.menu(QPointF(c["x0"], c["y0"] + 10))
        self.assertEqual(([t for t, _ in opciones], e.sel), (["Renombrar…"], [g1]))
        self.assertEqual(dict(opciones)["Renombrar…"](), "Lavado")
        self.assertEqual(preguntas, [("Renombrar el grafcet parcial", "Nuevo nombre del grafcet parcial G1:", "G1")])
        self.assertEqual((e.nombres[g1], len(e.ed.undo_stack)), ("Lavado", n + 1))
        e.deshacer()
        self.assertEqual(e.nombres[g1], "G1")
        e.rehacer()
        # y con doble clic en su borde (en una etapa, el doble clic sigue pidiendo su etiqueta)
        e.pedir_texto = lambda *a: "Secado"
        self.assertTrue(e.doble(QPointF(c["x0"], c["y0"] + 10)))
        self.assertEqual(e.nombres[g1], "Secado")
        # un nombre repetido se rechaza sin cambiar nada; cancelar o dejar el mismo, tampoco
        g2 = e.poner_parcial(QPointF(900, 500))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.parpadeo.parar()
        e.pedir_texto = lambda *a: "Secado"
        self.assertIsNone(e.renombrar_parcial(g2))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.parpadeo.ids), (antes, n, {g2}))
        self.assertTrue(e.mensaje and not e.mensaje_info and "Secado" in e.mensaje, e.mensaje)
        e.parpadeo.parar()
        self.assertEqual(e.nombres[g2], "G1", "el primer nombre libre: G1 quedó libre al renombrarlo")
        for respuesta in (None, "G1"):
            e.pedir_texto = lambda *a, r=respuesta: r
            self.assertIsNone(e.renombrar_parcial(g2))
            self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertIsNone(e.renombrar_parcial(e.raiz), "el raíz no se renombra desde aquí")

    def test_SEDI283_un_parcial_suelto_sin_etapas_sobrevive_a_guardar_y_abrir_con_su_marco_en_su_sitio(self):
        """REQ-EDT-01, REQ-EDT-02, REQ-DAT-01: dos parciales sueltos sin etapas se guardan y se abren (formato actual, sin
        cambios) con su nombre, su marco vacío en el mismo sitio y el modelo simulable."""
        from escritorio.diagrama import cajas_parciales
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        e.tipo_etapa(e.sel[0], True)
        g1 = e.poner_parcial(QPointF(700, 300))
        g2 = e.poner_parcial(QPointF(700, 500))
        cajas = cajas_parciales(e.M)
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / "proyecto")
            op = open_model(Path(tmp) / "proyecto")
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title,
                                 presentacion=op.presentations[0])
        self.assertEqual(cajas_parciales(otro.M), cajas, "los marcos, en el mismo sitio")
        self.assertEqual([(q["id"], q["label"], q.get("vacio")) for q in otro.M["partials"]],
                         [(g1, "G1", True), (g2, "G2", True)])
        self.assertEqual(self.pos(otro)[g1], self.pos(e)[g1])
        self.assertTrue(otro.ed.validate().can_simulate)
        self.assertEqual(self.libres(otro), {"G1": g1, "G2": g2})

    def test_SEDI284_un_parcial_suelto_es_destino_de_la_ficha_forzado_y_se_borra_con_aviso_y_un_deshacer(self):
        """REQ-JER-02, REQ-JER-03, REQ-EDT-05, REQ-SIM-03: un parcial suelto sale en el diálogo de la ficha «Forzado» (con sus
        etapas, si las tiene) y la orden creada fuerza de verdad ese parcial al simular; Supr sobre su marco lo borra con sus
        órdenes, consultando antes si lo hay, en una sola operación de deshacer (y cancelar no borra nada)."""
        from unittest import mock
        from PySide6.QtWidgets import QMessageBox
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        h = e.sel[0]
        e.tipo_etapa(h, True)
        self.assertIsNone(e.renombrar(h, "H"))
        g1 = e.poner_parcial(QPointF(700, 200))
        c = cajas_parciales(e.M)[g1]
        e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        b = e.sel[0]
        self.assertIsNone(e.renombrar(b, "B"))
        g2 = e.poner_parcial(QPointF(700, 600))
        # la ficha «Forzado» sobre H: el diálogo ofrece los dos parciales sueltos, con las etapas del primero
        pedidas = []
        e.pedir_forzado = lambda datos: pedidas.append(datos) or {"destino": g1, "forma": "explicit", "etapas": [b]}
        self.soltar_ficha("forzado", centro(e.M, h))
        self.assertEqual(pedidas[0]["destinos"], [(g1, "G1"), (g2, "G2")])
        self.assertEqual(pedidas[0]["etapas"], {g1: [(b, "B")], g2: []})
        (f1,) = e.ed.model["forces"]
        self.assertEqual((f1["sourceStepRef"], f1["targetPartialRef"], f1["targetKind"], f1["targetSteps"]), (h, g1, "explicit", [b]))
        self.assertTrue(w.diagrama.cajas_ordenes, "y se dibuja su orden")
        self.assertEqual(e.ed.validate().diagnostics, [])
        # lo construido simula: con H activa, G1 queda forzado a {B}
        situaciones, _ = corrida(e.ed.model, [(1, {})])
        self.assertEqual(situaciones[0], ["B", "H"])
        # el botón derecho en H y el panel de opciones del marco lo describen con nombres
        self.assertIn("Forzar un parcial…", dict(e.menu(centro(e.M, h))))
        e.seleccionar([g1])
        self.assertEqual((w.props.pagina, w.props.ficha_izq.texto.text()), ("marco", "Grafcet parcial G1 · forzado desde H"))
        # una segunda orden, sobre el parcial vacío, y borrar ese parcial con Supr: el aviso, una operación, deshacer
        e.pedir_forzado = lambda datos: {"destino": g2, "forma": "empty", "etapas": []}
        f2 = e.forzar(h)
        planes = []
        e.confirmar_borrado = lambda plan: planes.append(plan) or True
        e.seleccionar([g2])
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.assertTrue(e.borrar())
        self.assertEqual(len(planes), 1, "con una orden que lo apunta, pregunta antes de borrar")
        self.assertTrue({g2, f2} <= set(planes[0]["elements"]), planes[0])
        self.assertEqual((sorted(self.libres(e)), [f["id"] for f in e.ed.model["forces"]], len(e.ed.undo_stack)),
                         (["G1"], [f1["id"]], n + 1))
        self.assertNotIn(g2, cajas_parciales(e.M))
        e.deshacer()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n), "una sola operación de deshacer")
        # el aviso de la ventana dice con nombres lo que se lleva; cancelarlo no borra nada
        e.confirmar_borrado = w._confirmar_borrado
        e.seleccionar([g2])
        with mock.patch("escritorio.ventana.QMessageBox.question", return_value=QMessageBox.StandardButton.No) as pregunta:
            self.assertFalse(e.borrar())
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        texto = pregunta.call_args[0][2]
        self.assertIn("G2", texto)
        self.assertIn("orden", texto)
        self.assertNotRegex(texto, r"\b[a-z]-[0-9a-f]{8,}", "sin ID internos")
        # sin ninguna orden que lo apunte, se borra sin preguntar
        g3 = e.poner_parcial(QPointF(1000, 300))
        e.confirmar_borrado = lambda plan: self.fail("no hay nada que avisar")
        self.assertTrue(e.borrar())
        self.assertNotIn("G3", self.libres(e))

    def test_SEDI285_el_menu_del_hueco_ofrece_un_grafcet_parcial_nuevo_aqui(self):
        """REQ-EDT-02, REQ-JER-02: el botón derecho en un hueco ofrece «Nuevo grafcet parcial aquí» (lo mismo que soltar la
        ficha, centrado en el punto, en una operación); sobre un elemento no se ofrece, y encima de un marco no crea nada y avisa."""
        from escritorio.diagrama import cajas_parciales
        from escritorio.edicion import MSG_SOLAPE_PARCIAL
        w, e = self.vacio()
        opciones = e.menu(QPointF(600, 400))
        self.assertEqual([t for t, _ in opciones], [self.NUEVO])
        n = len(e.ed.undo_stack)
        g1 = dict(opciones)[self.NUEVO]()
        b = cajas_parciales(e.M)[g1]
        self.assertEqual((len(e.ed.undo_stack), e.sel, list(self.libres(e))), (n + 1, [g1], ["G1"]))
        self.assertLessEqual(abs((b["x0"] + b["x1"]) / 2 - 600) + abs((b["y0"] + b["y1"]) / 2 - 400), 20)
        # encima de su propio marco: la opción está, pero no crea nada y avisa
        antes, n = self.estado(e), len(e.ed.undo_stack)
        dict(e.menu(QPointF(600, 400)))[self.NUEVO]()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.mensaje), (antes, n, MSG_SOLAPE_PARCIAL))
        # sobre un elemento (una etapa) no se ofrece: la etapa tiene su menú
        e.colocar("etapa", QPointF(1000, 100))
        self.assertNotIn(self.NUEVO, dict(e.menu(centro(e.M, e.sel[0]))))


@unittest.skipUnless(QT, "PySide6 no está instalado")
class EncuadrarYDependencias(BaseQt):
    """Encargo C2, puntos 2 y 3: «Mostrar dependencias» junto al zoom y «Encuadrar…» en lugar de «Abrir expansión» / «Ir a…»."""

    @staticmethod
    def rayas(w):
        """Los trazos discontinuos grises de las dependencias que hay dibujados."""
        from PySide6.QtWidgets import QGraphicsLineItem
        from escritorio.diagrama import COL
        return [it for it in w.diagrama.scene().items() if isinstance(it, QGraphicsLineItem)
                and it.pen().style() == Qt.PenStyle.CustomDashLine and it.pen().color().name() == COL["muted"]]

    @staticmethod
    def visible(w):
        d = w.diagrama
        return d.mapToScene(d.viewport().rect()).boundingRect()

    def test_SEDI290_el_boton_mostrar_dependencias_esta_junto_al_zoom_en_edicion_y_en_simulacion_y_se_recuerda(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-SIM-03: «Mostrar dependencias» es un botón conmutable junto a los controles del
        zoom, apagado por defecto: sin él no hay trazos discontinuos de macroetapa ni de encapsulante, y con él aparecen (al
        editar y al simular) sin cambiar la selección ni la vista; el estado se recuerda en los ajustes entre sesiones."""
        from escritorio.diagrama import CLAVE_DEPENDENCIAS, cajas_parciales
        from escritorio.ventana import Ventana
        w, e = self.vacio()
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        d = w.diagrama
        b = d.b_dependencias
        self.assertEqual((b.text(), b.isCheckable(), b.isChecked(), d.dependencias), ("Mostrar dependencias", True, False, False))
        lay = d.barra.layout()
        self.assertEqual([lay.itemAt(i).widget() for i in range(lay.count())], [d.b_menos, d.l_zoom, d.b_mas, d.b_ajustar, b],
                         "en la barra del zoom")
        self.assertIn("dependencias", b.toolTip())
        # en edición: una macroetapa con su expansión y una encapsulante con su recinto
        mid = e.poner_macro(QPointF(260, 220))
        e.colocar("encapsulante", QPointF(900, 60))
        enc = e.sel[0]
        r = e.anadir_recinto(enc)
        e.seleccionar([mid])
        self.app.processEvents()
        self.assertEqual(self.rayas(w), [], "por defecto, sin trazos de dependencia")
        marcos, escala, sel = cajas_parciales(e.M), d.escala(), list(e.sel)
        contenido = d.scene().itemsBoundingRect()
        b.click()
        self.app.processEvents()
        self.assertEqual((b.isChecked(), d.dependencias, len(self.rayas(w))), (True, True, 3), "dos de la macroetapa y uno de la encapsulante")
        self.assertEqual((cajas_parciales(e.M), d.escala(), e.sel, d.scene().itemsBoundingRect()), (marcos, escala, sel, contenido),
                         "ni la disposición, ni los marcos, ni la selección, ni la vista")
        self.assertTrue(w.ajustes.value(CLAVE_DEPENDENCIAS, False, type=bool))
        # el trazo de la encapsulante va de ella a su recinto
        un = next(it for it in self.rayas(w) if abs(it.line().x1() - centro(e.M, enc).x()) < 0.01 and abs(it.line().y1() - centro(e.M, enc).y()) < 0.01)
        self.assertTrue(marcos[r]["x0"] <= un.line().x2() <= marcos[r]["x1"] and marcos[r]["y0"] <= un.line().y2() <= marcos[r]["y1"])
        # al simular también hay botón y trazos, con el estado que se dejó
        e.ed.dirty = False
        w.cargar_ejemplo("macroetapa")
        self.app.processEvents()
        self.assertTrue(w.diagrama.b_dependencias.isChecked() and w.diagrama.b_dependencias.isVisible())
        self.assertEqual(len(self.rayas(w)), 2, "la macroetapa del ejemplo, con su expansión")
        w.diagrama.b_dependencias.click()
        self.assertEqual(self.rayas(w), [], "apagado también al simular")
        self.assertFalse(w.ajustes.value(CLAVE_DEPENDENCIAS, False, type=bool))
        w.diagrama.b_dependencias.click()
        # se recuerda entre sesiones: otra ventana con los mismos ajustes arranca con él encendido
        w.a_ejecutar.setChecked(False)
        ini = Path(self.tmp.name) / "a.ini"
        w2 = Ventana(QSettings(str(ini), QSettings.Format.IniFormat), Path(self.tmp.name) / "recup2")
        try:
            w2.resize(1360, 860)
            w2.show()
            w2.nuevo()
            self.app.processEvents()
            self.assertEqual((w2.diagrama.dependencias, w2.diagrama.b_dependencias.isChecked()), (True, True))
            w2.cargar_ejemplo("macroetapa")
            self.app.processEvents()
            self.assertEqual(len(self.rayas(w2)), 2)
        finally:
            w2.a_ejecutar.setChecked(False)
            w2.edicion = None
            w2.deleteLater()

    def test_SEDI291_encuadrar_la_expansion_encaja_su_zona_con_margen_y_la_resalta(self):
        """REQ-EDT-08, REQ-JER-07: «Encuadrar la expansión» (botón derecho y doble clic en la macroetapa, y su botón del panel)
        encaja y centra en la vista la zona entera de la expansión con margen, sin pasar del zoom máximo de «Centrar todo»
        (1,6), deja la vista en zoom manual, selecciona su parcial y lo hace parpadear; no toca el modelo ni el historial. Ya no
        hay «Abrir expansión»."""
        from escritorio.diagrama import MARGEN_AJUSTE, ZOOM_AJUSTE_MAX, cajas_parciales
        w, e = self.vacio()
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        e.ed.dirty = False
        d = w.diagrama
        b = cajas_parciales(e.M)[x.partial]
        zona = QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])
        opciones = e.menu(centro(e.M, mid))
        self.assertEqual([t for t, _ in opciones], ["Encuadrar la expansión", "Renombrar…"])
        self.assertNotIn("Abrir expansión", dict(opciones))
        antes, n, rev = self.estado(e), len(e.ed.undo_stack), e.ed.revision

        def comprobar(como):
            self.app.processEvents()
            vis = self.visible(w)
            self.assertTrue(vis.contains(zona), f"{como}: toda la zona a la vista")
            self.assertLessEqual(d.escala(), ZOOM_AJUSTE_MAX + 1e-9, como)
            centrada = zona.adjusted(-10, -10, 10, 18).center()  # (la caja que se encuadra lleva algo de holgura: el nombre debajo)
            self.assertAlmostEqual(vis.center().x(), centrada.x(), delta=1.5 / d.escala())
            self.assertAlmostEqual(vis.center().y(), centrada.y(), delta=1.5 / d.escala())
            margen = min(zona.left() - vis.left(), vis.right() - zona.right(), zona.top() - vis.top(), vis.bottom() - zona.bottom())
            self.assertGreaterEqual(margen * d.escala(), MARGEN_AJUSTE - 2, f"{como}: con margen")
            self.assertTrue(d._manual, f"{como}: el zoom queda manual")
            self.assertEqual((e.sel, e.parpadeo.ids, e.parpadeo.t.isActive()), ([x.partial], {x.partial}, True), como)
            self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.ed.revision, e.ed.dirty), (antes, n, rev, False), como)
            self.assertTrue(e.mensaje_info and "M1" in e.mensaje, como)
            e.parpadeo.parar()
        dict(opciones)["Encuadrar la expansión"]()
        comprobar("botón derecho")
        d.ajustar()
        e.seleccionar([])
        self.assertTrue(e.doble(centro(e.M, mid)))
        comprobar("doble clic")
        d.ajustar()
        e.seleccionar([mid])
        w.props.ficha_izq.botones["Encuadrar la expansión"].click()
        comprobar("botón del panel")

    def test_SEDI292_encuadrar_la_macroetapa_desde_su_expansion_y_el_tope_de_zoom(self):
        """REQ-EDT-08, REQ-JER-07: al revés, «Encuadrar la macroetapa» (en la zona de la expansión seleccionada y en su entrada
        y su salida) encaja la macroetapa, la selecciona y la hace parpadear; una caja pequeña no se amplía más de 1,6 (el tope de
        «Centrar todo»). Ya no hay «Ir a la macroetapa»."""
        from escritorio.diagrama import ZOOM_AJUSTE_MAX
        w, e = self.vacio()
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        d = w.diagrama
        antes, n = self.estado(e), len(e.ed.undo_stack)
        for como, abrir in (("la zona de la expansión", lambda: e.seleccionar([x.partial])),
                            ("la entrada", lambda: e.seleccionar([x.entry])), ("la salida", lambda: e.seleccionar([x.exit]))):
            d.ajustar()
            abrir()
            ficha = w.props.ficha_izq if como.startswith("la zona") else w.props.ficha_etapa
            self.assertIn("Encuadrar la macroetapa", ficha.textos_visibles(), como)
            self.assertNotIn("Ir a la macroetapa", ficha.textos_visibles(), como)
            ficha.botones["Encuadrar la macroetapa"].click()
            self.app.processEvents()
            self.assertEqual((e.sel, e.parpadeo.ids), ([mid], {mid}), como)
            self.assertTrue(self.visible(w).contains(e.centro(mid)), como)
            self.assertAlmostEqual(d.escala(), ZOOM_AJUSTE_MAX, places=6, msg=f"{como}: una etapa es pequeña, el tope es 1,6")
            e.parpadeo.parar()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n), "solo navegación")
        self.assertEqual([t for t, _ in e.menu(centro(e.M, x.entry))][-2:], ["Encuadrar la macroetapa", "Forzar un parcial…"])

    def test_SEDI293_encuadrar_el_recinto_y_la_encapsulante_en_los_dos_sentidos(self):
        """REQ-EDT-08, REQ-JER-07: desde una encapsulante, «Encuadrar el recinto» (o «los recintos», con varios, todos juntos)
        encaja su marco y lo hace parpadear; desde una etapa del recinto o desde su marco, «Encuadrar la encapsulante». Es solo
        navegación y ya no hay «Ir a la encapsulante»."""
        from escritorio.diagrama import cajas_parciales
        w, e, d = self.con_recinto()
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        e0, r, a = d["e0"], d["r"], d["a"]
        e.ed.dirty = False

        def marco(pid):
            c = cajas_parciales(e.M)[pid]
            return QRectF(c["x0"], c["y0"], c["x1"] - c["x0"], c["y1"] - c["y0"])
        opciones = dict(e.menu(centro(e.M, e0)))
        self.assertIn("Encuadrar el recinto", opciones)
        self.assertNotIn("Encuadrar los recintos", opciones)
        opciones["Encuadrar el recinto"]()
        self.app.processEvents()
        self.assertEqual((e.sel, e.parpadeo.ids), ([r], {r}))
        self.assertTrue(self.visible(w).contains(marco(r)))
        e.parpadeo.parar()
        # desde una etapa del recinto y desde su marco: la encapsulante
        for como, punto in (("etapa", centro(e.M, a)), ("marco", QPointF(marco(r).left(), marco(r).top() + 10))):
            w.diagrama.ajustar()
            e.seleccionar([])
            opciones = dict(e.menu(punto))
            self.assertIn("Encuadrar la encapsulante", opciones, como)
            self.assertNotIn("Ir a la encapsulante", opciones, como)
            opciones["Encuadrar la encapsulante"]()
            self.app.processEvents()
            self.assertEqual((e.sel, e.parpadeo.ids), ([e0], {e0}), como)
            self.assertTrue(self.visible(w).contains(e.centro(e0)), como)
            e.parpadeo.parar()
        # con dos recintos, «Encuadrar los recintos» los encaja a la vez y los selecciona a los dos
        e.pedir_texto = lambda *args: "R2"
        r2 = e.anadir_recinto(e0)
        e.ed.dirty = False
        antes, n = self.estado(e), len(e.ed.undo_stack)
        opciones = dict(e.menu(centro(e.M, e0)))
        self.assertIn("Encuadrar los recintos", opciones)
        self.assertNotIn("Encuadrar el recinto", opciones)
        w.diagrama.ajustar()
        opciones["Encuadrar los recintos"]()
        self.app.processEvents()
        self.assertEqual((e.sel, e.parpadeo.ids), ([r, r2], {r, r2}))
        vis = self.visible(w)
        self.assertTrue(vis.contains(marco(r)) and vis.contains(marco(r2)), "los dos marcos a la vez")
        self.assertEqual(w.props.ficha_izq.isHidden(), True)
        e.parpadeo.parar()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.ed.dirty), (antes, n, False), "solo navegación")

    def test_SEDI294_las_ayudas_y_las_fichas_hablan_de_encuadrar_y_no_de_la_navegacion_antigua(self):
        """REQ-EDT-08, REQ-JER-07, REQ-EDT-02: la ayuda de las fichas de la paleta y del panel de opciones, y los botones de la
        ficha de jerarquía, usan «Encuadrar…»; ya no queda «Abrir expansión» ni «Ir a la macroetapa / encapsulante», ni sus
        operaciones en Edicion, y la vista tiene `encuadrar`."""
        from escritorio import propiedades
        from escritorio.diagrama import VistaDiagrama
        from escritorio.edicion import Edicion
        textos = list(propiedades.AYUDAS.values()) + list(propiedades.PanelPropiedades.AYUDA_JERARQUIA.values())
        for t in textos:
            for viejo in ("Abrir expansión", "Ir a la macroetapa", "Ir a la encapsulante"):
                self.assertNotIn(viejo, t)
        self.assertIn("Encuadrar la expansión", propiedades.AYUDAS["macroetapa"])
        self.assertIn("Encuadrar el recinto", propiedades.AYUDAS["encapsulante"])
        self.assertIn("Encuadrar la expansión", propiedades.PanelPropiedades.AYUDA_JERARQUIA["macro"])
        self.assertIn("Encuadrar la macroetapa", propiedades.PanelPropiedades.AYUDA_JERARQUIA["expansion"])
        orden = propiedades.FichaJerarquia.ORDEN
        for nuevo in ("Encuadrar la expansión", "Encuadrar el recinto", "Encuadrar los recintos", "Encuadrar la encapsulante",
                      "Encuadrar la macroetapa"):
            self.assertIn(nuevo, orden)
        self.assertFalse({"Abrir expansión", "Ir a la macroetapa", "Ir a la encapsulante"} & set(orden))
        self.assertFalse(hasattr(Edicion, "abrir_expansion") or hasattr(Edicion, "ir_a"))
        self.assertTrue(callable(getattr(VistaDiagrama, "encuadrar", None)))
        self.assertIn("Mostrar dependencias", propiedades.AYUDAS["macroetapa"])

    def test_SEDI273_la_leyenda_dice_que_los_trazos_de_dependencia_solo_se_ven_con_el_boton_y_no_habla_de_la_navegacion_antigua(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: la leyenda de la ventana ya no dice que la macroetapa va unida a su expansión por
        trazos discontinuos sin más: explica que esos trazos (macroetapa-expansión y encapsulante-recinto) solo se ven con el
        botón «Mostrar dependencias» de la vista; ningún texto de la ventana habla de «Abrir expansión» ni de «Ir a la…»."""
        import inspect
        from escritorio import ventana
        from escritorio.diagrama import VistaDiagrama
        d = VistaDiagrama()
        boton = d.b_dependencias.text()
        d.deleteLater()
        self.assertEqual(boton, "Mostrar dependencias")
        leyenda = ventana.LEYENDA
        self.assertIn(f"«{boton}»", leyenda, "nombra el botón de la vista")
        self.assertIn("solo se ven con", leyenda)
        self.assertIn("macroetapa con su expansión", leyenda)
        self.assertIn("encapsulante con su recinto", leyenda)
        self.assertNotIn("unida a su expansión", leyenda, "ya no se dibuja siempre")
        fuente = inspect.getsource(ventana)
        for viejo in ("Abrir expansión", "Ir a la macroetapa", "Ir a la encapsulante", "Ir a la expansión"):
            self.assertNotIn(viejo, fuente)


if __name__ == "__main__":
    unittest.main()
