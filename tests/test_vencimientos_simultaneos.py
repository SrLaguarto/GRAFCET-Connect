"""Vencimientos simultáneos sin tope (U-06, L-04, P-IMP-09): reparto en grupos independientes y comprobación exacta.

La regla no cambia: varios vencimientos en el mismo microsegundo se aceptan solo si el resultado no depende del
orden. Cambia cómo se comprueba (grafcet/independencia.py y engine.check_simultaneous_expiries). El oráculo de estas
pruebas es el algoritmo antiguo: todas las permutaciones aplicadas con run_full y sin tope.
"""
import copy
import dataclasses
import itertools
import random
import time
import unittest

from helpers import M, S, scenario, session

from grafcet import engine, independencia
from grafcet.engine import Session, Stimulus, check_simultaneous_expiries, run_full
from grafcet.independencia import grupos_de_vencimientos
from grafcet.diagnostics import DiagnosticError
from grafcet.model import validate_model

DOS = "delay(2 s, active({}), 0 s)"


def oraculo(cm, z, stim, budget, options):
    """Algoritmo antiguo: todas las permutaciones, sin tope. Devuelve True si el resultado no depende del orden y
    None si aplicar todos juntos no se estabiliza (el motor nuevo no opina en ese caso)."""
    ref = run_full(cm, z, stim, budget, options)
    if ref.status != "estable":
        return None
    for perm in itertools.permutations(stim.expiring):
        cur = z
        for key in perm:
            out = run_full(cm, cur, Stimulus("vencimiento", stim.time, None, (key,)), budget, options)
            if out.status != "estable":
                return False
            cur = out.state
        if not cur.equivalent(ref.state):
            return False
    return True


def primer_vencimiento(cm, options=None, init=None):
    s = session(cm, options=options, init=init)
    stim = s.next_stimulus()
    assert stim is not None and not hasattr(stim, "code") and stim.kind == "vencimiento", stim
    return s, stim


def veredicto(cm, options=None, n=None, init=None):
    """(diagnóstico del motor nuevo, veredicto del oráculo, estímulo)."""
    s, stim = primer_vencimiento(cm, options, init)
    if n is not None:
        assert len(stim.expiring) == n, stim.expiring
    dg = check_simultaneous_expiries(cm, s.z, stim, s.ctl.budget, s.options)
    return dg, oraculo(cm, s.z, stim, s.ctl.budget, s.options), stim


def temporizadores(m, nombres, partial_de=None, ret="2 s"):
    """Por cada nombre X: X0 (inicial) → X1 con delay(ret, active(X0))."""
    for x in nombres:
        p = (partial_de or {}).get(x, "g")
        m.step(f"{x}0", True, partial=p).step(f"{x}1", partial=p)
        m.trans(f"t{x}", [f"{x}0"], [f"{x}1"], f"delay({ret}, active({x}0), 0 s)", partial=p)
    return m


def independientes(n, relleno=0):
    m = M().var("e")
    for i in range(n):
        m.partial(f"P{i}")
    temporizadores(m, [f"A{i}" for i in range(n)], {f"A{i}": f"P{i}" for i in range(n)})
    for j in range(relleno):
        m.step(f"R{j}a", True).step(f"R{j}b").step(f"R{j}c")
        m.trans(f"r{j}1", [f"R{j}a"], [f"R{j}b"], "e").trans(f"r{j}2", [f"R{j}b"], [f"R{j}c"], "e")
        m.trans(f"r{j}3", [f"R{j}c"], [f"R{j}a"], "e")
    return m.compile()


def ramas_paralelas(n):
    """n ramas en paralelo de un mismo parcial que convergen en Y: todas vencen a la vez."""
    m = M()
    ramas = [f"X{i}" for i in range(n)]
    temporizadores(m, ramas)
    m.step("Z")
    m.trans("conv", [f"X{i}1" for i in range(n)], ["Z"], "true")
    return m.compile()


def ramas_sin_convergencia(n):
    m = M()
    temporizadores(m, [f"X{i}" for i in range(n)])
    return m.compile()


# --- Familias para el oráculo ---------------------------------------------------------

def f_parciales_independientes():
    return independientes(3)


def f_paralelas_convergencia():
    return ramas_paralelas(3)


def f_misma_etapa_mismo_retardo():
    """Dos transiciones salen de A con el mismo retardo: el orden importa (A→B o A→C)."""
    m = M().step("A", True).step("B").step("C")
    m.trans("t1", ["A"], ["B"], DOS.format("A")).trans("t2", ["A"], ["C"], "delay(2 s, active(A) AND true, 0 s)")
    return m.compile()


def f_almacenada_compartida_conflicto():
    """Dos parciales memorizan valores distintos en la misma variable en la misma evolución: conflicto (2.1 C)."""
    m = M().partial("Q").var("v", "internal", "int")
    temporizadores(m, ["A"])
    temporizadores(m, ["B"], {"B": "Q"})
    m.stored("A1", "v", "activation", "1").stored("B1", "v", "activation", "2")
    return m.compile()


def _dos_con_cola(valor_b):
    """P memoriza al activar A1; Q memoriza una evolución más tarde (B1 → B2, y al activar B2)."""
    m = M().partial("Q").var("v", "internal", "int")
    temporizadores(m, ["A"])
    temporizadores(m, ["B"], {"B": "Q"})
    m.step("B2", partial="Q").trans("tB2", ["B1"], ["B2"], "true", partial="Q")
    m.stored("A1", "v", "activation", "1" if valor_b != "v + 1" else "v + 1").stored("B2", "v", "activation", valor_b)
    return m.compile()


def f_almacenada_compartida_efecto_orden():
    """Q escribe v una evolución después que P: según el orden gana 1 o 2."""
    return _dos_con_cola("2")


def f_almacenada_compartida_incremento():
    """Dos parciales con v := v + 1 (el segundo una evolución después): se unen y el resultado no depende del orden."""
    return _dos_con_cola("v + 1")


def f_variable_escrita_en_P_leida_en_Q_con_efecto():
    m = M().partial("Q").var("v", "internal")
    temporizadores(m, ["A"])
    m.stored("A1", "v", "activation", "true")
    m.step("B0", True, partial="Q").step("B1", partial="Q")
    m.trans("tB", ["B0"], ["B1"], "delay(2 s, active(B0), 0 s) AND NOT v", partial="Q")
    return m.compile()


def f_variable_escrita_en_P_leida_en_Q_sin_efecto():
    m = M().partial("Q").var("v", "internal")
    temporizadores(m, ["A"])
    m.stored("A1", "v", "activation", "true")
    m.step("B0", True, partial="Q").step("B1", partial="Q")
    m.trans("tB", ["B0"], ["B1"], "delay(2 s, active(B0), 0 s) AND v", partial="Q")
    return m.compile()


def f_salida_continua_compartida():
    m = M().partial("Q").var("y", "output")
    temporizadores(m, ["A"])
    temporizadores(m, ["B"], {"B": "Q"})
    m.cont("A1", "y").cont("B1", "y")
    return m.compile()


def f_forzado_entre_parciales():
    m = M().partial("G").var("p")
    temporizadores(m, ["A"])
    m.step("G0", True, partial="G").step("G1", partial="G")
    m.trans("tg", ["G0"], ["G1"], "delay(2 s, active(G0), 0 s)", partial="G")
    m.force("F", "A1", "G", "explicit", ["G0"])
    return m.compile()


def f_forzado_entre_parciales_vacio():
    m = M().partial("G")
    temporizadores(m, ["A"])
    m.step("G0", True, partial="G").step("G1", partial="G")
    m.trans("tg", ["G0"], ["G1"], "delay(2 s, active(G0), 0 s)", partial="G")
    m.force("F", "A1", "G", "empty")
    return m.compile()


def f_macroetapa():
    m = M().partial("X").var("q")
    m.step("A", True).step("B")
    m.step("E", kind="entry", partial="X").step("K", partial="X").step("Sx", kind="exit", partial="X")
    m.trans("tq", ["E"], ["K"], "q", partial="X").trans("tr", ["K"], ["Sx"], "true", partial="X")
    m.macro("M", "X", "E", "Sx")
    m.trans("tp", ["A"], ["M"], "delay(2 s, active(A), 0 s)").trans("ts", ["M"], ["B"], "true")
    m.partial("W")
    temporizadores(m, ["C"], {"C": "W"})
    return m.compile()


def f_encapsulacion():
    m = M().partial("R")
    m.step("A", True).step("H", kind="enclosing")
    m.step("E0", partial="R").step("E1", partial="R")
    m.trans("t", ["A"], ["H"], "delay(2 s, active(A), 0 s)")
    m.trans("u", ["E0"], ["E1"], "true", partial="R")
    m.enclosure("H", "R", ["E0"]).partial("W")
    temporizadores(m, ["C"], {"C": "W"})
    return m.compile()


def f_flanco_de_actividad_otro_parcial():
    m = M().partial("Q")
    temporizadores(m, ["A"])
    m.step("B0", True, partial="Q").step("B1", partial="Q")
    m.trans("tB", ["B0"], ["B1"], "delay(2 s, active(B0), 0 s) OR rise(active(A1))", partial="Q")
    return m.compile()


def f_limite_de_accion():
    m = M().partial("Q").var("y", "output")
    temporizadores(m, ["A"], {"A": "g"})
    m.step("B0", True, partial="Q").cont("B0", "y", limit_us=2 * S, aid="lim")
    return m.compile()


def f_limite_de_accion_en_la_misma_etapa():
    m = M().var("y", "output")
    m.step("A0", True).step("A1")
    m.trans("tA", ["A0"], ["A1"], DOS.format("A0"))
    m.cont("A0", "y", limit_us=2 * S, aid="lim")
    return m.compile()


def f_base_lee_etapa_de_otro_parcial():
    m = M().partial("Q")
    temporizadores(m, ["A"])
    m.step("B0", True, partial="Q").step("B1", partial="Q")
    m.trans("tB", ["B0"], ["B1"], "delay(2 s, active(A0) AND active(B0), 0 s)", partial="Q")
    return m.compile()


def f_base_lee_etapa_de_otro_parcial_inocua():
    """La base de Q lee una etapa de P que no cambia en ese instante."""
    m = M().partial("Q").var("p")
    temporizadores(m, ["A"])
    m.step("K0", True).step("K1")
    m.trans("tk", ["K0"], ["K1"], "p")
    m.step("B0", True, partial="Q").step("B1", partial="Q")
    m.trans("tB", ["B0"], ["B1"], "delay(2 s, active(K0) AND active(B0), 0 s)", partial="Q")
    return m.compile()


FAMILIAS = {
    # nombre: (constructor, el resultado no depende del orden, grupos que debe repartir el análisis)
    "parciales independientes": (f_parciales_independientes, True, 3),
    "paralelas con convergencia": (f_paralelas_convergencia, True, 1),
    "misma etapa y mismo retardo": (f_misma_etapa_mismo_retardo, False, 1),
    "almacenada compartida con efecto de orden": (f_almacenada_compartida_efecto_orden, False, 1),
    "almacenada compartida v + 1": (f_almacenada_compartida_incremento, True, 1),
    "variable escrita en P y leída en Q con efecto": (f_variable_escrita_en_P_leida_en_Q_con_efecto, False, 1),
    "variable escrita en P y leída en Q sin efecto": (f_variable_escrita_en_P_leida_en_Q_sin_efecto, True, 1),
    "salida continua compartida y no leída": (f_salida_continua_compartida, True, 2),
    "forzado entre parciales": (f_forzado_entre_parciales, False, 1),
    "forzado vacío entre parciales": (f_forzado_entre_parciales_vacio, True, 1),
    "macroetapa": (f_macroetapa, True, 2),
    "encapsulación": (f_encapsulacion, True, 2),
    "flanco de actividad de otro parcial": (f_flanco_de_actividad_otro_parcial, True, 1),
    "acción limitada en otro parcial": (f_limite_de_accion, True, 2),
    "acción limitada en la misma etapa": (f_limite_de_accion_en_la_misma_etapa, True, 1),
    "base que lee otra etapa que cambia": (f_base_lee_etapa_de_otro_parcial, False, 1),
    "base que lee otra etapa que no cambia": (f_base_lee_etapa_de_otro_parcial_inocua, True, 1),
}


def comparar(test, cm, options=None, n=None):
    """Veredicto nuevo frente al oráculo; devuelve (diagnóstico, oráculo, estímulo). Ignora lo que el motor no opina."""
    dg, viejo, stim = veredicto(cm, options, n)
    test.assertIsNotNone(viejo, "el oráculo no puede opinar si aplicar todos juntos no se estabiliza")
    test.assertEqual(dg is None, viejo, f"nuevo={dg and dg.message} oráculo={viejo}")
    return dg, viejo, stim


class Oraculo(unittest.TestCase):
    def test_SVSIM01_familias_contra_el_oraculo(self):
        """REQ-TMP-02, REQ-TMP-03: el veredicto nuevo (None o bloqueo) coincide con el de todas las permutaciones."""
        for nombre, (construir, no_depende, grupos) in FAMILIAS.items():
            with self.subTest(nombre):
                cm = construir()
                dg, viejo, stim = comparar(self, cm)
                self.assertEqual(viejo, no_depende)
                self.assertEqual(len(grupos_de_vencimientos(cm, stim.expiring)), grupos)
                if dg is not None:
                    self.assertEqual(dg.evidence["capacidad"], "temporal.coincidencias")
                    self.assertIn("depende del orden", dg.message)

    def test_SVSIM02_modelos_aleatorios_contra_el_oraculo(self):
        """REQ-TMP-02, REQ-TMP-03: 400 modelos pequeños con semilla fija; el veredicto nuevo coincide con el antiguo."""
        rng = random.Random(20261126)
        comparados = {True: 0, False: 0}
        repartidos = 0
        for _ in range(400):
            try:
                cm = modelo_aleatorio(rng)
            except DiagnosticError:
                continue
            s = Session(cm, scenario(cm, None, []), budget=10_000)
            if s.start():
                continue
            stim = s.next_stimulus()
            if stim is None or getattr(stim, "kind", None) != "vencimiento" or not 2 <= len(stim.expiring) <= 5:
                continue
            viejo = oraculo(cm, s.z, stim, s.ctl.budget, s.options)
            if viejo is None:
                continue
            dg = check_simultaneous_expiries(cm, s.z, stim, s.ctl.budget, s.options)
            self.assertEqual(dg is None, viejo, f"{stim.expiring}: nuevo={dg and dg.message} oráculo={viejo}")
            comparados[viejo] += 1
            repartidos += len(grupos_de_vencimientos(cm, stim.expiring)) > 1
        self.assertGreater(comparados[True], 30)
        self.assertGreater(comparados[False], 10)
        self.assertGreater(repartidos, 30, "el reparto en grupos tiene que usarse en la mayoría de modelos")

    def test_SVSIM03_ejecucion_real_nombra_el_grupo_y_bloquea(self):
        """REQ-TMP-02, REQ-TMP-03: en la sesión, la dependencia del orden detiene el avance con temporal.coincidencias."""
        s = session(f_misma_etapa_mismo_retardo())
        s.run()
        self.assertEqual(s.status, "error")
        self.assertEqual(s.diagnostics[-1].evidence["capacidad"], "temporal.coincidencias")
        self.assertIn("depende del orden", s.diagnostics[-1].message)
        self.assertEqual(s.z.situation, {"A"}, "no se aplica ninguno de los dos")

    def test_SVSIM04_aplicados_juntos_sin_estabilizar_no_opina(self):
        """REQ-TMP-02, REQ-TMP-03: si aplicarlos juntos ya falla, la comprobación no opina y la ejecución real diagnostica."""
        cm = f_almacenada_compartida_conflicto()
        s, stim = primer_vencimiento(cm)
        self.assertEqual(run_full(cm, s.z, stim, s.ctl.budget, s.options).status, "fallo")
        self.assertIsNone(check_simultaneous_expiries(cm, s.z, stim, s.ctl.budget, s.options))
        s.run()
        self.assertEqual(s.status, "error")
        self.assertNotEqual(s.diagnostics[-1].evidence.get("capacidad"), "temporal.coincidencias")
        self.assertNotIn("depende del orden", s.diagnostics[-1].message)


class Contador:
    """Cuenta las llamadas a run_full del motor durante la comprobación."""

    def __enter__(self):
        self.n = 0
        self.original = engine.run_full

        def contando(*a, **k):
            self.n += 1
            return self.original(*a, **k)
        engine.run_full = contando
        return self

    def __exit__(self, *exc):
        engine.run_full = self.original


class SinTope(unittest.TestCase):
    def comprobar(self, cm, n):
        s, stim = primer_vencimiento(cm)
        self.assertEqual(len(stim.expiring), n)
        with Contador() as c:
            dg = check_simultaneous_expiries(cm, s.z, stim, s.ctl.budget, s.options)
        return dg, c.n

    def test_SVSIM05_parciales_independientes_pasan_sin_ejecuciones(self):
        """REQ-TMP-02, REQ-TMP-03: 6 y 8 vencimientos de parciales independientes pasan sin ninguna ejecución extra."""
        for n in (6, 8):
            with self.subTest(n=n):
                cm = independientes(n)
                dg, ejecuciones = self.comprobar(cm, n)
                self.assertIsNone(dg)
                self.assertEqual(ejecuciones, 0)
                self.assertEqual(len(grupos_de_vencimientos(cm, primer_vencimiento(cm)[1].expiring)), n)
                s = session(cm)
                s.run()
                self.assertEqual(s.status, "finalizada")
                self.assertEqual(s.z.situation, {f"A{i}1" for i in range(n)})

    def test_SVSIM06_ramas_paralelas_de_un_parcial_pasan_sin_tope(self):
        """REQ-TMP-02, REQ-TMP-03: 6 ramas en paralelo de un parcial con convergencia pasan; n·2^(n-1) ejecuciones y una de referencia."""
        for n in (5, 6):
            with self.subTest(n=n):
                dg, ejecuciones = self.comprobar(ramas_paralelas(n), n)
                self.assertIsNone(dg)
                self.assertEqual(ejecuciones, 1 + n * 2 ** (n - 1))
        s = session(ramas_paralelas(6))
        s.run()
        self.assertEqual(s.z.situation, {"Z"})

    def test_SVSIM07_seis_temporizadores_con_orden_que_importa_bloquean(self):
        """REQ-TMP-02, REQ-TMP-03: 6 vencimientos en un parcial, uno de ellos con salida alternativa: depende del orden."""
        m = M()
        temporizadores(m, [f"X{i}" for i in range(5)])
        m.step("Y").trans("alt", ["X00"], ["Y"], DOS.format("X00"))
        cm = m.compile()
        dg, _ = self.comprobar(cm, 6)
        self.assertIsNotNone(dg)
        self.assertEqual(dg.evidence["capacidad"], "temporal.coincidencias")
        self.assertIn("depende del orden", dg.message)
        self.assertNotIn("demasiados", dg.message)
        _, viejo, _ = veredicto(cm)
        self.assertFalse(viejo, "el oráculo (todas las permutaciones) coincide")
        s = session(cm)
        s.run()
        self.assertEqual(s.status, "error")
        self.assertEqual(s.diagnostics[-1].evidence["capacidad"], "temporal.coincidencias")

    def test_SVSIM08_el_mensaje_demasiados_no_aparece(self):
        """REQ-TMP-02, REQ-TMP-03: con 10 vencimientos simultáneos (grupo único) tampoco hay tope."""
        dg, ejecuciones = self.comprobar(ramas_sin_convergencia(10), 10)
        self.assertIsNone(dg)
        self.assertEqual(ejecuciones, 1 + 10 * 2 ** 9)

    def test_SVSIM09_agrupacion_conservadora_y_cache(self):
        """REQ-TMP-02, REQ-TMP-03: claves desconocidas dejan todo en un grupo; el análisis se guarda y no altera el modelo."""
        cm = independientes(3)
        self.assertEqual(grupos_de_vencimientos(cm, ["e3", "e1", "e2"]), [("e1",), ("e2",), ("e3",)])
        self.assertEqual(grupos_de_vencimientos(cm, ["e1", "raro", "e2"]), [("e1", "e2", "raro")])
        self.assertEqual(grupos_de_vencimientos(cm, ["e1"]), [("e1",)])
        self.assertEqual(grupos_de_vencimientos(cm, []), [])
        sin_cache = copy.copy(cm)
        self.assertIn(independencia._ATRIBUTO, vars(cm))
        del vars(sin_cache)[independencia._ATRIBUTO]
        self.assertEqual(cm, sin_cache, "la caché no entra en la igualdad del modelo")
        self.assertNotIn(independencia._ATRIBUTO, [f.name for f in dataclasses.fields(cm)])
        calculos = []
        original = independencia._analizar
        independencia._analizar = lambda c: calculos.append(1) or original(c)
        try:
            nuevo = independientes(3)
            for _ in range(3):
                grupos_de_vencimientos(nuevo, ["e1", "e2"])
        finally:
            independencia._analizar = original
        self.assertEqual(len(calculos), 1, "se calcula una vez por modelo")

    def test_SVSIM10_tiempos_holgados(self):
        """REQ-TMP-02, REQ-TMP-03: 6 parciales independientes con unas 100 etapas, 6 y 8 ramas: cotas muy holgadas."""
        casos = {"6 independientes + 100 etapas": (independientes(6, 30), 6), "6 ramas": (ramas_paralelas(6), 6),
                 "8 ramas": (ramas_paralelas(8), 8)}
        for nombre, (cm, n) in casos.items():
            with self.subTest(nombre):
                t0 = time.perf_counter()
                dg, _ = self.comprobar(cm, n)
                self.assertIsNone(dg)
                self.assertLess(time.perf_counter() - t0, 120)


def modelo_aleatorio(rng):
    """Modelo pequeño: 2 a 3 parciales con cadenas de temporizadores de 2 s y acoplamientos al azar."""
    npar = rng.randint(2, 3)
    pids = ["g"] + [f"Q{i}" for i in range(1, npar)]
    m = M().var("v", "internal").var("y", "output").var("e")
    for p in pids[1:]:
        m.partial(p)
    cadenas = []
    for i in range(rng.randint(2, 5)):
        p = rng.choice(pids)
        cadenas.append((f"X{i}", p))
        m.step(f"X{i}a", True, partial=p).step(f"X{i}b", partial=p)
    nombres = [x for x, _ in cadenas]
    for x, p in cadenas:
        base = f"active({x}a)"
        if rng.random() < 0.3:
            base += f" AND active({rng.choice(nombres)}a)"
        cond = f"delay(2 s, {base}, 0 s)"
        r = rng.random()
        if r < 0.2:
            cond += " AND NOT v"
        elif r < 0.3:
            cond += " AND v"
        elif r < 0.4:
            cond += f" OR rise(active({rng.choice(nombres)}b))"
        m.trans(f"t{x}", [f"{x}a"], [f"{x}b"], cond, partial=p)
        if rng.random() < 0.3:  # segunda salida de la misma etapa, con el mismo retardo
            m.step(f"{x}c", partial=p).trans(f"u{x}", [f"{x}a"], [f"{x}c"], f"delay(2 s, active({x}a), 0 s)", partial=p)
        if rng.random() < 0.25:
            m.stored(f"{x}b", "v", "activation", rng.choice(["true", "false"]))
        if rng.random() < 0.25:
            m.cont(f"{x}b", "y")
        if rng.random() < 0.2:
            m.step(f"{x}d", partial=p).trans(f"w{x}", [f"{x}b"], [f"{x}d"], "true", partial=p)
    if rng.random() < 0.3 and len(cadenas) > 1:
        a, b = rng.sample(nombres, 2)
        pb = dict(cadenas)[b]
        m.force(f"F{a}", f"{a}b", pb, rng.choice(["empty", "initial"]))
    return m.compile()



if __name__ == "__main__":
    unittest.main()


class MensajeLlano(unittest.TestCase):
    """El aviso de vencimientos simultáneos que lee el usuario: sus elementos por la etiqueta, sin claves internas ni Ajustes."""

    @staticmethod
    def con_ids_reales(m):
        """El mismo modelo con los ID de expresión de un proyecto real (`e-<32 cifras hexadecimales>`)."""
        import json
        texto = json.dumps(m.doc)
        for i in (1, 2):
            texto = texto.replace(f'"e{i}"', f'"e-{i:032x}"')
        doc = json.loads(texto)
        return doc, validate_model(doc).model

    def test_SVSIM11_el_nucleo_da_las_claves_del_grupo_como_evidencia(self):
        """REQ-TMP-02: el diagnóstico de dependencia del orden lleva las claves del grupo en `evidence['claves']`; el texto no cambia."""
        s = session(f_misma_etapa_mismo_retardo())
        s.run()
        d = s.diagnostics[-1]
        self.assertEqual(d.evidence["claves"], "e1, e2")
        self.assertEqual(d.message, "vencimientos simultáneos cuyo resultado depende del orden (e2, e1 frente a e1, e2; grupo e1, e2) "
                                    "[temporal.coincidencias]")

    def test_SVSIM12_el_usuario_ve_las_transiciones_por_su_etiqueta_y_sin_ajustes(self):
        """REQ-TMP-02, REQ-UX-01: dos transiciones de la misma etapa con `2s/X0`: «Las transiciones t1 y t2 (tras X0)…»; sin `e-…` ni
        «Ajustes de simulación», con la corrección de usar tiempos distintos."""
        from escritorio.mensajes import vencimientos_en_palabras
        from grafcet.view import display_names
        m = M().step("E0", True).step("E1").step("E2")
        m.trans("t1", ["E0"], ["E1"], "delay(2 s, active(E0), 0 s)").trans("t2", ["E0"], ["E2"], "delay(2 s, active(E0), 0 s)")
        doc, cm = self.con_ids_reales(m)
        s = session(cm)
        s.run()
        self.assertEqual(s.status, "error")
        d = s.diagnostics[-1].to_dict()
        self.assertRegex(d["message"], r"e-[0-9a-f]{32}")
        mensaje, correccion = vencimientos_en_palabras(d, doc, display_names(doc))
        self.assertEqual(mensaje, "Las transiciones t1 y t2 (tras X0) tienen temporizadores que vencen en el mismo instante "
                                  "y el resultado depende de cuál vaya primero.")
        self.assertEqual(correccion, "Usa tiempos distintos o evita que compitan por la misma etapa.")
        for texto in (mensaje, correccion):
            self.assertNotRegex(texto, r"e-[0-9a-f]{8}")
            self.assertNotIn("Ajustes de simulación", texto)

    def test_SVSIM13_otros_diagnosticos_no_se_tocan(self):
        """REQ-TMP-02: un diagnóstico que no es de vencimientos simultáneos sigue su camino (devuelve None)."""
        from escritorio.mensajes import vencimientos_en_palabras
        self.assertIsNone(vencimientos_en_palabras({"code": "D-SEM-PENDIENTE", "message": "otra cosa"}, {}, {}))
        self.assertIsNone(vencimientos_en_palabras({"code": "D-LIM-EVOL", "message": "vencimientos simultáneos cuyo resultado depende del orden"},
                                                   {}, {}))
