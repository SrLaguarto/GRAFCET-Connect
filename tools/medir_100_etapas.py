"""Carga de 100 etapas y medida de la suelta de una acción (auxiliar de `tests/test_ad118.py`)."""
from time import perf_counter_ns

from PySide6.QtCore import QPointF

from tools import hoja_contactos as hc


def construir(c):
    ed = c.e.ed
    ids = []
    dueno = None
    with ed.group("perfil de 100 etapas"):
        entrada = ed.add_variable("Marcha", "input", {"kind": "bool"})
        salida = ed.add_variable("Motor", "output", {"kind": "bool"})
        recinto = ed.add_partial("Recinto", owner="g")
        for columna in range(4):
            parcial = "g" if columna < 3 else recinto
            x = 200 + columna * 360
            y = 80 if columna < 3 else 140
            cadena = []
            for fila in range(25):
                encapsulante = columna == 2 and fila == 1
                ident = ed.add_step(parcial, str(columna * 25 + fila), initial=fila == 0 and columna < 3,
                                    kind="enclosing" if encapsulante else "ordinary", at=(x, y + 120 * fila))
                if encapsulante:
                    dueno = ident
                if cadena:
                    ed.add_transition(parcial, "Marcha", [cadena[-1]], [ident], at=(x, y + 120 * fila - 60))
                cadena.append(ident)
            ids.extend(cadena)
        ed.add_enclosure(dueno, recinto, [ids[75]])
        for sid in ids[::5]:
            ed.add_continuous_action(sid, salida)
        ed.set_comment(ids[5], "Comentario de la etapa")
    assert entrada
    assert len(ed.model["steps"]) == 100 and len(ed.model["transitions"]) == 96
    validacion = ed.validate()
    assert validacion.can_simulate, [d.message for d in validacion.diagnostics if d.blocks_start]
    c.e.cambia()
    c.mostrar()
    c.w.diagrama.centrar_en(QPointF(540, 680))
    c.w.diagrama.mostrar_dependencias(True)
    hc._bombear(12)
    return ids[5]


def muestra(c, aid, perfil=None):
    e = c.e
    x, y, w, h = e.accion_en_id(aid)["rect"]
    origen = QPointF(x + w, y + h / 2)
    final = origen + QPointF(50, 0)
    e.prensar(origen)
    e.mover(final)
    assert e.enlace and e.enlace.get("nueva") == "der"
    hc._bombear(5)
    assert not e.ed.draft_actions()
    if perfil is not None:
        perfil.enable()
    inicio = perf_counter_ns()
    e.soltar(final)
    suelta = perf_counter_ns()
    hc._bombear(5)
    total = perf_counter_ns()
    if perfil is not None:
        perfil.disable()
    borradores = e.ed.draft_actions()
    assert len(borradores) == 1 and borradores[0].get("etapa")
    assert not e._encima
    assert e.deshacer()
    hc._bombear(5)
    return {"suelta_ms": (suelta - inicio) / 1e6, "total_ms": (total - inicio) / 1e6}
