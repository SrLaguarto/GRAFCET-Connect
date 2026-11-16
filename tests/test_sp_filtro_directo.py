"""SP1: exclusiones por ID y selección recordada; HTTP falso y carpetas temporales."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from conexion.catalogo_directo import interna
from conexion.configuracion import Configuracion
from conexion.filtro_directo import actualizar, anadir, excluida, quitar
from conexion.http_directo import ClienteDirecto
from conexion.uniones import Union
from grafcet.editor import new_grafcet_document
from servidor_directo_falso import ServidorDirecto, senal


def identidad(n):
    return str(UUID(int=n))


class FiltroDirecto(unittest.TestCase):
    def setUp(self):
        self.config = Configuracion(host="localhost", puerto=7410, modo="directo")
        self.catalogo = [senal(identidad(1), "Planta I/O (Run)", papel="Output", direccion=496),
                         senal(identidad(2), "Motor I/O (izq)", direccion=5),
                         senal(identidad(3), "Sensor normal", direccion=240)]

    def test_SP101_regla_doble_y_no_patron_antiguo(self):
        self.assertTrue(interna(self.catalogo[0]))
        self.assertFalse(interna(self.catalogo[1]))
        self.assertFalse(interna(self.catalogo[2]))
        self.assertFalse(interna(senal(identidad(4), "SISTEMA (Running)", direccion=496)))

    def test_SP102_lista_inicial_y_excepcion_unida(self):
        actualizar(self.config, self.catalogo)
        self.assertEqual(len(self.config.filtro_senales), 1)
        self.assertTrue(excluida(self.config, self.catalogo[0]))
        self.config.uniones = [Union("v", identidad(1), "Run", "Bit", "output")]
        self.assertFalse(excluida(self.config, self.catalogo[0]))

    def test_SP103_sin_recordar_siguiente_lectura_restaura(self):
        self.assertFalse(self.config.recordar_filtro)
        actualizar(self.config, self.catalogo)
        self.config.filtro_senales[0]["excluir"] = False
        anadir(self.config, identidad(2), self.catalogo)
        self.assertFalse(excluida(self.config, self.catalogo[0]))
        self.assertTrue(excluida(self.config, self.catalogo[1]))
        actualizar(self.config, self.catalogo)
        self.assertTrue(excluida(self.config, self.catalogo[0]))
        self.assertFalse(excluida(self.config, self.catalogo[1]))

    def test_SP104_recordar_desmarcada_quitada_anadida_y_otra_escena(self):
        actualizar(self.config, self.catalogo)
        self.config.recordar_filtro = True
        self.config.filtro_senales[0]["excluir"] = False
        anadir(self.config, identidad(2), self.catalogo)
        actualizar(self.config, [])
        self.assertEqual(len(self.config.filtro_senales), 2)
        actualizar(self.config, self.catalogo)
        self.assertFalse(excluida(self.config, self.catalogo[0]))
        self.assertTrue(excluida(self.config, self.catalogo[1]))
        quitar(self.config, identidad(1))
        actualizar(self.config, self.catalogo)
        self.assertFalse(excluida(self.config, self.catalogo[0]))
        self.assertTrue(self.config.filtro_senales[0]["quitada"])

    def test_SP105_validacion_y_duplicados(self):
        for texto in ("", "sin-id", "123", "https://servidor", "0" * 32):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                anadir(self.config, texto, self.catalogo)
        anadir(self.config, identidad(2), self.catalogo)
        with self.assertRaises(ValueError):
            anadir(self.config, identidad(2).upper(), self.catalogo)
        self.assertEqual(self.config.filtro_senales[0]["nombre"], "Motor I/O (izq)")

    def test_SP106_persistencia_recordada_y_proyecto_sin_lista(self):
        doc = new_grafcet_document("p")
        actualizar(self.config, self.catalogo)
        with TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "conexion.json"
            self.config.guardar(ruta, doc)
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertNotIn("filtro_senales", datos)
            anterior = Configuracion.cargar(ruta, doc)
            self.assertFalse(anterior.recordar_filtro)
            actualizar(anterior, self.catalogo)
            self.assertTrue(excluida(anterior, self.catalogo[0]))
            self.config.recordar_filtro = True
            self.config.filtro_senales[0]["excluir"] = False
            self.config.guardar(ruta, doc)
            nueva = Configuracion.cargar(ruta, doc)
            self.assertTrue(nueva.recordar_filtro)
            self.assertFalse(excluida(nueva, self.catalogo[0]))

    def test_SP107_catalogo_http_falso_conserva_identidad_interna_neutral(self):
        servidor = ServidorDirecto(self.catalogo)
        self.addCleanup(servidor.cerrar)
        cliente = ClienteDirecto("127.0.0.1", servidor.puerto)
        self.addCleanup(cliente.cerrar)
        leidas = cliente.catalogo()
        self.assertTrue(interna(leidas[0]))
        self.assertEqual(leidas[0]["name"], "Simulador (Run)")
        self.assertFalse(interna(leidas[1]))
        copia = deepcopy(leidas)
        actualizar(self.config, leidas)
        self.assertEqual(leidas, copia)

    def test_SP123_unidas_excluidas_se_leen_y_escriben_con_http_falso(self):
        from conexion.intercambio_directo import TransporteDirecto
        catalogo = [senal(identidad(1), "Simulador I/O (Running)", direccion=496, valor=True),
                    senal(identidad(2), "Simulador I/O (Run)", papel="Output", direccion=496)]
        servidor = ServidorDirecto(catalogo)
        self.addCleanup(servidor.cerrar)
        self.config.host = "127.0.0.1"
        self.config.puerto = servidor.puerto
        actualizar(self.config, catalogo)
        self.assertTrue(all(f["excluir"] for f in self.config.filtro_senales))
        self.config.uniones = [Union("sensor", identidad(1), "Running", "Bit", "input"),
                               Union("motor", identidad(2), "Run", "Bit", "output")]
        transporte = TransporteDirecto(self.config)
        self.addCleanup(transporte.cerrar)
        transporte.senales = {s["id"]: s for s in transporte.catalogo()}
        self.assertEqual(transporte.leer(self.config.uniones), {"sensor": True})
        self.assertEqual(transporte.escribir(self.config.uniones, {"motor": True}), {"motor": True})
        self.assertTrue(servidor.senales[1]["value"])
        self.assertFalse(any(excluida(self.config, s) for s in catalogo))

    def test_SP124_metadatos_de_filtro_incorrectos_se_rechazan(self):
        from conexion.filtro_directo import validar
        for nombre, valor in (("nombre", None), ("tipo", 9)):
            with self.subTest(nombre=nombre):
                fila = dict(id=identidad(1), excluir=True, nombre="Run", tipo="Bit")
                fila[nombre] = valor
                self.config.filtro_senales = [fila]
                with self.assertRaises(ValueError):
                    validar(self.config)


if __name__ == "__main__":
    unittest.main()
