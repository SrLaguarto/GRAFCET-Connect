"""Identifica un grupo del portapapeles y el punto en el que se puede unir."""
from PySide6.QtCore import QPointF

from . import orden_acciones
from .geometria.acciones import iman_en_punto as geometria_iman


def iman_en_punto(cajas, punto, radio, excluir=()):
    iman = geometria_iman(cajas, punto.toTuple(), radio, excluir)
    return {**iman, "linea": tuple(QPointF(*p) for p in iman["linea"])} if iman is not None else None


def objetivo(edicion, fragmento, punto, radio, sobre_seleccion):
    """Los fragmentos mixtos y las acciones individuales siguen usando el pegado libre."""
    borradores = fragmento.presentation.get("draftActions", [])
    if len(borradores) < 2 or any(d.get("etapa") or d["tipo"] == "forzado" for d in borradores):
        return None
    if set(fragmento.selected) != {d["id"] for d in borradores}:
        return None
    if any(elementos for clase, elementos in fragmento.entities.items() if clase != "expressions"):
        return None
    if fragmento.presentation.get("barras") or fragmento.presentation.get("notes"):
        return None
    if sobre_seleccion:
        seleccionada = edicion.accion_activa()
        if seleccionada:
            return seleccionada
    if edicion.diagrama is not None:
        iman = iman_en_punto(edicion.diagrama.cajas_acciones, punto, radio)
        if iman:
            return iman["objetivo"]
    return None


def acciones_copiadas(editor, fragmento, nuevos):
    """Orden visual del grupo copiado tras reasignar sus identificadores."""
    ids = {nuevos[i] for i in fragmento.selected}
    borradores = [d for d in editor.draft_actions() if d["id"] in ids]
    orden_acciones.agrupar_pegadas(editor, borradores)
    unidos = [d for d in editor.draft_actions() if d["id"] in ids]
    unidos.sort(key=lambda d: d.get("orden", float("inf")))
    return [d["id"] for d in unidos]
