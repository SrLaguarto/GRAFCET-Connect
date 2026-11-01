import copy
from pathlib import Path
import tempfile
import unittest

from conexion.configuracion import ARCHIVO, Configuracion, Senal
from grafcet.examples import EJEMPLOS
from grafcet.persistence import add_document, new_project, save_project


class ConfigTests(unittest.TestCase):
    def test_SFIO26_escala_factoryio_100_por_defecto_y_personalizable(self):
        """REQ-DAT-02: entradas/salidas numéricas usan 100 por defecto y respetan las escalas guardadas."""
        import json
        from grafcet.builder import M
        doc=M().var("sensor",kind="decimal",scale=2).var("consigna","output","int").step("0",True).doc
        c=Configuracion(senales=[Senal("sensor","input-register",0,"INT16"),
                                 Senal("consigna","holding",0,"UINT16")])
        self.assertEqual([s.escala for s in c.senales],["100","100"])
        with tempfile.TemporaryDirectory() as tmp:
            ruta=Path(tmp)/"conexion.json"
            c.guardar(ruta,doc)
            datos=json.loads(ruta.read_text(encoding="utf-8"))
            for s in datos["senales"]:
                s["escala"]="1"
            ruta.write_text(json.dumps(datos),encoding="utf-8")
            cargada=Configuracion.cargar(ruta,doc)
            self.assertEqual([s.escala for s in cargada.senales],["1","1"])

    def test_SFIO23_limites_de_canales_configurados(self):
        """REQ-DAT-02: rangos explícitos, asignaciones fuera y compatibilidad sin rangos."""
        for rango in ({"offset":0,"cantidad":257}, {"offset":65535,"cantidad":2},
                      {"offset":-1,"cantidad":2}, {"offset":0,"cantidad":True}):
            with self.subTest(rango=rango), self.assertRaises(ValueError):
                Configuracion(canales={"discrete":rango}).validar(self.doc)
        c=Configuracion(senales=[Senal(self.var["id"],"discrete",5)])
        c.validar(self.doc)
        c.canales={"discrete":{"offset":6,"cantidad":2}}
        with self.assertRaises(ValueError):
            c.validar(self.doc)
        c.canales={"discrete":{"offset":5,"cantidad":1}}
        c.validar(self.doc)

    def setUp(self):
        self.doc = EJEMPLOS[next(iter(EJEMPLOS))][2]()[0].doc
        self.var = next(v for v in self.doc["variables"] if v["role"] == "input" and v["type"]["kind"] == "bool")
        self.config = Configuracion(senales=[Senal(self.var["id"], "discrete", 0)])

    def test_SFIO04_persistencia_separada(self):
        """REQ-DAT-02: configuración externa no cambia el documento ni se borra al guardar."""
        original = copy.deepcopy(self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / ARCHIVO
            self.config.guardar(ruta, self.doc)
            p = new_project("p", "Prueba")
            add_document(p, self.doc)
            save_project(Path(tmp), p)
            c = Configuracion.cargar(ruta, self.doc)
            self.assertEqual(c.senales, self.config.senales)
            self.assertEqual(c.modelo, self.doc["id"])
        self.assertEqual(self.doc, original)

    def test_SFIO05_mapa_invalido(self):
        """REQ-ROB-01: no admite asociaciones incompatibles o repetidas."""
        for s in (Senal("inexistente", "discrete", 0), Senal(self.var["id"], "discrete", -1),
                  Senal(self.var["id"], "holding", 0), Senal(self.var["id"], "coil", 0, escala="0")):
            with self.subTest(s=s), self.assertRaises(ValueError):
                Configuracion(senales=[s]).validar(self.doc)
        self.config.senales *= 2
        with self.assertRaises(ValueError):
            self.config.validar(self.doc)

    def test_SFIO56_cargar_descarta_solo_las_asignaciones_que_ya_no_casan_y_rechaza_lo_corrupto(self):
        """REQ-DAT-02, REQ-ROB-01: un mapa guardado con una variable que ya no existe (o de tipo o papel que ya no casan con el
        área) se carga sin esas asignaciones, con un aviso por cada una, y conserva el resto (servidor, canales y las demás
        asignaciones); un JSON corrupto o de formato inválido se sigue rechazando entero."""
        import json
        from grafcet.builder import M
        doc = M().var("a").var("b").var("c", "output").var("d", "output", "decimal", scale=2).step("0", True).doc
        canales = {"discrete": {"offset": 0, "cantidad": 4}, "coil": {"offset": 0, "cantidad": 4},
                   "holding": {"offset": 0, "cantidad": 2}}
        original = Configuracion(host="10.0.0.5", puerto=1502, unidad=4, periodo_ms=40, timeout_ms=700, canales=canales,
                                 senales=[Senal("a", "discrete", 0), Senal("b", "discrete", 1), Senal("c", "coil", 0),
                                          Senal("d", "holding", 0, "INT16")])
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "conexion.json"
            original.guardar(ruta, doc)
            # el modelo cambia: «b» se borra, «a» pasa a salida (ya no puede ser un Input) y «d» a booleana (ya no es un registro)
            nuevo = copy.deepcopy(doc)
            nuevo["variables"] = [v for v in nuevo["variables"] if v["id"] != "b"]
            for v in nuevo["variables"]:
                if v["id"] == "a":
                    v["role"] = "output"
                if v["id"] == "d":
                    v["type"] = {"kind": "bool"}
            avisos = []
            c = Configuracion.cargar(ruta, nuevo, avisos)
            self.assertEqual([s.variable for s in c.senales], ["c"], "solo se descartan las que ya no casan")
            self.assertEqual(avisos, ["«a» ya no encaja en Entrada 0", "la variable de Entrada 1 ya no existe", "«d» ya no encaja en Salida numérica 0"])
            self.assertEqual((c.host, c.puerto, c.unidad, c.periodo_ms, c.timeout_ms, c.canales, c.modelo),
                             ("10.0.0.5", 1502, 4, 40, 700, canales, doc["id"]), "lo demás del mapa se conserva")
            self.assertEqual(Configuracion.cargar(ruta, nuevo).senales, c.senales, "`avisos` es opcional")
            self.assertEqual(Configuracion.cargar(ruta, doc).senales, original.senales, "con el modelo de siempre, nada se quita")
            # lo corrupto o de formato inválido se rechaza entero, aunque haya también asignaciones obsoletas
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            casos = {
                "versión": lambda d: d.update(version=2),
                "sin señales": lambda d: d.pop("senales"),
                "señales no es una lista": lambda d: d.update(senales=5),
                "otro modelo": lambda d: d.update(modelo="otro"),
                "mismo canal dos veces": lambda d: d["senales"].append(dict(d["senales"][2], variable="a")),
                "área desconocida": lambda d: d["senales"][2].update(area="banana"),
                "formato desconocido": lambda d: d["senales"][2].update(formato="FLOAT"),
                "formato que no casa con el área": lambda d: d["senales"][2].update(formato="INT16"),
                "fuera de los canales": lambda d: d["senales"][2].update(direccion=9),
                "variable repetida": lambda d: d["senales"].append(dict(d["senales"][2], direccion=1)),
            }
            for nombre, cambiar in casos.items():
                dañado = copy.deepcopy(datos)
                cambiar(dañado)
                ruta.write_text(json.dumps(dañado), encoding="utf-8")
                with self.subTest(nombre), self.assertRaises(ValueError):
                    Configuracion.cargar(ruta, nuevo)
            ruta.write_text("{ esto no es json", encoding="utf-8")
            with self.assertRaises(ValueError):
                Configuracion.cargar(ruta, nuevo)
