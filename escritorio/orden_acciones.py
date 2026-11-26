"""Orden visual estable entre acciones completas y pendientes de una misma etapa."""
from __future__ import annotations

from typing import Any

from .geometria.acciones import CLAVE, acciones_etapa as acciones_etapa, ordenar as ordenar


def ids_etapa(editor: Any, sid: str) -> list[str]:
    etapa = next(s for s in editor.model["steps"] if s["id"] == sid)
    fuerzas = [{"id": f["id"]} for f in editor.model["forces"] if f["sourceStepRef"] == sid]
    pendientes = [b for b in editor.draft_actions() if b.get("etapa") == sid]
    pendientes.sort(key=lambda b: b.get("orden", 10 ** 6))
    elementos = [{"id": i} for i in etapa["actionRefs"]] + fuerzas + pendientes
    ordenes = editor.presentation.get(CLAVE, {})
    orden = ordenes.get(sid, []) if isinstance(ordenes, dict) else []
    return [a["id"] for a in ordenar(elementos, orden if isinstance(orden, list) else [])]


def guardar(editor: Any, sid: str, orden: list[str]) -> None:
    """La presentación y los cambios de modelo comparten el grupo de deshacer del llamante."""
    def aplicar(modelo, presentacion):
        ordenes = presentacion.get(CLAVE, {})
        ordenes = dict(ordenes) if isinstance(ordenes, dict) else {}
        ordenes[sid] = list(orden)
        presentacion[CLAVE] = ordenes
    editor._txn("conservar orden de acciones", aplicar, view_only=True)


def sustituir(editor: Any, sid: str, orden: list[str], anterior: str, nuevo: str) -> None:
    final = [nuevo if i == anterior else i for i in orden]
    guardar(editor, sid, final)
    sincronizar_completas(editor, sid, final)


def sincronizar_completas(editor: Any, sid: str, orden: list[str]) -> None:
    refs = next(s for s in editor.model["steps"] if s["id"] == sid)["actionRefs"]
    final = [i for i in orden if i in refs]
    final.extend(i for i in refs if i not in final)
    for posicion, ident in enumerate(final):
        refs = next(s for s in editor.model["steps"] if s["id"] == sid)["actionRefs"]
        actual = refs.index(ident)
        if actual != posicion:
            editor.move_action(ident, posicion - actual)


def colocar_tras(editor: Any, sid: str, ids: list[str], objetivo: str | None) -> None:
    orden = [i for i in ids_etapa(editor, sid) if i not in ids]
    posicion = orden.index(objetivo) + 1 if objetivo in orden else len(orden)
    orden[posicion:posicion] = ids
    guardar(editor, sid, orden)


def mover(editor: Any, sid: str, ident: str, delta: int) -> None:
    orden = ids_etapa(editor, sid)
    posicion = orden.index(ident)
    destino = max(0, min(len(orden) - 1, posicion + delta))
    orden.insert(destino, orden.pop(posicion))
    guardar(editor, sid, orden)
    sincronizar_completas(editor, sid, orden)


def aplicar_vista(vista: dict[str, Any], editor: Any) -> None:
    """No modifica ni el modelo semántico ni los documentos anteriores sin este dato visual."""
    if CLAVE in editor.presentation:
        ordenes = editor.presentation[CLAVE]
        if isinstance(ordenes, dict):
            vista[CLAVE] = {sid: orden for sid, orden in ordenes.items() if isinstance(orden, list)}


def agrupar_pegadas(editor: Any, borradores: list[dict[str, Any]]) -> None:
    """Agrupa las acciones copiadas solas, en el orden en que se veían."""
    from fractions import Fraction

    if len({a.get("grupo") for a in borradores}) == 1 and borradores[0].get("grupo"):
        return
    orden = sorted(borradores, key=lambda a: (Fraction(a["y"]), Fraction(a["x"])))
    grupo = editor.ids.new("grupo")
    x, y = orden[0]["x"], orden[0]["y"]
    editor.update_draft_actions({
        a["id"]: {"grupo": grupo, "orden": n, "x": x, "y": y}
        for n, a in enumerate(orden)
    })
