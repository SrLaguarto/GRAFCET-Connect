"""Proyecto reproducible de carga para los bancos de la versión 2.0."""
from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import IdGenerator
from grafcet.notation import a_nucleo

NOMBRE = "Proyecto de referencia"
PARCIALES = ("Emergencia", "Rearme", "Conducción", "Paro", "Producción", "Preparación", "Parpadeo", "Validación")


def _transicion(ed, parcial, texto, antes, despues, x, y):
    etiquetas = (s["label"] for s in ed.model["steps"])
    formula = a_nucleo(texto, etiquetas)
    tid, error = ed.add_transition(parcial, formula, antes, despues, at=(x, y))
    if error:
        raise ValueError(error.message)
    return tid


def _etapas(ed, parcial, indice, total, x, y, inicial=False, encapsulante=False):
    return [
        ed.add_step(
            parcial, str(indice * 100 + i), initial=inicial and i == 0,
            kind="enclosing" if encapsulante and i == 1 else "ordinary", at=(x, y + i * 110),
        )
        for i in range(total)
    ]


def _cadena(ed, parcial, etapas, x, y, condiciones, cerrar=True):
    for i, (origen, destino) in enumerate(zip(etapas, etapas[1:])):
        tid = _transicion(ed, parcial, condiciones[i % len(condiciones)], [origen], [destino], x, y + 55 + 110 * i)
        if i % 5 == 0:
            ed.set_comment(tid, "Paso de secuencia")
    if cerrar:
        retorno = f"1s/X{ed.get(etapas[-1])['label']}"
        _transicion(ed, parcial, retorno, etapas[-1:], etapas[:1], x, y + 110 * len(etapas))


def _ramas(ed, parcial, etapas, x, y):
    """Inserta una elección con salto y una simultaneidad, ambas con reunión."""
    ed.move(etapas[2], x + 360, y + 110)
    _transicion(ed, parcial, "Avance AND NOT Bloqueo", etapas[:1], etapas[1:2], x, y + 55)
    _transicion(ed, parcial, "Avance AND Bloqueo", etapas[:1], etapas[2:3], x + 360, y + 55)
    _transicion(ed, parcial, "↑Pulso", etapas[1:2], etapas[3:4], x, y + 220)
    _transicion(ed, parcial, "↓Pulso", etapas[2:3], etapas[3:4], x + 360, y + 220)
    _transicion(ed, parcial, "Avance", etapas[3:4], etapas[4:6], x, y + 385)
    ed.move(etapas[4], x, y + 440)
    ed.move(etapas[5], x + 360, y + 440)
    _transicion(ed, parcial, "NOT Avance", etapas[4:6], etapas[6:7], x, y + 590)
    _cadena(ed, parcial, etapas[6:], x, y + 660, ("↑Pulso", "↓Pulso"), cerrar=False)
    _transicion(ed, parcial, "NOT Avance", etapas[-1:], etapas[:1], x - 100, y + 110 * len(etapas))


def _estructura(ed):
    raices = ["g", *(ed.add_partial(f"G{i} {tema}") for i, tema in enumerate(PARCIALES[1:6], 2))]
    ed.rename("g", "G1")
    forzante = None
    for i, parcial in enumerate(raices):
        x, y = 150 + i % 3 * 1050, 100 + i // 3 * 1980
        etapas = _etapas(ed, parcial, i, 13, x, y, inicial=True, encapsulante=i == 3)
        if i == 0:
            condiciones = [f"1s/X{ed.get(s)['label']}" for s in etapas]
            _cadena(ed, parcial, etapas, x, y, condiciones)
        elif i == 4:
            _ramas(ed, parcial, etapas, x, y)
        else:
            prec = ("↑Avance", "↓Avance", "Pulso AND NOT Bloqueo", "C < 3 AND active(`G1.0`) AND Pulso")
            _cadena(ed, parcial, etapas, x, y, prec)
        if i == 2:
            ed.add_force(etapas[1], raices[4], "current")
            forzante = etapas[2]
        if i == 3:
            recinto = ed.add_partial(f"G7 {PARCIALES[6]}", owner=parcial)
            interiores = _etapas(ed, recinto, 6, 10, x + 480, y + 150)
            ed.add_enclosure(etapas[1], recinto, interiores[:1])
            _cadena(ed, recinto, interiores, x + 480, y + 150, ("↑Pulso", "↓Pulso"))
        if i == 5:
            ed.add_force(forzante, parcial, "explicit", etapas[:1])
            macro = ed.add_macro(parcial, "M1", at=(x, y + 13 * 110), expansion_label=f"G8 {PARCIALES[7]}")
            mx, my = x + 470, y + 220
            interiores = _etapas(ed, macro.partial, 7, 10, mx, my + 110)
            ed.move(macro.entry, mx, my)
            ed.move(macro.exit, mx, my + 1210)
            _cadena(ed, macro.partial, [macro.entry, *interiores, macro.exit], mx, my, ("↑Pulso", "↓Pulso"), False)
            _transicion(ed, parcial, "Bloqueo AND ↑Pulso", etapas[-1:], [macro.macro], x + 100, y + 1375)
            _transicion(ed, parcial, "true", [macro.macro], etapas[:1], x + 100, y + 1485)


def _acciones(ed, salidas, contador):
    """Tres acciones por etapa, en la disposición de cajas pegadas del editor."""
    indices = {p["id"]: i for i, p in enumerate(ed.model["partials"])}
    for i, etapa in enumerate(ed.model["steps"]):
        sid, label = etapa["id"], etapa["label"]
        parcial = etapa["partialRef"]
        indice = indices[parcial]
        ed.add_continuous_action(sid, salidas[0])
        ed.add_continuous_action(sid, salidas[1], "Pulso AND NOT Bloqueo")
        # Solo una etapa de G1 está activa: un mismo flanco tiene un único autor para C.
        if parcial == "g":
            ed.add_stored_action(sid, contador, "event", "C + 1", "rise(Pulso)")
        else:
            # Escalona los vencimientos de los parciales que arrancan juntos.
            ed.add_continuous_action(sid, salidas[2], limit_us=750_000 + 10_000 * indice)
        if i % 2 == 0:
            ed.set_comment(sid, f"Etapa {label} de {PARCIALES[indice]}")


def construir():
    """Devuelve un Editor con 100 etapas, una macroetapa y ocho parciales en total."""
    ed = Editor(new_grafcet_document("referencia_v2"), ids=IdGenerator("ref-"))
    with ed.group("Construir proyecto de referencia"):
        for nombre in ("Avance", "Pulso", "Bloqueo"):
            ed.add_variable(nombre, "input", {"kind": "bool"})
        salidas = [ed.add_variable(n, "output", {"kind": "bool"}) for n in ("Motor", "Piloto", "Alarma")]
        contador = ed.add_variable("C", "internal", {"kind": "int"})
        _estructura(ed)
        _acciones(ed, salidas, contador)
    return ed

