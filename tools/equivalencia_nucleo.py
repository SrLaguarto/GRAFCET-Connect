"""Huellas del comportamiento del núcleo `grafcet/` sobre los proyectos de referencia (V2-E3, paso 9).

Calcula, para cada proyecto (ejemplos de aula, fixtures, guía GEMMA, proyecto generado de 100 etapas y Linea larga), resúmenes
canónicos de lo que el núcleo devuelve: revisión, diagnósticos (en su orden), enlaces, estructura de la vista y la evolución de una
simulación de N pasos, antes y después de una serie de ediciones con deshacer y rehacer. Sirve para comprobar que un cambio de
rendimiento no cambia ningún resultado: se ejecuta con el árbol anterior y con el nuevo y se comparan los JSON (o contra el
`tests/fixtures/equivalencia_nucleo.json` que se generó con el árbol anterior).

  python tools/equivalencia_nucleo.py SALIDA.json            # con el árbol donde está este fichero
  python tools/equivalencia_nucleo.py SALIDA.json --pasos 12
"""
from argparse import ArgumentParser
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from grafcet.builder import M  # noqa: E402
from grafcet.editor import Editor  # noqa: E402
from grafcet.ids import IdGenerator  # noqa: E402
from grafcet.model import compute_revision, validate_model  # noqa: E402
from grafcet.persistence import open_model  # noqa: E402
from grafcet.profile import normalize_options  # noqa: E402
from grafcet.view import Vista, layout_from_presentation, presentation_for  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"


def h(valor):
    """Resumen estable de cualquier estructura de datos."""
    return sha256(json.dumps(valor, sort_keys=True, default=repr, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def diagnosticos(lista):
    return [asdict(d) if hasattr(d, "__dataclass_fields__") else repr(d) for d in lista]


def vista_de(ed):
    pres = ed.presentation
    return Vista(ed.model["id"], "t", "", lambda: (ed.model, layout_from_presentation(pres)), normalize_options(None),
                 hidden=ed.hidden_labels(), bars=ed.bars(), link_styles=ed.link_styles(), draft_actions=[],
                 action_layouts=ed.action_layouts(), comments=ed.comments(), orientations=ed.transition_orientations())


def resumen_editor(ed, pasos):
    """Todo lo que el editor y la vista de edición piden al núcleo, para el estado actual de `ed`."""
    r = validate_model(ed.model)
    v = vista_de(ed)
    out = {"revision": compute_revision(ed.model), "revisionId": ed.model.get("revisionId"),
           "cm_revision": r.model.revision if r.model is not None else None,
           "validacion": h(diagnosticos(r.diagnostics)), "n_diag": len(r.diagnostics), "capacidades": sorted(r.capabilities),
           "puede_simular": r.can_simulate, "editor_validate": h(diagnosticos(ed.validate().diagnostics)),
           "compile_diags": h(diagnosticos(v.compile_diags)), "enlaces": h(v.model["links"]), "n_enlaces": len(v.model["links"]),
           "estructura": h({k: x for k, x in v.model.items() if k != "links"})}
    if r.can_simulate:
        s = v.s
        out["start_diags"] = h(diagnosticos(v.start_diags))
        out["situacion_inicial"] = sorted(s.z.situation)
        entradas = sorted(k for k, var in s.cm.variables.items() if var.role == "input" and var.type.kind == "bool")
        evolucion = [h(v.state())]
        for n in range(pasos):
            try:
                if entradas and n % 3 == 1:
                    v.act("entrada", {"var": entradas[n % len(entradas)]})
                else:
                    v.act("avanzar", {"us": 1_000_000})
            except Exception as exc:  # noqa: BLE001  (el error forma parte del resultado)
                evolucion.append(f"{type(exc).__name__}:{exc}")
                break
            evolucion.append(h(v.state()))
        out["evolucion"] = evolucion
    return out


def ediciones(ed):
    """Una serie de operaciones del editor: mover, cambiar la presentación, deshacer y rehacer."""
    out = []
    pasos = [s["id"] for s in ed.model["steps"]]
    if not pasos:
        return out
    ed.move(pasos[0], 400, 80)
    out.append(("mover", resumen_editor(ed, 0)))
    ed.move(pasos[-1], 700, 900)
    out.append(("mover_otra", resumen_editor(ed, 0)))
    ed.add_step(ed.model["steps"][0]["partialRef"], "977", at=(1300, 120))  # un cambio del modelo (cambia la revisión)
    out.append(("anadir_etapa", resumen_editor(ed, 0)))
    ed.rename(ed.model["steps"][0]["id"], "978", repetida=True)
    out.append(("renombrar", resumen_editor(ed, 0)))
    ed.undo()
    out.append(("deshacer_renombrar", resumen_editor(ed, 0)))
    ed.undo()
    out.append(("deshacer_etapa", resumen_editor(ed, 0)))
    ed.undo()
    out.append(("deshacer", resumen_editor(ed, 0)))
    ed.undo()
    out.append(("deshacer2", resumen_editor(ed, 0)))
    ed.redo()
    out.append(("rehacer", resumen_editor(ed, 0)))
    ed.redo()
    out.append(("rehacer2", resumen_editor(ed, 0)))
    return out


def editor_de(doc, pres):
    import copy
    return Editor(copy.deepcopy(doc), copy.deepcopy(pres), ids=IdGenerator("eq-"))  # (ids deterministas: la revisión depende de ellos)


def disposiciones_al_azar(ed, semilla, cuantas):
    """Huella de los enlaces de `cuantas` disposiciones al azar del mismo proyecto (mover etapas y transiciones por todo el plano:
    retornos, cruces, carriles): cubre `routing.enlaces` mucho más allá de la disposición con que se guardó el proyecto."""
    import random
    azar = random.Random(semilla)
    ids = [s["id"] for s in ed.model["steps"]] + [t["id"] for t in ed.model["transitions"]]
    out = []
    for _ in range(cuantas):
        for _ in range(azar.randint(1, 4)):
            ed.move(azar.choice(ids), azar.randrange(0, 1600, 10), azar.randrange(0, 2200, 10))
        out.append(h(vista_de(ed).model["links"]))
    return out


def proyectos(temporal):
    from grafcet.ejemplos_aula import DIDACTICOS
    for clave, (_, _, constructor) in DIDACTICOS.items():
        m, layout = constructor()
        doc = m.doc if isinstance(m, M) else m
        yield f"aula/{clave}", doc, presentation_for(doc, layout)
    sys.path.insert(0, str(RAIZ / "tools"))
    from escritorio.proyecto_archivo import abrir_grafnet
    from escritorio.sello import CLAVE
    rutas = sorted(FIXTURES.rglob("*.grafnet"))
    for ruta in rutas:
        contenedor = abrir_grafnet(ruta, CLAVE)
        try:
            abierto = open_model(contenedor.raiz)
            yield f"fixtures/{ruta.relative_to(FIXTURES).as_posix()}", abierto.doc, (abierto.presentations or [{}])[0]
        finally:
            contenedor.cerrar()
    from tools.proyecto_referencia import construir
    ed = construir()
    yield "generado/referencia_100", ed.model, ed.presentation


def main():
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("--pasos", type=int, default=12)
    a = ap.parse_args()
    resultado = {}
    with TemporaryDirectory(prefix="equivalencia-") as tmp:
        for nombre, doc, pres in proyectos(tmp):
            ed = editor_de(doc, pres)
            resultado[nombre] = {"inicial": resumen_editor(ed, a.pasos),
                                 "ediciones": [(n, x) for n, x in ediciones(ed)]}
            resultado[nombre]["disposiciones"] = disposiciones_al_azar(editor_de(doc, pres), 9, 8 if len(doc["steps"]) > 90 else 25)
            print(nombre, resultado[nombre]["inicial"]["n_diag"], "diagnósticos", flush=True)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, sort_keys=True, default=repr), encoding="utf-8",
                        newline="\n")


if __name__ == "__main__":
    main()
