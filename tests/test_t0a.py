"""Pruebas de la tanda T0a: voz «tú», tabla de microcopia (#10) y renombres de texto (#1, #6.4)."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tests") not in sys.path:
    sys.path.insert(1, str(RAIZ / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from escritorio.mensajes import CORRECCION_VENCIMIENTOS, amable, correccion_amable, mezcla_acciones, motivo_parada

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication, QLabel
    from escritorio.entradas_salidas import PanelES
    from escritorio.ventana import AcercaDe

PATRON_USTED = re.compile(
    r"(?<!\bse\s)(?<!\bel\s)(?<!\bun\s)(?<!\bde\s)(?<!\bdel\s)(?<!\bsin\s)(?<!\bcada\s)\b("
    r"pulse|púlsel\w*|elija|elíjal\w*|seleccione|selecciónel\w*|revise|revísel\w*|"
    r"arrastre|arrástrel\w*|compruebe|compruébel\w*|ponga|póngal\w*|pídalas|pídala|pídalo|"
    r"suelte|suéltel\w*|ábralo|reinícielo|reinicie|escríbale|escríbalo|escriba|"
    r"cambie|bórrelo|bórrelos|corríjalo|corrija|apártelo|créelas|créela|"
    r"quítela|quítelas|quítelo|quítele|vacíela|vacíe|sincronice|únala|haga\s+clic|"
    r"tiene\s+instalada|ya\s+tiene\s+la\s+última"
    r")\b",
    re.I,
)


class TextosT0a(unittest.TestCase):
    def test_ST0A01_sin_formas_usted_en_cadenas_de_interfaz(self):
        """Ninguna cadena literal de interfaz en escritorio/ conserva formas de «usted»."""
        hallados: list[str] = []
        for ruta in sorted((RAIZ / "escritorio").rglob("*.py")):
            fuente = ruta.read_text(encoding="utf-8")
            arbol = ast.parse(fuente, filename=str(ruta))
            docs = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if (
                        nodo.body
                        and isinstance(nodo.body[0], ast.Expr)
                        and isinstance(nodo.body[0].value, ast.Constant)
                        and isinstance(nodo.body[0].value.value, str)
                    ):
                        docs.add(id(nodo.body[0].value))
            # En mensajes.py, TUTEOS_NUCLEO contiene en el lado izquierdo los textos originales de grafcet/
            ignorar = set()
            if ruta.name == "mensajes.py":
                for nodo in ast.walk(arbol):
                    if isinstance(nodo, ast.AnnAssign) and getattr(nodo.target, "id", "") == "TUTEOS_NUCLEO":
                        for tupla in getattr(nodo.value, "elts", ()):
                            if isinstance(tupla, ast.Tuple) and tupla.elts:
                                ignorar.add(id(tupla.elts[0]))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                    if id(nodo) in docs or id(nodo) in ignorar:
                        continue
                    texto = nodo.value
                    if texto == "arrastre":  # clave interna de caché en bloques.py
                        continue
                    m = PATRON_USTED.search(texto)
                    if m:
                        rel = ruta.relative_to(RAIZ).as_posix()
                        hallados.append(f"{rel}:{nodo.lineno} [{m.group(0)}]: {texto!r}")
        self.assertEqual(hallados, [])

    def test_ST0A02_ayuda_de_usuario_en_tu_y_modbus_16_4(self):
        """LEEME.txt, README.md y PRIMERA_CONEXION_MODBUS.md usan «tú» y 16 digitales / 4 numéricos."""
        for rel in ("escritorio/LEEME.txt", "README.md", "docs/PRIMERA_CONEXION_MODBUS.md"):
            texto = (RAIZ / rel).read_text(encoding="utf-8")
            m = PATRON_USTED.search(texto)
            self.assertIsNone(m, f"{rel} conserva «{m.group(0) if m else ''}»")
        guia = (RAIZ / "docs/PRIMERA_CONEXION_MODBUS.md").read_text(encoding="utf-8")
        self.assertIn("16 canales digitales y 4 numéricos", guia)
        self.assertNotIn("32 canales digitales", guia)
        self.assertIn("**Detener**", guia)
        self.assertNotIn("**Stop**", guia)

    def test_ST0A03_mensajes_traduce_textos_del_nucleo_a_tu(self):
        """Los diagnósticos de grafcet/ se traducen a «tú» en mensajes.py sin tocar grafcet/."""
        self.assertIn("Revisa esas receptividades.", motivo_parada(
            "D-LIM-EVOL", "presupuesto agotado",
            [{"evolutionIndex": 1, "cleared": ["t1"], "situation": ["s1"]},
             {"evolutionIndex": 2, "cleared": ["t2"], "situation": ["s2"]}],
            {"t1": "t1", "t2": "t2", "s1": "1", "s2": "2"},
        )[1][0])
        self.assertEqual(CORRECCION_VENCIMIENTOS, "Usa tiempos distintos o evita que compitan por la misma etapa.")
        self.assertEqual(
            correccion_amable("D-BARRA-SUELTA", "Una la barra a lo que va por encima y por debajo, o bórrela"),
            "Une la barra a lo que va por encima y por debajo, o bórrala",
        )
        self.assertIn("Únela o bórrala.", amable("Simultaneidad 1 no tiene nada conectado. Únala o bórrela."))
        self.assertIn("usa una barra de simultaneidad.", amable("X llega a t1, que ya tiene otra etapa anterior: use una barra de simultaneidad."))
        self.assertIn("quítalas antes de convertirla en macroetapa", amable("La etapa «1» tiene acciones: quítelas antes de convertirla en macroetapa"))
        self.assertIn("vacía la expansión antes", amable("la expansión de «M1» tiene contenido (etapas): vacíe la expansión antes"))
        modelo = {
            "steps": [{"id": "s1", "label": "1"}, {"id": "s2", "label": "2"}],
            "actions": [
                {"stepRef": "s1", "mode": "continuous", "targetRef": "v1"},
                {"stepRef": "s2", "mode": "stored", "targetRef": "v1"},
            ],
        }
        self.assertTrue(mezcla_acciones(modelo, {"v1": "Luz"}, "v1").endswith("usa solo un tipo."))


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazT0a(BaseQt):
    def test_ST0A04_tabla_microcopia_10(self):
        """Comprueba las frases exactas de la tabla de microcopia (#10) en acciones, macroetapa, E/S y Acerca de."""
        w, e = self.vacio()
        e.nueva_variable("luz", "output", {"kind": "bool"})
        s0 = e.poner_etapa(QPointF(140, 80), inicial=True)
        did = e.ed.add_draft_action((200, 80), {"tipo": "activacion", "etapa": s0})
        e.cambia()
        e.pedir_accion(s0, did)
        w._abrir_opciones()
        QApplication.processEvents()
        self.assertEqual(
            w.props.accion.l_nota_bool.text(),
            "Elige arriba una variable booleana o numérica para configurar la asignación.",
        )
        w.props.accion._elegida = "luz"
        w.props.accion._ajustar()
        self.assertEqual(
            w.props.accion.l_nota_bool.text(),
            "Elige el valor booleano (1 o 0) que tomará la variable al ejecutarse la acción.",
        )
        self.assertTrue(
            w.props.AYUDA_JERARQUIA["macro"].endswith("suelta etapas y transiciones dentro de su zona para rellenarla.")
        )

        acerca = AcercaDe(w)
        self.addCleanup(acerca.close)
        textos_acerca = " ".join(lb.text() for lb in acerca.findChildren(QLabel))
        self.assertIn("el autor ofrece licencias comerciales: pídelas a través de GitHub.", textos_acerca)

        panel = PanelES()
        self.addCleanup(panel.close)
        panel.cargar(e.ed.model)
        panel.directa.seleccionar("directo")
        panel.directa.dibujar()
        self.assertEqual(
            panel.ayuda_vacio.text(),
            "Arrastra una variable a su señal o haz clic en la variable y luego en la señal. "
            "Pon el controlador en «Ninguno» para la conexión directa.",
        )
        panel.directa.seleccionar("modbus")
        self.assertEqual(
            panel.ayuda_vacio.text(),
            "Arrastra una variable a su canal o haz clic en la variable y luego en el canal.",
        )
        self.assertEqual(panel.b_restaurar_canales.text(), "Restablecer canales por defecto")
        self.assertEqual(panel.b_restaurar_canales.toolTip(), "16 digitales y 4 numéricos")

    def test_ST0A05_renombres_detener_consigna_y_memorizada(self):
        """En simulación: botón «Detener», cabecera «Consigna» y modo «memorizada» (abreviado «mem.» en estrecho)."""
        w, e = self.vacio()
        e.nueva_variable("m1", "internal", {"kind": "int"})
        s0 = e.poner_etapa(QPointF(140, 80), inicial=True)
        t1 = e.poner_transicion(QPointF(140, 160))
        s1 = e.poner_etapa(QPointF(140, 240))
        e.conectar(s0, t1)
        e.conectar(t1, s1)
        e.poner_condicion(t1, "2s/X0")
        e.poner_accion(s0, {"variable": "m1", "tipo": "activacion", "valor": "1"})
        e.cambia()
        w.resize(1366, 768)
        w.show()
        QApplication.processEvents()
        self.assertEqual(
            [w.t_temp.horizontalHeaderItem(c).text() for c in range(4)],
            ["Dónde", "Estado", "Lleva", "Consigna"],
        )
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        QApplication.processEvents()
        self.assertEqual(w.a_ejecutar.text(), "Detener")
        self.assertIn("Detener:", w.a_ejecutar.toolTip())

        delegado = w.t_vars.itemDelegateForColumn(1)
        indice = w.t_vars.model().index(0, 1)
        delegado.corto = False
        self.assertEqual(delegado.displayText(indice.data(), w.t_vars.locale()), "memorizada")
        delegado.corto = True
        self.assertEqual(delegado.displayText(indice.data(), w.t_vars.locale()), "mem.")
        w.a_ejecutar.setChecked(False)


if __name__ == "__main__":
    unittest.main()
