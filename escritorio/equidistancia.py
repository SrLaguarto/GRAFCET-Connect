"""Reserva el nivel de las barras a partir del espacio que ocupan sus vecinos."""
from collections import defaultdict
from fractions import Fraction

from grafcet.editor import _niveles
from grafcet.routing import BARRA_GROSOR, orientacion


def reservar_barras(editor, vista, ids, posiciones, extensiones, paso, margen):
    explicitas = {b["id"]: b["kind"] for b in editor.bars()}
    implicitas = {
        t["id"]: (bool(t.get("simulPre")), bool(t.get("simulPost")))
        for t in vista["transitions"]
        if orientacion(t) == "abajo" and (t.get("simulPre") or t.get("simulPost"))
    }
    if not explicitas and not implicitas:
        return
    pos = editor._positions(editor.presentation)
    for ident, (x, y) in posiciones.items():
        pos.setdefault(ident, (Fraction(str(x)), Fraction(str(y))))
    _, aristas, barras, cadenas = editor._chains(ids, pos)
    iniciales = {s["id"] for s in editor.model["steps"] if s["initial"] is True}
    for nodos, ids_barras in cadenas:
        propios = set(nodos)
        niveles = _niveles(nodos, [(a, b) for a, b in aristas if a in propios],
                           {i: pos[i][1] for i in nodos}, {i: pos[i][0] for i in nodos}, iniciales)
        por_nivel = defaultdict(list)
        for ident, nivel in niveles.items():
            por_nivel[nivel].append(ident)

        requisitos = defaultdict(set)
        for ident in ids_barras:
            arriba, _ = barras[ident]
            if arriba:
                requisitos[max(niveles[i] for i in arriba)].add(explicitas[ident])
        for ident in propios.intersection(implicitas):
            delante, detras = implicitas[ident]
            if delante:
                requisitos[niveles[ident] - 1].add("pre")
            if detras:
                requisitos[niveles[ident]].add("post")
        _reservar_niveles(por_nivel, requisitos, extensiones, paso, margen)


def _reservar_niveles(por_nivel, requisitos, extensiones, paso, margen):
    for nivel, tipos in requisitos.items():
        if nivel not in por_nivel or nivel + 1 not in por_nivel:
            continue
        arriba, abajo = por_nivel[nivel], por_nivel[nivel + 1]
        inferior = max(extensiones.get(i, (0, 0))[1] for i in arriba)
        superior = max(extensiones.get(i, (0, 0))[0] for i in abajo)
        hueco = 2 * paso
        if "pre" in tipos:
            hueco = max(hueco, paso + BARRA_GROSOR + margen + inferior)
        if "post" in tipos:
            hueco = max(hueco, paso + BARRA_GROSOR + margen + superior)
        if tipos.intersection(("Y", "O")):
            grosor = BARRA_GROSOR if "Y" in tipos else 0
            hueco = max(hueco, 2 * (margen + max(inferior, superior + grosor)))
        ident = arriba[0]
        alto, _ = extensiones.get(ident, (0, 0))
        # El núcleo suma ambas caras y el margen antes de redondear a rejilla.
        extensiones[ident] = alto, max(inferior, hueco - superior - margen)
