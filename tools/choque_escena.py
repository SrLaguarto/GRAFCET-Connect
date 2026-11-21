"""Prueba de choque del dibujo del editor (V2-E3, paso 0).

Miles de ediciones al azar con semilla fija sobre GEMMA, el proyecto generado de 100 etapas y Linea larga. Entre una
operación y otra se disparan también los redibujados automáticos (pasos del parpadeo, `_redibujar_edicion`, refresco de E/S,
`mostrar` del último estado, eventos pendientes de Qt). Tras cada paso se comprueba la escena:

  ESC-1  un objeto por elemento del modelo: todo id del modelo tiene figura, toda polilínea de enlace está dibujada y
         ninguna figura pertenece a un elemento inexistente;
  ESC-2  ninguna figura oculta, fuera de la escena, vacía o con geometría no finita (salvo lo que ordena el filtro de parcial);
  ESC-3  la escena coincide con una reconstrucción completa desde cero (`diagrama.dibujar_directo`, el dibujo ítem a ítem sin modelo visual, sobre una escena nueva): posiciones,
         trazos, textos, apilado, `cajas_acciones`, `uniones_acciones` y `cajas_ordenes`;
  ESC-4  `Edicion.M` coincide con el que daría una reconstrucción nueva desde el modelo, y `enlaces(M)` con el cálculo en limpio;
  EXC    una operación lanza una excepción que no es un aviso o rechazo de la propia interfaz.

La secuencia se guarda como datos (objetivos por ordinal, no por id: los ids son UUID al abrir un .grafnet), de modo que se
puede repetir y minimizar con ddmin. Uso:

  python tools/choque_escena.py --proyecto gemma --semilla 7 --ops 300
  python tools/choque_escena.py --largo                      # 3000 / 300 / 500 operaciones
  python tools/choque_escena.py --reproducir fallo.json

Solo lee y ejecuta el programa; escribe únicamente los informes de fallo (por defecto en artifacts/v2_e3/fallos/).
"""
from argparse import ArgumentParser
from copy import deepcopy
from math import isfinite
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from time import perf_counter
import json
import sys
import traceback

import shiboken6

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.entorno_v2_e0 import GEMMA, RAIZ, archivo_referencia, paso, play, ventana  # noqa: E402
from tools.hoja_contactos import _bombear as bombear  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import (QApplication, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem,  # noqa: E402
                               QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem)

LINEA = RAIZ / "tests" / "fixtures" / "referencia" / "linea_larga.grafnet"
SALIDA = RAIZ / "artifacts" / "v2_e3" / "fallos"
TEXTOS = ("marcha", "Paro", "no Paro", "marcha y no Paro", "Seta emergencia", "A+", "x", "↑marcha", "")
COMENTARIOS = ("", "prueba", "Retorno al inicio de ciclo de la máquina", "x")
TIPOS = ("continua", "condicionada", "activacion", "desactivacion", "evento")
PESOS = (("anadir_etapa", 4), ("anadir_transicion", 2), ("anadir_accion", 5), ("anadir_debajo", 1), ("mover", 8),
         ("borrar", 3), ("deshacer", 6), ("rehacer", 3), ("pegar", 3), ("equidistanciar", 2), ("texto_accion", 3),
         ("condicion", 3), ("renombrar", 2), ("comentario", 2), ("flecha", 1), ("girar", 1), ("zoom", 2),
         ("errores", 1), ("dependencias", 2), ("filtro", 1), ("play", 4), ("sim_paso", 1), ("stop", 1),
         ("propiedades", 5), ("cerrar_propiedades", 1),
         # simulación (V2-E4): tramos largos en que cambian entradas y situación
         ("sim_fijar", 7), ("sim_cambio", 5), ("sim_reiniciar", 1), ("sim_filtro", 1), ("navegar", 2))
AUTOMATICOS = ("parpadeo", "redibujar_edicion", "redibujar_senal", "refrescar_modbus", "refrescar", "mostrar_ultimo",
               "eventos", "refrescar_edicion")


class Fallo(Exception):
    def __init__(self, tipo, detalle, indice=None, momento=""):
        super().__init__(f"{tipo}: {detalle}")
        self.tipo, self.detalle, self.indice, self.momento = tipo, detalle, indice, momento


# ------------------------------------------------------------------------------------------------------------ generación
def generar(semilla, n):
    azar = Random(semilla)
    nombres = [x for x, p in PESOS for _ in range(p)]
    secuencia = []
    for _ in range(n):
        reg = {"op": azar.choice(nombres), "k": azar.randrange(10**6), "k2": azar.randrange(10**6),
               "dx": azar.randrange(-15, 16) * 20, "dy": azar.randrange(-15, 16) * 20, "v": azar.randrange(10**6),
               "auto": [{"a": azar.choice(AUTOMATICOS), "k": azar.randrange(10**6), "n": azar.randrange(1, 4)}
                        for _ in range(azar.choice((0, 0, 1, 1, 2, 3)))]}
        if reg["op"] == "mover":
            reg["mitad"] = azar.choice((None, None, "redibujar_edicion", "parpadeo", "mostrar_ultimo"))
        secuencia.append(reg)
    return secuencia


# ------------------------------------------------------------------------------------------------------------ operaciones
def _elige(lista, k):
    return lista[k % len(lista)] if lista else None


def _ids(e):
    m = e.ed.model
    return {"etapas": [s["id"] for s in m["steps"]], "transiciones": [t["id"] for t in m["transitions"]],
            "acciones": [a["id"] for a in m["actions"]] + [b["id"] for b in e.ed.draft_actions()],
            "barras": [b["id"] for b in e.M.get("bars", [])]}


def _punto(e, ident, dx=0, dy=0):
    from escritorio.diagrama import posiciones
    x, y = posiciones(e.M)[ident]
    return QPointF(x + dx, y + dy)


def aplicar(w, r):
    e, d = w.edicion, w.diagrama
    op, k = r["op"], r["k"]
    ids = _ids(e)
    sim = w.modo == "simular"
    if op == "play":
        if not sim:
            while e.ed.undo_stack and not e.ed.validate().can_simulate:  # deshace hasta un estado que se pueda simular
                e.deshacer()
            if e.ed.validate().can_simulate:
                play(w)
        return
    if op == "stop":
        if sim:
            w.a_ejecutar.trigger()
            bombear()
        return
    if op == "sim_paso":
        if sim:
            paso(w, "avanzar", us=1_000_000 * (1 + r["v"] % 3))
        return
    if op in ("sim_fijar", "sim_cambio", "sim_reiniciar"):
        if sim and w.v is not None and w.v.s is not None:
            _operacion_sim(w, r)
        return
    if op == "navegar":
        datos = w.navegacion.datos
        if datos:
            w.navegacion.ir(_elige([x["id"] for x in datos], k), enfocar=False)
            bombear()
        return
    if sim and op not in ("dependencias", "zoom", "filtro", "sim_filtro"):
        return  # en simulación no se edita
    if op == "propiedades":
        tipo = r["v"] % 3
        if tipo == 0 and ids["transiciones"]:
            w.editar_condicion(_elige(ids["transiciones"], k))
        elif tipo == 1 and ids["etapas"]:
            w.editar_etiqueta(_elige(ids["etapas"], k))
        elif e.ed.model["actions"]:
            a = _elige(e.ed.model["actions"], k)
            w.editar_accion(a["stepRef"], a["id"])
        bombear()
        return
    if op == "cerrar_propiedades":
        if w.flot.abierto:
            w.flot._cerrar(False)
        bombear()
        return
    todos = ids["etapas"] + ids["transiciones"]
    if op in ("anadir_etapa", "anadir_transicion"):
        base = _elige(todos, k)
        if base:
            e.colocar("etapa" if op == "anadir_etapa" else "transicion", _punto(e, base, r["dx"] + 120, r["dy"] + 120))
    elif op == "anadir_accion":
        base = _elige(ids["etapas"], k)
        if base:
            e.colocar("accion:" + TIPOS[r["v"] % len(TIPOS)], _punto(e, base, 200 + abs(r["dx"]), r["dy"] // 4))
    elif op == "anadir_debajo":
        e.seleccionar([_elige(todos, k)] if todos else [])
        if e.sel:
            e.anadir_debajo()
    elif op == "mover":
        ident = _elige(todos, k)
        if ident:
            o = _punto(e, ident)
            e.seleccionar([])
            e.prensar(o)
            e.mover(o + QPointF(r["dx"] / 2, r["dy"] / 2))
            comprobar_modelo(w, "en un fotograma del arrastre")
            if r.get("mitad"):
                automatico(w, {"a": r["mitad"], "k": k, "n": 1})
                comprobar(w, lite=True, momento="a mitad de un gesto")
            e.mover(o + QPointF(r["dx"], r["dy"]))
            comprobar_modelo(w, "en el último fotograma del arrastre")
            e.soltar(o + QPointF(r["dx"], r["dy"]))
    elif op == "borrar":
        ident = _elige(todos + ids["acciones"], k)
        if ident:
            e.seleccionar([ident])
            e.borrar()
    elif op == "deshacer":
        e.deshacer()
    elif op == "rehacer":
        e.rehacer()
    elif op == "pegar":
        ident = _elige(todos + ids["acciones"], k)
        if ident:
            e.seleccionar([ident])
            frag = e.copiar_fragmento()
            e.pegar_fragmento(frag, _punto(e, _elige(ids["etapas"], r["k2"]) or ident, r["dx"] + 260, r["dy"] + 260))
    elif op == "equidistanciar":
        ident = _elige(ids["etapas"], k)
        if ident:
            e.seleccionar([ident])
            e.equidistanciar([ident])
    elif op == "texto_accion":
        ident = _elige(ids["acciones"], k)
        if ident:
            e.poner_texto_accion(ident, "texto", TEXTOS[r["v"] % len(TEXTOS)], crear=r["k2"] % 2 == 0)
    elif op == "condicion":
        ident = _elige(ids["transiciones"], k)
        if ident:
            e.poner_condicion(ident, TEXTOS[r["v"] % len(TEXTOS)], crear=r["k2"] % 2 == 0)
    elif op == "renombrar":
        ident = _elige(ids["etapas"], k)
        if ident:
            e.renombrar(ident, str(r["v"] % 400))
    elif op == "comentario":
        ident = _elige(todos, k)
        if ident:
            e.poner_comentario(ident, COMENTARIOS[r["v"] % len(COMENTARIOS)])
    elif op == "flecha":
        ident = _elige([x["id"] for x in e.M.get("links", [])], k)
        if ident:
            e.alternar_flecha(ident)
    elif op == "girar":
        ident = _elige(ids["transiciones"], k)
        if ident:
            e.girar_transiciones("derecha" if r["v"] % 2 else "izquierda", [ident])
    elif op == "zoom":
        d.zoom(1.25 if r["v"] % 2 else 0.8, QPointF(300, 200))
        d.verticalScrollBar().setValue(d.verticalScrollBar().value() + r["dy"])
    elif op == "errores":
        w.b_errores.setChecked(not w.b_errores.isChecked())
        w._alternar_errores(w.b_errores.isChecked())
    elif op == "dependencias":
        d.mostrar_dependencias(not d.dependencias)
    elif op in ("filtro", "sim_filtro"):
        nav = w.navegacion
        n = nav.parcial.count()
        nav.modo.setCurrentIndex(r["v"] % max(1, nav.modo.count()))
        nav.parcial.setCurrentIndex(k % n if n and r["k2"] % 3 else 0)
    bombear()


def _entradas_sim(w):
    s = w.v.s
    return sorted(k for k, var in s.cm.variables.items() if var.role == "input" and var.type.kind == "bool")


def _operacion_sim(w, r):
    """Operaciones de simulación: cambiar 1 o 2 entradas, un guion corto hasta que cambie la situación, o Reiniciar."""
    op, k = r["op"], r["k"]
    s = w.v.s
    entradas = _entradas_sim(w)
    if op == "sim_reiniciar":
        w.reiniciar()
        bombear()
    elif op == "sim_fijar" and entradas:
        elegidas = list(dict.fromkeys(entradas[(k + i * 7) % len(entradas)] for i in range(1 + r["k2"] % 2)))
        paso(w, "fijar", cambios={x: not bool(s.z.values[x]) for x in elegidas})
        bombear()
    elif op == "sim_cambio":
        antes = set(w.v.s.z.situation)
        for intento in range(6):  # (como `_buscar_cambio` del banco, con tope)
            if entradas and intento % 2 == 0:
                x = entradas[(k + intento) % len(entradas)]
                paso(w, "fijar", cambios={x: not bool(w.v.s.z.values[x])})
            else:
                paso(w, "avanzar", us=1_000_000)
            bombear()
            if set(w.v.s.z.situation) != antes:
                break


def automatico(w, r):
    e, d = w.edicion, w.diagrama
    a = r["a"]
    editando = w.modo == "editar"
    if a == "parpadeo" and editando:
        ids = _ids(e)
        objetivos = [i for i in (_elige(ids["etapas"], r["k"]), _elige(ids["transiciones"], r["k"]),
                                 _elige(ids["acciones"], r["k"])) if i]
        e.parpadeo.iniciar(objetivos)
        for _ in range(r["n"]):
            e.parpadeo.paso()
        if r["k"] % 3 == 0:
            e.parpadeo.parar()
    elif a == "redibujar_edicion" and editando:
        w._redibujar_edicion()
    elif a == "redibujar_senal" and editando:
        e.redibujar.emit()
    elif a == "refrescar_modbus":
        w._refrescar_modbus()
    elif a == "refrescar":
        if w.modo == "simular":
            w.refrescar()
        else:
            w.refrescar_edicion()
    elif a == "mostrar_ultimo" and d._ultimo is not None:
        d.mostrar(*d._ultimo)
    elif a == "eventos":
        bombear(3)
    elif a == "refrescar_edicion" and editando:
        w.refrescar_edicion()


# ------------------------------------------------------------------------------------------------------------ comprobaciones
def _num(x):
    return round(float(x), 4)


def _sin_repetidos(pts):
    """Qt descarta los puntos consecutivos iguales de un camino."""
    return tuple(p for n, p in enumerate(pts) if n == 0 or p != pts[n - 1])


def _pluma(p):
    return (p.color().rgba(), _num(p.widthF()), int(p.style().value), int(p.capStyle().value), int(p.joinStyle().value),
            tuple(_num(v) for v in p.dashPattern()))


def _relleno(b):
    return (b.color().rgba(), int(b.style().value))


def huella_item(i, filtro):
    base = [type(i).__name__, _num(i.zValue()), (_num(i.pos().x()), _num(i.pos().y())), i.data(42), i.data(43), i.toolTip()]
    if not filtro:
        base += [i.isVisible(), _num(i.opacity())]
    if isinstance(i, QGraphicsLineItem):
        ln = i.line()
        base += [tuple(_num(v) for v in (ln.x1(), ln.y1(), ln.x2(), ln.y2())), _pluma(i.pen())]
    elif isinstance(i, (QGraphicsRectItem, QGraphicsEllipseItem)):
        r = i.rect()
        base += [tuple(_num(v) for v in (r.x(), r.y(), r.width(), r.height())), _pluma(i.pen()), _relleno(i.brush())]
    elif isinstance(i, QGraphicsPathItem):
        p = i.path()
        base += [tuple((_num(p.elementAt(n).x), _num(p.elementAt(n).y), int(p.elementAt(n).type.value))
                       for n in range(p.elementCount())), _pluma(i.pen()), _relleno(i.brush())]
    elif isinstance(i, QGraphicsTextItem):
        b = i.boundingRect()
        base += [i.toPlainText(), i.defaultTextColor().rgba(), i.font().key(), (_num(b.width()), _num(b.height()))]
    return tuple(base)


def _provisionales(d):
    return {id(x) for x in [*d._marcas, d.goma, d.cuadro, d.iman, d.destino, *d.prohibidos] if x is not None}


def figuras(d):
    ajenas = _provisionales(d)
    return [i for i in d.scene().items(Qt.SortOrder.DescendingOrder) if id(i) not in ajenas]


def filtro_activo(w):
    nav = w.navegacion
    return nav.parcial.currentData(), nav.modo.currentData()


def esperados(e):
    from escritorio.diagrama import cajas_parciales, enlaces
    m, M = e.ed.model, e.M
    ids = {s["id"] for s in m["steps"]} | {t["id"] for t in m["transitions"]} | {a["id"] for a in m["actions"]}
    ids |= {b["id"] for b in e.ed.draft_actions()} | {b["id"] for b in M.get("bars", [])}
    ids |= {x["id"] for x in M.get("macros", [])} | {f["id"] for f in m["forces"]}
    return ids, [tuple((float(x), float(y)) for x, y in r["pts"]) for r in enlaces(M)], set(cajas_parciales(M))


def comprobar_objetos(w, momento):
    """ESC-1 y ESC-2."""
    d, e = w.diagrama, w.edicion
    sc = d.scene()
    pid, modo = filtro_activo(w)
    cosas = figuras(d)
    transiciones = {t["id"] for t in e.ed.model["transitions"]}
    for i in cosas:
        if i.scene() is not sc:
            raise Fallo("ESC-2", f"ítem fuera de la escena: {type(i).__name__}", momento=momento)
        if shiboken6.ownedByPython(i):  # su envoltorio lo borraría de la escena al morir (p. ej. tras llamar a `parentItem()`)
            raise Fallo("ESC-2", f"ítem de la escena que PySide da por propiedad de Python: {type(i).__name__} {i.data(43)}",
                        momento=momento)
        oculto_esperado = bool(pid and i.data(42) and i.data(42) != pid and modo == "ocultar")
        if i.isVisible() == oculto_esperado:
            raise Fallo("ESC-2", f"{type(i).__name__} {'oculto' if oculto_esperado is False else 'visible'} sin motivo "
                                 f"(elementos {i.data(43)}, parcial {i.data(42)})", momento=momento)
        opaco = 0.18 if (pid and i.data(42) and i.data(42) != pid and modo == "atenuar") else 1.0
        if abs(i.opacity() - opaco) > 1e-9:
            raise Fallo("ESC-2", f"opacidad {i.opacity()} en lugar de {opaco} ({type(i).__name__}, {i.data(43)})", momento=momento)
        r = i.sceneBoundingRect()
        if not all(isfinite(v) for v in (r.x(), r.y(), r.width(), r.height())):
            raise Fallo("ESC-2", f"geometría no finita en {type(i).__name__}", momento=momento)
        vacia_legitima = bool(i.data(43)) and all(x in transiciones for x in i.data(43))  # receptividad aún sin escribir
        if isinstance(i, QGraphicsTextItem) and not vacia_legitima and (not i.toPlainText() or r.width() <= 0 or r.height() <= 0):
            raise Fallo("ESC-2", f"texto vacío o sin tamaño ({i.data(43)})", momento=momento)
        if isinstance(i, QGraphicsRectItem) and i.rect().isEmpty() and i.rect().width() == 0 and i.rect().height() == 0:
            raise Fallo("ESC-2", f"rectángulo vacío ({i.data(43)})", momento=momento)
    comprobar_lupa(w, momento)
    registro(w, cosas, momento)  # (también al simular: la escena es incremental en los dos modos)
    if w.modo != "editar":
        return
    ids, rutas, marcos = esperados(e)
    presentes = set()
    for i in cosas:
        presentes |= set(i.data(43) or ())
    for ident in ids:
        if ident not in presentes:
            raise Fallo("ESC-1", f"el elemento {e.nombres.get(ident, ident)} ({ident}) no tiene ninguna figura", momento=momento)
    sobran = {x for x in presentes - ids if not x.startswith("enlaceacc:") and x not in marcos
              and x not in {p["id"] for p in e.ed.model["partials"]}}
    if sobran:
        raise Fallo("ESC-1", f"figuras de elementos que ya no existen: {sorted(sobran)[:4]}", momento=momento)
    dibujadas = set()
    for i in cosas:
        if isinstance(i, QGraphicsPathItem):
            p = i.path()
            dibujadas.add(_sin_repetidos(tuple((_num(p.elementAt(n).x), _num(p.elementAt(n).y)) for n in range(p.elementCount()))))
    for pts in rutas:
        if _sin_repetidos(tuple((_num(x), _num(y)) for x, y in pts)) not in dibujadas:
            raise Fallo("ESC-1", f"un enlace no está dibujado: {pts[:2]}…", momento=momento)


def comprobar_lupa(w, momento):
    """La lupa de Propiedades (si está a la vista): su escena incremental cumple lo mismo que el lienzo: un objeto por clave del
    modelo visual, todo en la escena, visible y de nadie más, y coincide con el dibujo directo del mismo modelo (ESC-1 a ESC-3;
    ESC-4 y ESC-5 son del modelo y los comprueba el lienzo)."""
    flot = w.flot
    if flot.principal is None or not flot.principal.isVisible():
        return
    lupa = flot.principal.lupa
    sc = lupa._escena
    if lupa._modelo is None or sc.modelo is None:
        return
    from escritorio import diagrama as dg
    from escritorio.escena.modelo_visual import construir
    cosas = sc.items(Qt.SortOrder.DescendingOrder)
    for i in cosas:
        if i.scene() is not sc or not i.isVisible() or shiboken6.ownedByPython(i):
            raise Fallo("ESC-2", f"lupa: ítem fuera de la escena, oculto o de Python: {type(i).__name__} {i.data(43)}", momento=momento)
    mv = construir(lupa._modelo, {}, None, None, None, lupa._dependencias)
    if set(sc.nodos) != set(mv.objetos) or tuple(sc.modelo.orden) != mv.orden:
        raise Fallo("ESC-1", "lupa: el registro de la escena no tiene un objeto por elemento", momento=momento)
    propios = set()
    for clave, nodo in sc.nodos.items():
        if [d for d, _ in nodo] != list(mv.objetos[clave]) or not all(items for _, items in nodo):
            raise Fallo("ESC-1", f"lupa: el objeto {clave} no coincide con su modelo visual", momento=momento)
        for _, items in nodo:
            propios |= {id(i) for i in items}
    if any(id(i) not in propios for i in cosas):
        raise Fallo("ESC-1", "lupa: ítems en la escena que no son de ningún objeto", momento=momento)
    fresca = QGraphicsScene()
    dg.dibujar_directo(fresca, lupa._modelo, {}, None, None, None, [], [], lupa._dependencias)
    if [huella_item(i, False) for i in cosas] != [huella_item(i, False) for i in fresca.items(Qt.SortOrder.DescendingOrder)]:
        raise Fallo("ESC-3", "lupa: la escena no coincide con el dibujo directo de su modelo", momento=momento)
    fresca.clear()


def registro(w, cosas, momento):
    """ESC-1 sobre la escena incremental (si la hay): un objeto por clave del modelo visual, con todos sus ítems en la escena, y
    ningún ítem suelto fuera del registro."""
    sc = w.diagrama.scene()
    nodos = getattr(sc, "nodos", None)
    if nodos is None or sc.modelo is None or w.diagrama._ultimo is None:
        return
    from escritorio.escena.modelo_visual import construir
    M, S, sel, marcados, naranja = w.diagrama._ultimo
    mv = construir(M, S, sel, marcados, naranja, w.diagrama.dependencias)
    if set(nodos) != set(mv.objetos) or tuple(sc.modelo.orden) != mv.orden:
        falta, sobra = set(mv.objetos) - set(nodos), set(nodos) - set(mv.objetos)
        raise Fallo("ESC-1", f"el registro de la escena no tiene un objeto por elemento: faltan {sorted(falta)[:3]}, sobran "
                             f"{sorted(sobra)[:3]}", momento=momento)
    propios = set()
    for clave, nodo in nodos.items():
        if [d for d, _ in nodo] != list(mv.objetos[clave]) or not all(items for _, items in nodo):
            raise Fallo("ESC-1", f"el objeto {clave} no coincide con su modelo visual o tiene un descriptor sin ítems", momento=momento)
        for _, items in nodo:
            propios |= {id(i) for i in items}
    sueltos = [i for i in cosas if id(i) not in propios]
    if sueltos:
        raise Fallo("ESC-1", f"{len(sueltos)} ítems en la escena que no son de ningún objeto (p. ej. {type(sueltos[0]).__name__} "
                             f"{sueltos[0].data(43)})", momento=momento)


def comprobar_huella(w, momento):
    """ESC-3."""
    from escritorio import diagrama as dg
    d = w.diagrama
    if d._ultimo is None:
        return
    M, S, sel, marcados, naranja = d._ultimo
    fresca = QGraphicsScene()
    uniones, ordenes = [], []
    cajas = getattr(dg, "dibujar_directo", dg.dibujar)(fresca, M, S, sel, marcados, naranja, uniones, ordenes, d.dependencias)
    filtro = bool(filtro_activo(w)[0])
    a = [huella_item(i, filtro) for i in figuras(d)]
    b = [huella_item(i, filtro) for i in fresca.items(Qt.SortOrder.DescendingOrder)]
    if a != b:
        n = next((n for n, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        raise Fallo("ESC-3", f"la escena no coincide con la reconstrucción completa: {len(a)} ítems frente a {len(b)}; primera "
                             f"diferencia en el {n}: {a[n] if n < len(a) else None} frente a {b[n] if n < len(b) else None}",
                    momento=momento)
    for nombre, mia, otra in (("cajas_acciones", d.cajas_acciones, cajas), ("uniones_acciones", d.uniones_acciones, uniones),
                              ("cajas_ordenes", d.cajas_ordenes, ordenes)):
        if mia != otra:
            raise Fallo("ESC-3", f"{nombre} distinto de la reconstrucción completa", momento=momento)
    fresca.clear()


def comprobar_modelo(w, momento):
    """ESC-4: M coincide con el de una reconstrucción nueva y las rutas con el cálculo en limpio."""
    from escritorio.geometria.enlaces import _ajustar_enlaces
    from grafcet import routing
    e = w.edicion
    if w.modo != "editar":
        return
    guardado = (e.M, e.vista, e.nombres, list(e.sel), e.accion)
    antes = deepcopy(e.M)
    try:
        e.reconstruir()
        distinto = antes != e.M
        claves = [k for k in set(antes) | set(e.M) if antes.get(k) != e.M.get(k)]
    finally:
        e.M, e.vista, e.nombres, e.sel, e.accion = guardado
    if distinto:
        raise Fallo("ESC-4", f"Edicion.M está obsoleto frente al modelo (campos distintos: {sorted(claves)})", momento=momento)
    from escritorio.diagrama import enlaces
    limpios = _ajustar_enlaces(e.M, routing.enlaces(e.M))
    if enlaces(e.M) != limpios:
        raise Fallo("ESC-4", "enlaces(M) no coincide con el cálculo en limpio", momento=momento)


def comprobar_diagnosticos(w, momento):
    """ESC-5: los diagnósticos que da la memoria de la validación son los de validar de nuevo."""
    e = w.edicion
    if w.modo != "editar":
        return
    memoria = e.diagnosticos()
    e._memo_validacion = []
    if memoria != e.diagnosticos():
        raise Fallo("ESC-5", "los diagnósticos memorizados no coinciden con una validación nueva", momento=momento)


# ------------------------------------------------------------------------------------------------------------ simulación
def foto_tabla(t):
    """Todo lo que se ve de una tabla de estado: celdas (texto, ayuda, UserRole, color, letra), alto de cada fila, ancho de cada columna
    y alto de la tabla."""
    from PySide6.QtCore import Qt as _Qt
    celdas = []
    for r in range(t.rowCount()):
        fila = []
        for c in range(t.columnCount()):
            it = t.item(r, c)
            fila.append(None if it is None else (it.text(), it.toolTip(), it.data(_Qt.ItemDataRole.UserRole),
                                                 it.foreground().color().rgba(), it.font().key()))
        celdas.append(tuple(fila))
    return (tuple(celdas), tuple(t.rowHeight(r) for r in range(t.rowCount())), tuple(t.columnWidth(c) for c in range(t.columnCount())),
            t.height(), t.minimumHeight(), t.maximumHeight())


def foto_paneles(w):
    nombres = tuple(tuple(getattr(d.contexto, "_nombres", ())) for d in (*w._del_vars, w._del_temp))
    return (foto_tabla(w.t_vars), foto_tabla(w.t_temp), w.c_temp.isVisibleTo(w), nombres, w.sc_entradas.height(),
            w.sc_entradas.minimumHeight(), w.sc_entradas.maximumHeight())


def comprobar_tablas(w, momento):
    """ESC-6: las tablas de Variables y Temporizadores son las que deja la rutina completa (`_variables`) con el estado de ahora."""
    bombear(1)
    antes = foto_paneles(w)
    completa = getattr(w, "_variables_completo", w._variables)
    completa(w.v.model, w.v.state())
    bombear(1)
    despues = foto_paneles(w)
    if antes != despues:
        for nombre, a, b in zip(("t_vars", "t_temp", "c_temp", "contextos", "alto_entradas", "min_entradas", "max_entradas"), antes, despues):
            if a != b:
                raise Fallo("ESC-6", f"las tablas no son las de la rutina completa: difiere {nombre}", momento=momento)


def comprobar_traza(w, momento):
    """ESC-7: la traza tiene las filas, textos y colores de construirla de cero desde `S["trace"]`, desplazada al final."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QListWidgetItem
    from escritorio.diagrama import COL
    from escritorio.ventana import TRAZA
    S = w.v.state()
    defecto = QListWidgetItem("").foreground().color().rgba()
    esperado = [(f"{r['time']:>9}   {r['text']}", QColor(COL[TRAZA[r["kind"]]]).rgba() if r["kind"] in TRAZA else defecto)
                for r in S.get("trace", [])]
    real = [(w.traza.item(i).text(), w.traza.item(i).foreground().color().rgba()) for i in range(w.traza.count())]
    if real != esperado:
        raise Fallo("ESC-7", f"la traza no es la de construirla de cero: {len(real)} filas frente a {len(esperado)}", momento=momento)
    barra = w.traza.verticalScrollBar()
    if barra.value() != barra.maximum():
        raise Fallo("ESC-7", "la traza no está desplazada al final", momento=momento)


def comprobar_entradas(w, momento):
    """ESC-8: texto, marcado, habilitado y estilo de cada botón y campo de entrada son los que da el estado."""
    S = w.v.state()
    estable = S["status"] == "pausada-estable"
    valores = S.get("values", {})
    for var, b in w.botones.items():
        if w.modbus.activo:
            continue
        if b.isEnabled() != estable:
            raise Fallo("ESC-8", f"entrada {w.nombre(var)}: habilitada {b.isEnabled()}, debería {estable}", momento=momento)
        if var in w.campos:
            campo = w.campos[var]
            if not campo.hasFocus() and campo.text() != str(valores.get(var, "")):
                raise Fallo("ESC-8", f"campo {w.nombre(var)}: {campo.text()!r} en lugar de {valores.get(var, '')!r}", momento=momento)
            if campo.isEnabled() != estable:
                raise Fallo("ESC-8", f"campo {w.nombre(var)}: habilitado {campo.isEnabled()}, debería {estable}", momento=momento)
            continue
        on = valores.get(var) is True
        esperado = (on, f"{w.nombre(var)} = {1 if on else 0}", on)
        real = (b.isChecked(), b.text(), b.property("activa"))
        if real != esperado:
            raise Fallo("ESC-8", f"entrada {w.nombre(var)}: {real} en lugar de {esperado}", momento=momento)


def comprobar_atajo(w, momento):
    """ESC-9 (H5): tras un `refrescar` (que se salta el dibujo si el estado es idéntico al dibujado), la escena es la del estado vigente."""
    from escritorio import diagrama as dg
    w.refrescar()
    if w.modo != "simular" or w.v is None:
        return
    d = w.diagrama
    S, M = w.v.state(), w.v.model
    estado = S if "time" in S else {}
    fresca = QGraphicsScene()
    dg.dibujar_directo(fresca, M, estado, set(d.seleccion_navegacion), None, None, [], [], d.dependencias)
    filtro = bool(filtro_activo(w)[0])
    if [huella_item(i, filtro) for i in figuras(d)] != [huella_item(i, filtro) for i in fresca.items(Qt.SortOrder.DescendingOrder)]:
        raise Fallo("ESC-9", "tras refrescar, la escena no es la del estado vigente (el atajo del dibujo dejó un estado viejo)",
                    momento=momento)
    fresca.clear()


def comprobar_simulacion(w, momento):
    if w.modo != "simular" or w.v is None or w.v.s is None:
        return
    comprobar_tablas(w, momento)
    comprobar_traza(w, momento)
    comprobar_entradas(w, momento)
    comprobar_atajo(w, momento)


def comprobar(w, lite=False, huella=True, modelo=True, momento=""):
    comprobar_objetos(w, momento)
    if lite:
        return
    if huella:
        comprobar_huella(w, momento)
    comprobar_simulacion(w, momento)
    if modelo:
        comprobar_modelo(w, momento)
        comprobar_diagnosticos(w, momento)


# ------------------------------------------------------------------------------------------------------------ ejecución
def _aviso_de_interfaz(exc):
    t = str(exc)
    return isinstance(exc, RuntimeError) and (" — " in t or t.startswith(("Paso de simulación fallido", "Play no arrancó")))


def reiniciar(w, ruta):
    if w.modo == "simular":
        w.a_ejecutar.setChecked(False)
        bombear()
    if w.edicion is not None:
        w.edicion.parpadeo.parar()
        w.edicion.ed.dirty = False
    if not w.abrir_ruta(ruta):
        raise RuntimeError(f"No se pudo abrir {ruta}")
    bombear()
    w.edicion.confirmar_borrado = lambda plan: True


def ejecutar(w, ruta, secuencia, cada=1, modelo_cada=1, tope_s=None):
    """Repite la secuencia desde el proyecto y devuelve el primer `Fallo` (o None)."""
    reiniciar(w, ruta)
    inicio = perf_counter()
    for i, reg in enumerate(secuencia):
        if tope_s is not None and perf_counter() - inicio > tope_s:
            break
        try:
            aplicar(w, reg)
        except Fallo as f:
            f.indice = i
            return f
        except Exception as exc:  # noqa: BLE001
            if not _aviso_de_interfaz(exc):
                f = Fallo("EXC", f"{reg['op']}: {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}", i, "operación")
                return f
        try:
            if reg["op"] != "mover" or True:
                comprobar(w, huella=i % cada == 0, modelo=i % modelo_cada == 0, momento=f"tras {reg['op']}")
            for a in reg["auto"]:
                try:
                    automatico(w, a)
                except Exception as exc:  # noqa: BLE001
                    if not _aviso_de_interfaz(exc):
                        return Fallo("EXC", f"automático {a['a']}: {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}",
                                     i, "automático")
                bombear(1)
                comprobar(w, huella=i % cada == 0, modelo=False, momento=f"tras el redibujado automático {a['a']}")
        except Fallo as f:
            f.indice = i
            return f
    return None


def ejecutar_nuevo(ruta, secuencia, **kw):
    """Repite la secuencia en una ventana nueva (escena, vista, ajustes y proyecto desde cero): es la única comprobación que vale
    para decir que un fallo se reproduce."""
    with ventana() as w:
        return ejecutar(w, ruta, secuencia, **kw)


def ddmin(ruta, secuencia, tipo, presupuesto_s=300, **kw):
    """Minimiza la secuencia manteniendo el mismo tipo de fallo. Cada candidato se prueba en una ventana nueva, así que solo se acepta
    una reducción que se reproduce desde cero (el estado de la vista o de la escena que dejó una prueba anterior no cuenta). Se
    detiene al agotar el presupuesto y devuelve lo reducido hasta entonces."""
    limite = perf_counter() + presupuesto_s

    def falla(s):
        if perf_counter() > limite:
            return False
        f = ejecutar_nuevo(ruta, s, **kw)
        return f is not None and f.tipo == tipo

    n = 2
    while len(secuencia) >= 2 and perf_counter() < limite:
        trozo = max(1, len(secuencia) // n)
        partes = [secuencia[i:i + trozo] for i in range(0, len(secuencia), trozo)]
        for p in partes:
            if falla(p):
                secuencia, n = p, 2
                break
        else:
            for k in range(len(partes)):
                resto = [x for j, p in enumerate(partes) if j != k for x in p]
                if resto and falla(resto):
                    secuencia, n = resto, max(n - 1, 2)
                    break
            else:
                if n >= len(secuencia):
                    break
                n = min(len(secuencia), n * 2)
    return secuencia


def informe(proyecto, semilla, f, minima, ruta_json, **extra):
    datos = {"proyecto": proyecto, "semilla": semilla, "tipo": f.tipo, "momento": f.momento, "detalle": f.detalle,
             "indice_en_la_secuencia_completa": f.indice, "secuencia_minima": minima, **extra,
             "repetir": f"python tools/choque_escena.py --reproducir {ruta_json}"}
    ruta_json.parent.mkdir(parents=True, exist_ok=True)
    ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return datos


def correr(nombre, ruta, semilla, n, cada=1, modelo_cada=1, minimizar_s=300, salida=SALIDA, w=None):
    """Genera, ejecuta y, si falla, lo confirma desde cero, lo minimiza y escribe el informe. Devuelve (fallo, datos).

    La secuencia del informe falla siempre al repetirla en una ventana nueva (`--reproducir`). Si ni siquiera la secuencia completa
    hasta el fallo se reproduce desde cero (depende de algo que no es la secuencia), se guarda esa secuencia completa y el informe
    lo dice (`reproducido_desde_cero: false`); si el ddmin no consigue reducir, se guarda la completa (`reducida: false`)."""
    secuencia = generar(semilla, n)
    if w is None:
        f = ejecutar_nuevo(ruta, secuencia, cada=cada, modelo_cada=modelo_cada)
    else:
        f = ejecutar(w, ruta, secuencia, cada, modelo_cada)
    if f is None:
        return None, None
    corta = secuencia[:f.indice + 1]
    destino = Path(salida) / f"fallo_{nombre}_{semilla}_{f.tipo}.json"
    desde_cero = ejecutar_nuevo(ruta, corta, cada=1, modelo_cada=1)
    if desde_cero is None or desde_cero.tipo != f.tipo:
        return f, informe(nombre, semilla, f, corta, destino, reproducido_desde_cero=False, reducida=False,
                          nota="la secuencia completa hasta el fallo no lo reproduce en una ventana nueva")
    minima = ddmin(ruta, corta, f.tipo, minimizar_s, cada=1, modelo_cada=1)
    final = ejecutar_nuevo(ruta, minima, cada=1, modelo_cada=1)
    if final is None or final.tipo != f.tipo:
        minima = corta
    return f, informe(nombre, semilla, desde_cero, minima, destino, reproducido_desde_cero=True, reducida=len(minima) < len(corta))


def proyectos(temporal):
    return {"gemma": GEMMA, "linea": LINEA, "ref100": archivo_referencia(Path(temporal))}


# ------------------------------------------------------------------------------------------------------------ línea de órdenes
def main():
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--proyecto", choices=("gemma", "linea", "ref100"))
    ap.add_argument("--semilla", type=int, nargs="*", default=[20261120])
    ap.add_argument("--ops", type=int, default=300)
    ap.add_argument("--cada", type=int, default=1, help="comparación completa (ESC-3) cada N operaciones")
    ap.add_argument("--largo", action="store_true", help="3000 operaciones en GEMMA, 300 en ref100 y 500 en linea")
    ap.add_argument("--reproducir", type=Path)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args()
    with TemporaryDirectory(prefix="choque-") as tmp:
        rutas = proyectos(tmp)
        if a.reproducir:
            d = json.loads(a.reproducir.read_text(encoding="utf-8"))
            f = ejecutar_nuevo(rutas[d["proyecto"]], d["secuencia_minima"])
            print("sin fallo" if f is None else f"{f.tipo} ({f.momento}): {f.detalle}")
            return 0 if f is None else 1
        plan = ([("gemma", 3000, 1), ("ref100", 300, 5), ("linea", 500, 5)] if a.largo
                else [(a.proyecto or "gemma", a.ops, a.cada)])
        fallos = 0
        for nombre, n, cada in plan:
            for semilla in a.semilla:
                t = perf_counter()
                f, datos = correr(nombre, rutas[nombre], semilla, n, cada=cada, modelo_cada=cada, salida=a.salida)
                print(f"{nombre} semilla {semilla}: {n} operaciones en {perf_counter() - t:.0f} s: "
                      + ("sin fallos" if f is None else f"FALLO {f.tipo} -> {datos['repetir']}"), flush=True)
                fallos += f is not None
        return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
