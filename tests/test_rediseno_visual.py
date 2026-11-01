"""Pruebas de los accesos visuales nuevos a operaciones existentes."""
import unittest
from test_editor_cadenas import BaseQt, QT
if QT:
    from PySide6.QtCore import QPointF, Qt


@unittest.skipUnless(QT, "PySide6 no está instalado")
class RedisenoVisual(BaseQt):
    def test_SVIS01_inicial_solape_y_deshacer(self):
        """REQ-EDT-02: etapa inicial desde la paleta, sin permitir solapes y con deshacer."""
        w, e = self.vacio()
        e.colocar("etapa_inicial", QPointF(300, 100))
        self.assertTrue(e.M["steps"][0]["initial"])
        e.colocar("etapa_inicial", QPointF(300, 100))
        self.assertEqual(len(e.M["steps"]), 1)
        e.deshacer()
        self.assertEqual(e.M["steps"], [])

    def test_SVIS02_simultaneidad_unica_crea_barras_Y(self):
        """REQ-EDT-02, REQ-MOD-03: la ficha única crea barras Y sin semántica nueva."""
        w, e = self.vacio()
        for ficha, y in (("simultaneidad", 100), ("simultaneidad", 300)):
            revision = e.ed.revision
            e.colocar(ficha, QPointF(300, y))
            self.assertEqual(e.M["bars"][-1]["kind"], "Y")
            self.assertEqual(e.ed.revision, revision)
        self.assertEqual(len(e.M["bars"]), 2)
        e.deshacer()
        self.assertEqual(len(e.M["bars"]), 1)

    def test_SVIS03_cinco_acciones_desde_paleta(self):
        """REQ-ACT-01, REQ-EDT-02: cada ficha crea el borrador de acción de su tipo."""
        w, e = self.vacio()
        tipos = ["continua", "condicionada", "activacion", "desactivacion", "evento"]
        for i, tipo in enumerate(tipos):
            e.colocar("accion:" + tipo, QPointF(300, 100 + i * 140))
        self.assertEqual([a["tipo"] for a in e.ed.draft_actions()], tipos)
        self.assertEqual(e.ed.model["actions"], [])

    def test_SVIS04_encabezados_y_dependencias(self):
        """REQ-EDT-02, REQ-SIM-03: encabezados sin arrastre; dependencias accesible al editar y simular."""
        w, e = self.vacio()
        pa = w.paleta
        for i in range(pa.count()):
            it = pa.item(i)
            if not it.data(Qt.ItemDataRole.UserRole):
                self.assertFalse(it.flags() & (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled))
                self.assertFalse(pa.mimeData([it]).hasText())
        w.show()
        self.app.processEvents()
        b = w.diagrama.b_dependencias
        self.assertIs(b.parent(), w.tb_vista)
        self.assertTrue(b.isVisible())
        b.click()
        self.assertTrue(w.diagrama.dependencias)
        e.ed.dirty = False
        w.cargar_ejemplo("temporizada")
        self.assertTrue(w.cambiar_modo("simular"))
        self.app.processEvents()
        self.assertTrue(b.isVisible() and b.isChecked())

    def test_SVIS05_propiedades_compactas_y_divisor_manual_respetado(self):
        """REQ-EDT-02, REQ-EDT-09: sin selección se libera el lienzo; el reparto manual se conserva."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        for _ in range(5):
            self.app.processEvents()
        vacio = w.vsplit.sizes()[1]
        self.assertLessEqual(vacio, 100)
        e.colocar("transicion", QPointF(300, 180))
        for _ in range(5):
            self.app.processEvents()
        self.assertGreater(w.vsplit.sizes()[1], vacio)
        self.assertTrue(w.props.cuerpo.isVisible())
        w.vsplit.moveSplitter(w.vsplit.sizes()[0] - 35, 1)
        self.app.processEvents()
        manual = w.vsplit.sizes()
        e.seleccionar([])
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(w.vsplit.sizes(), manual)
        self.assertFalse(w.props.cuerpo.isVisible())

    def test_SVIS11_cajas_y_conectores_de_acciones_y_forzado_iguales(self):
        """REQ-EDT-02: las seis fichas comparten caja y trazo sin conector sin perder sus marcas distintivas."""
        from escritorio.propiedades import figura
        claves=["accion:"+t for t in ("continua","condicionada","activacion","desactivacion","evento")]+["forzado"]
        imagenes=[figura(k)[0].toImage() for k in claves]
        self.assertEqual(len({bytes(im.constBits()) for im in imagenes}),6)
        for im in imagenes:
            for x in range(9,88):
                self.assertGreater(im.pixelColor(x,22).alpha(),0)
                self.assertGreater(im.pixelColor(x,66).alpha(),0)
            for y in range(23,66):
                self.assertGreater(im.pixelColor(8,y).alpha(),0)
                self.assertGreater(im.pixelColor(88,y).alpha(),0)
        self.assertTrue(all(im.pixelColor(x,y).alpha()==0 for im in imagenes for x in range(6) for y in range(im.height())))

    def test_SVIS12_solo_transicion_conserva_conectores_verticales(self):
        """REQ-EDT-02: etapas sin conectores y transición con conectores más largos y centrados."""
        from escritorio.propiedades import figura
        for clave in ("etapa","etapa_inicial","macroetapa","encapsulante"):
            im=figura(clave)[0].toImage()
            self.assertTrue(all(im.pixelColor(48,y).alpha()==0 for y in [*range(21),*range(68,88)]))
        im=figura("transicion")[0].toImage()
        self.assertTrue(all(im.pixelColor(48,y).alpha()>0 for y in range(18,71)))
        self.assertEqual(im.pixelColor(48,15).alpha(),0)
        self.assertEqual(im.pixelColor(48,73).alpha(),0)

    def test_SVIS13_rotulo_del_parcial_corta_el_borde_inferior(self):
        """REQ-EDT-02, REQ-JER-02: la G se monta sobre la línea inferior del marco y deja ver el fondo a sus lados."""
        from escritorio.propiedades import figura
        im=figura("parcial")[0].toImage()
        self.assertGreater(im.pixelColor(130,130).alpha(),0)
        self.assertEqual(im.pixelColor(137,130).alpha(),0)
        self.assertTrue(any(im.pixelColor(x,y).alpha()>0 for x in range(140,158) for y in range(131,139)))

    def test_SVIS14_ficha_unica_conserva_apertura_y_cierre_por_enlace(self):
        """REQ-EDT-02, REQ-MOD-03: una sola ficha con ayuda conserva los gestos de apertura y cierre de simultaneidad."""
        w,e=self.vacio(); pa=w.paleta
        items=[pa.item(i) for i in range(pa.count()) if pa.item(i).data(Qt.ItemDataRole.UserRole)=="simultaneidad"]
        self.assertEqual(len(items),1);self.assertEqual(items[0].text(),"Simultaneidad")
        self.assertIn("varias etapas",items[0].toolTip());self.assertIn("extremos",items[0].toolTip())
        for tipo,x,y in (("transicion",400,100),("simultaneidad",400,180),("etapa",360,280),
                         ("etapa",460,280),("simultaneidad",400,380),("transicion",400,460)):
            e.colocar(tipo,QPointF(x,y))
        nodos=sorted(e.M["transitions"],key=lambda t:t["y"]); barras=sorted(e.M["bars"],key=lambda b:float(b["y"]))
        etapas=[s["id"] for s in e.M["steps"]]; t0,t1=[t["id"] for t in nodos];b0,b1=[b["id"] for b in barras]
        self.unir(e,t0,"abajo",b0,"arriba")
        for sid in etapas:
            self.unir(e,b0,"abajo",sid,"arriba");self.unir(e,sid,"abajo",b1,"arriba")
        self.unir(e,b1,"abajo",t1,"arriba")
        ts={t["id"]:t for t in e.ed.model["transitions"]}
        self.assertEqual(set(ts[t0]["postRefs"]),set(etapas));self.assertEqual(set(ts[t1]["preRefs"]),set(etapas))
        self.assertTrue(all(b["kind"]=="Y" for b in e.ed.bars()))

    def test_SVIS15_carpetas_por_uso_en_panel_y_ventana_ampliada(self):
        """REQ-EDT-02, REQ-EDT-07: el orden por uso es idéntico y cada carpeta sigue cargando sus bloques en ambos editores."""
        w,e=self.vacio();p=w.props.prog
        claves=["entrada","etapa","interna","operador","tiempo","comparacion","salida","constante"]
        titulos=["Entradas","Etapas (X)","Memorias","Operadores","Temporizadores","Comparaciones","Salidas","Constantes"]
        v=p.ampliar_ventana()
        try:
            for prog in (p,v.programador):
                self.assertEqual(list(prog.categorias),claves)
                self.assertEqual([b.text() for b in prog.categorias.values()],titulos)
                for clave in claves:
                    prog.categorias[clave].click()
                    self.assertEqual(prog.paleta.clave,clave)
                    self.assertTrue(prog.categorias[clave].isChecked())
                    self.assertEqual(sum(b.isChecked() for b in prog.categorias.values()),1)
        finally:
            v.close()
