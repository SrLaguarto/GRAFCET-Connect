"""Comparador de decisiones (P-IMP-21): cada lectura hace lo que el comparador le anuncia al responsable.

Para cada cuestión simulable se ejecuta el ejemplo una vez por lectura, con el mismo guion, y se comprueban
los hechos de `checks` (situación, valores, salidas o diagnóstico) tras cada paso indicado. Así el texto
«Qué debe pasar» de cada panel no puede separarse de lo que hace el motor sin que falle una prueba. Elegir
una lectura no es conformidad: estas pruebas no son oráculos del documento 11.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import banco_de_pruebas as banco  # noqa: E402
from decisiones import CATALOGO, POR_ID, RESPUESTAS_HOJA_08, RESPUESTAS_INCORPORADAS  # noqa: E402

from grafcet.profile import SEMANTIC_OPTIONS  # noqa: E402

STABLE = ("pausada-estable", "finalizada")


class Comparador(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "decisiones.json"
        banco.guardar_registro(self.path, banco.nuevo_registro())
        self.cmp = banco.Comparador(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, did, value, k, state, chk):
        where = f"{did} lectura {value}, paso {k}"
        if "code" in chk:
            self.assertIn(chk["code"], [d["code"] for d in state["diagnostics"]], where)
            return
        self.assertIn(state["status"], STABLE, f"{where}: {state.get('diagnostics')}")
        if "situation" in chk:
            self.assertEqual(state["situation"], sorted(chk["situation"]), where)
        for var, val in chk.get("values", {}).items():
            self.assertEqual(state["values"][var], val, f"{where}: {var}")
        for var, val in chk.get("outputs", {}).items():
            self.assertEqual(state["outputs"][var]["value"], val, f"{where}: salida {var}")

    def test_SCMP01_catalogo_coherente(self):
        """REQ-NOR-02, REQ-SEM-09: cada lectura del comparador existe en el perfil, tiene su texto y se comprueba."""
        self.assertEqual(len(POR_ID), len(CATALOGO))
        for d in CATALOGO:
            with self.subTest(decision=d.id):
                values = [v for v, _ in d.choices]
                self.assertEqual(len(values), len(set(values)))
                if not d.simulable:
                    self.assertTrue(d.note, "una cuestión sin simulación explica por qué")
                    continue
                self.assertTrue(set(values) <= set(SEMANTIC_OPTIONS[d.option]["values"]))
                self.assertTrue(set(d.base) <= set(SEMANTIC_OPTIONS) and d.option not in d.base)
                self.assertEqual(set(d.expect), set(values))
                self.assertEqual(set(d.checks), set(values), "cada lectura tiene al menos una comprobación")
                for chk in d.checks.values():
                    self.assertTrue(set(chk) <= set(range(len(d.script) + 1)))

    def test_SCMP02_cada_lectura_hace_lo_que_anuncia(self):
        """REQ-SEM-09, REQ-SEM-01, REQ-ACT-02, REQ-TMP-03, REQ-EVT-03: cada alternativa evoluciona como dice su panel."""
        for d in CATALOGO:
            if not d.simulable:
                continue
            self.cmp.load(d.id)
            for k in range(len(d.script) + 1):
                if k:
                    self.cmp.step()
                view = self.cmp.view()
                for panel in view["panels"]:
                    chk = d.checks[panel["value"]].get(k)
                    if chk is not None:
                        with self.subTest(decision=d.id, lectura=panel["value"], paso=k):
                            self._check(d.id, panel["value"], k, panel["state"], chk)

    def test_SCMP03_las_lecturas_se_distinguen(self):
        """REQ-SEM-09: en cada ejemplo, las lecturas no acaban todas igual (si no, el ejemplo no sirve para elegir)."""
        for d in CATALOGO:
            if not d.simulable:
                continue
            self.cmp.load(d.id)
            seen = []
            for k in range(len(d.script) + 1):
                if k:
                    self.cmp.step()
                seen.append([(p["state"]["status"], tuple(p["state"].get("situation", [])),
                              tuple(sorted((p["state"].get("values") or {}).items())),
                              tuple(sorted((x, o["value"]) for x, o in (p["state"].get("outputs") or {}).items())))
                             for p in self.cmp.view()["panels"]])
            with self.subTest(decision=d.id):
                self.assertTrue(any(len(set(step)) > 1 for step in seen), "todas las lecturas dan lo mismo")

    def test_SCMP04_registro_de_decisiones(self):
        """REQ-NOR-02, REQ-DAT-02: la respuesta se guarda con su origen; los bloques 1 y 2 vienen de la hoja 08."""
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual({k: v["eleccion"] for k, v in doc["decisiones"].items()},
                         {k: v for k, (v, _) in RESPUESTAS_HOJA_08.items()})
        self.assertTrue(all(v["origen"] == "hoja 08" for v in doc["decisiones"].values()))
        self.assertIn("no es conformidad", doc["nota"])
        self.cmp.act("elegir", {"id": "3.1", "value": "A", "comentario": " la etapa no cambia "})
        self.cmp.act("elegir", {"id": "4.5", "value": "abierta"})
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((doc["decisiones"]["3.1"]["eleccion"], doc["decisiones"]["3.1"]["origen"],
                          doc["decisiones"]["3.1"]["comentario"]), ("A", "comparador", "la etapa no cambia"))
        self.assertEqual(doc["decisiones"]["4.5"]["texto"], "Dejar abierta")
        self.assertEqual(list(doc["decisiones"]), sorted(doc["decisiones"], key=lambda x: [int(n) for n in x.split(".")]))
        with self.assertRaises(ValueError):
            self.cmp.choose("3.1", "Z")
        # El comentario se guarda solo, sin elegir; elegir después lo conserva
        self.assertEqual(self.cmp.act("comentar", {"id": "7.2", "comentario": "  quiero verlo antes  "}), {"ok": True})
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((doc["decisiones"]["7.2"]["eleccion"], doc["decisiones"]["7.2"]["comentario"]),
                         (None, "quiero verlo antes"))
        self.cmp.act("comentar", {"id": "3.1", "comentario": "ampliado"})
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((doc["decisiones"]["3.1"]["eleccion"], doc["decisiones"]["3.1"]["comentario"]), ("A", "ampliado"))
        self.assertEqual(self.cmp.view()["decision"]["id"], "1.1", "elegir no cambia la cuestión en pantalla")

    def test_SCMP05_lecturas_por_defecto_son_las_respuestas_incorporadas(self):
        """REQ-SEM-09, REQ-NOR-02: las respuestas incorporadas (hoja 08 y comparador) son las lecturas por defecto; lo abierto se detiene."""
        for did, value in RESPUESTAS_INCORPORADAS.items():
            d = POR_ID[did]
            self.assertIn(value, dict(d.choices), did)
            if d.option is not None:
                self.assertEqual(SEMANTIC_OPTIONS[d.option]["default"], value, did)
        still_open = {d.id for d in CATALOGO} - set(RESPUESTAS_INCORPORADAS)
        self.assertEqual(still_open, {"7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "8.1", "8.2"})
        for did in still_open:
            if POR_ID[did].option is not None:
                self.assertEqual(SEMANTIC_OPTIONS[POR_ID[did].option]["default"], "detener", did)
        self.cmp.load("4.4")
        self.assertEqual(self.cmp.view()["applied"], "B", "el comparador muestra lo que el programa aplica")


if __name__ == "__main__":
    unittest.main()
