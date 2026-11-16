"""Limpieza explícita de uniones ausentes, con las comprobaciones del editor."""
from copy import deepcopy

from grafcet.diagnostics import DiagnosticError


def de_otra_escena(config, catalogo):
    presentes = {s["id"] for s in catalogo}
    return [u for u in config.uniones if u.id not in presentes]


def contar_reunidas(anteriores, config):
    return sum(u.variable in anteriores and anteriores[u.variable] != u.id for u in config.uniones)


def resumen_lectura(config, catalogo, reunidas=0):
    partes = [f"{config.host}:{config.puerto}"]
    if catalogo:
        partes.append("1 señal leída" if len(catalogo) == 1 else f"{len(catalogo)} señales leídas")
    if reunidas:
        partes.append("1 unión se ha vuelto a unir" if reunidas == 1 else f"{reunidas} uniones se han vuelto a unir")
    ausentes = len(de_otra_escena(config, catalogo))
    if ausentes:
        mensaje = "1 unión no está en esta escena" if ausentes == 1 else f"{ausentes} uniones no están en esta escena"
        partes.append(mensaje)
    return " · ".join(partes)


def donde_se_usa(edicion, variable):
    editor = edicion.ed
    usos = editor.usages(variable)
    usos += [{"owner": a["id"]} for a in editor.model["actions"] if a["targetRef"] == variable]
    usos += [{"owner": a["id"]} for a in editor.draft_actions() if a.get("variable") == variable]
    return list(dict.fromkeys(edicion.nombre(u["owner"]) for u in usos))


def quitar_uniones(edicion, config, historial, seleccionadas, borrar_variables=True):
    """Una transacción agrupada; delete_variable es también el control de la tabla de Variables."""
    claves = {(u.variable, u.id) for u in seleccionadas}
    elegidas = [u for u in config.uniones if (u.variable, u.id) in claves]
    if not elegidas:
        return []
    editor = edicion.ed
    antes = deepcopy(config.uniones)
    variables = {v["id"]: v for v in editor.model["variables"]}
    avisos = []
    n = len(editor.undo_stack)
    with editor.group("Quitar uniones de otra escena"):
        if borrar_variables:
            for vid in dict.fromkeys(u.variable for u in elegidas):
                if vid not in variables:
                    continue
                try:
                    editor.delete_variable(vid)
                except DiagnosticError as exc:
                    lugares = donde_se_usa(edicion, vid)
                    motivo = "; ".join(lugares) or "; ".join(d.message for d in exc.diagnostics)
                    avisos.append(f"«{variables[vid]['name']}» se conserva: se usa en {motivo}")
        if len(editor.undo_stack) == n:
            editor._txn("Quitar uniones de otra escena", lambda modelo, presentacion: None, view_only=True)
    config.uniones = [u for u in config.uniones if (u.variable, u.id) not in claves]
    historial.registrar(editor, editor.undo_stack[-1], antes, deepcopy(config.uniones))
    return avisos
