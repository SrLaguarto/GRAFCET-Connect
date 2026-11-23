"""SRUT01..SRUT02: `routing._separar_lazos` más rápido (V2-E9, solo rendimiento) da los mismos recorridos que la versión anterior, copiada aquí."""
import copy
import json
import unittest
from pathlib import Path
from random import Random
from unittest import mock
from zipfile import ZipFile

from grafcet import routing
from grafcet.routing import H, SX
from grafcet.view import Vista, layout_from_presentation

REFERENCIA = Path(__file__).with_name("fixtures") / "referencia"


def _separar_lazos_antes(M, out, pos):
    """Preferir carriles sin cruces con enlaces y cajas. Se calcula siempre sobre los recorridos automáticos de todos los
    enlaces, también los colocados a mano (`route` de su estilo): colocar un tramo a mano no mueve a ningún otro enlace, ni
    antes de soltarlo ni después, y el tramo colocado se superpone después, tal como se soltó (P-IMP-113 y P-IMP-118). Así un
    retorno automático no «huye» del tramo que se arrastra hacia él; la separación automática sigue siendo entre los enlaces
    tal como se dibujan sin colocar nada a mano."""
    lazos = [e for e in out if len(e["pts"]) == 6 and (e["rol"] in ("pre", "post") or e.get("cruza"))
             and any(b[1] < a[1] for a, b in zip(e["pts"], e["pts"][1:]))
             and not e.get("orient")]
    ids = {e["id"] for e in lazos}
    fijos = [e for e in out if e["id"] not in ids]
    cajas = [(n["id"], pos[n["id"]][0]-H, pos[n["id"]][1]-H,
              pos[n["id"]][0]+H, pos[n["id"]][1]+H)
             for coll in ("steps", "macros") for n in M.get(coll, [])]
    cajas += [(t["id"], pos[t["id"]][0]-8, pos[t["id"]][1]-3,
               pos[t["id"]][0]+8, pos[t["id"]][1]+3) for t in M["transitions"]]
    # Reservar también las filas de acciones: un carril junto a la etapa puede atravesarlas.
    # Cota conservadora independiente de la fuente del visor; el dibujo no cambia de tamaño.
    for paso in M.get("steps", []):
        acciones = paso.get("actions", [])
        if not acciones:
            continue
        x, y = pos[paso["id"]]
        anchos = [max(80, 24 + 15 * max(len("".join(t.get("t", "") for t in (a.get(k) or [])))
                                            for k in ("text", "cond", "event"))) for a in acciones]
        disposicion = paso.get("actionLayout", "fila")
        columnas = 1 if disposicion == "columna" else 2 if disposicion == "matriz-2" else len(acciones)
        filas = (len(acciones) + columnas - 1) // columnas
        ancho = sum(sorted(anchos, reverse=True)[:columnas]) + 36 * (columnas - 1)
        cajas.append((paso["id"], x + H, y - H - 40, x + H + 26 + ancho,
                      y + H + (filas - 1) * 96 + 24))
    izquierda = min((p[0] for p in pos.values()), default=SX)-70
    derecha = max([p[0] for p in pos.values()] + [c[3] for c in cajas] + [SX])+70

    def envolvente(pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    envolventes = {id(o): envolvente(o["pts"]) for o in fijos}  # (solo rendimiento: un corte exige que las cajas se toquen)

    def cortes(pts, e):
        encontrados = set()
        x0_, y0_, x1_, y1_ = envolvente(pts)
        for otro in fijos:
            ox0, oy0, ox1, oy1 = envolventes[id(otro)]
            if ox1 < x0_ or ox0 > x1_ or oy1 < y0_ or oy0 > y1_:
                continue  # sus cajas no se tocan: ningún tramo de uno puede cruzar ni solaparse con uno del otro
            extremos = {e["tid"], e["sid"]} & {otro["tid"], otro["sid"]}
            for a, b in zip(pts, pts[1:]):
                if a == b: continue
                for c, d in zip(otro["pts"], otro["pts"][1:]):
                    if c == d: continue
                    vertical, otra_vertical = a[0] == b[0], c[0] == d[0]
                    if vertical != otra_vertical:
                        v, w, h, j = (a,b,c,d) if vertical else (c,d,a,b)
                        punto = (v[0],h[1])
                        if min(v[1],w[1]) <= punto[1] <= max(v[1],w[1]) and min(h[0],j[0]) <= punto[0] <= max(h[0],j[0]):
                            # Una unión compartida en un extremo no es un cruce.
                            if extremos and punto in pts and punto in otro["pts"]: continue
                            encontrados.add(punto)
                    elif not extremos:
                        eje, otro_eje = (1,0) if vertical else (0,1)
                        if a[otro_eje] == c[otro_eje] and max(min(a[eje],b[eje]),min(c[eje],d[eje])) < min(max(a[eje],b[eje]),max(c[eje],d[eje])):
                            encontrados.add(((a[0]+b[0])/2,(a[1]+b[1])/2))
        return len(encontrados)

    # Los retornos interiores se colocan primero; los exteriores pueden rodearlos.
    for e in sorted(lazos, key=lambda e: (max(p[1] for p in e["pts"])-min(p[1] for p in e["pts"]),e["id"])):
        original = e["pts"]
        x0 = original[2][0]
        preferida = x0 < min(original[0][0],original[-1][0])
        candidatos = [x0] + [x for n in range(len(lazos)+2) for x in (izquierda-26*n,derecha+26*n)]
        def puntuar(x):
            pts = [original[0],original[1],(x,original[2][1]),(x,original[3][1]),original[4],original[5]]
            choques = sum(1 for ident,l,t,r,b in cajas if ident not in (e["tid"],e["sid"])
                          for a,z in zip(pts,pts[1:]) if
                          (a[0] == z[0] and l < a[0] < r and max(min(a[1],z[1]),t) < min(max(a[1],z[1]),b)) or
                          (a[1] == z[1] and t < a[1] < b and max(min(a[0],z[0]),l) < min(max(a[0],z[0]),r)))
            return (choques, cortes(pts,e), (x < min(original[0][0],original[-1][0])) != preferida, abs(x-x0)), pts
        _, e["pts"] = min((puntuar(x) for x in candidatos), key=lambda v:v[0])
        fijos.append(e)
        envolventes[id(e)] = envolvente(e["pts"])


def modelo_visual(nombre):
    with ZipFile(REFERENCIA / nombre) as z:
        modelo = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("model-"))
        presentacion = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("presentation-"))
    layout = layout_from_presentation(presentacion)
    return Vista(modelo["id"], "t", "", lambda: (modelo, layout), {}, presentation=presentacion).model


def barajar(M, azar, fuerza):
    """Una disposición distinta del mismo modelo: etapas y transiciones movidas por el plano a pasos de rejilla (retornos, cruces, carriles)."""
    for coleccion in ("steps", "macros", "transitions"):
        for x in M.get(coleccion, []):
            if azar.random() < 0.35:
                x["x"] = x["x"] + azar.choice((-1, 1)) * azar.randrange(0, fuerza, 10)
                x["y"] = x["y"] + azar.choice((-1, 1)) * azar.randrange(0, fuerza, 10)
    return M


class LazosIguales(unittest.TestCase):
    def comparar(self, M, etiqueta):
        nuevos = routing.enlaces(copy.deepcopy(M))
        with mock.patch.object(routing, "_separar_lazos", _separar_lazos_antes):
            antiguos = routing.enlaces(copy.deepcopy(M))
        self.assertEqual(nuevos, antiguos, etiqueta)
        return sum(1 for e in nuevos if len(e["pts"]) == 6)

    def test_SRUT01_los_recorridos_coinciden_con_los_de_la_version_anterior_en_los_proyectos_de_referencia(self):
        """REQ-DAT-06: `routing.enlaces` da los mismos recorridos que con la versión anterior de `_separar_lazos` en GEMMA y en Linea larga tal como están."""
        for nombre in ("guia_gemma.grafnet", "linea_larga.grafnet"):
            with self.subTest(nombre):
                recorridos = self.comparar(modelo_visual(nombre), nombre)
                if nombre.startswith("linea"):
                    self.assertGreater(recorridos, 0)  # (GEMMA, tal como está, no tiene retornos: ahí solo importa que coincida)

    def test_SRUT02_los_recorridos_coinciden_con_disposiciones_al_azar(self):
        """REQ-DAT-06: lo mismo con disposiciones al azar de los dos proyectos (muchos retornos, cruces y carriles)."""
        for nombre, veces in (("guia_gemma.grafnet", 14), ("linea_larga.grafnet", 5)):
            M = modelo_visual(nombre)
            azar = Random(11)
            lazos = 0
            for k in range(veces):
                lazos += self.comparar(barajar(copy.deepcopy(M), azar, 400 if k % 2 else 900), (nombre, k))
            self.assertGreater(lazos, 0, nombre)


if __name__ == "__main__":
    unittest.main()
