"""Regresiones de retornos, simultaneidad, valores e incidencias."""
import copy
import json
import unittest
from unittest import mock
from grafcet.builder import M
from grafcet.routing import enlaces
from test_dibujo_vista import vista, ejemplo, dibujo, texto, QT, QJS, ROOT, MOCK_DOM, dibujar_con_js
from test_editor_cadenas import nuevo, entradas, BaseQt
if QT:
    from PySide6.QtCore import QEvent, Qt, QPointF
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from escritorio import diagrama as dg
    from escritorio.edicion import Edicion
if QJS:
    from PySide6.QtQml import QJSEngine


@unittest.skipUnless(QT, "requiere PySide6")
class Retornos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def paridad(self, v, st):
        roles = dg._colores_elementos(v.model, st)
        if QJS:
            eng = QJSEngine()
            js = (ROOT/"tools/dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}", "Object.assign({x, y}, attrs)")
            self.assertFalse(eng.evaluate(MOCK_DOM + js).isError())
            eng.evaluate("var M="+json.dumps(v.model)+", S="+json.dumps(st)+";")
            actual = eng.evaluate("JSON.stringify(M.links.map(e=>colorEnlace(M,coloresElementos(M,S),e)||'text'))")
            self.assertFalse(actual.isError(), actual.toString())
            self.assertEqual(json.loads(actual.toString()), [dg._color_enlace(v.model, roles, e) for e in v.model["links"]])
        return roles

    def test_SSAL01_destino_activo_y_receptividad_no_colorean_retornos_no_validados(self):
        """REQ-SIM-03, REQ-MOD-03: no se propaga actividad desde la etapa destino; paridad real Qt/JS en tres ejemplos."""
        for clave, cambios, origen, tid in (("repeticion", {"inicio":True,"repetir":True}, "2", "retorno"),
                ("salto", {"avanzar1":True}, "2", "salto"),
                ("alternativas", {"marcha":True,"repetir":True}, "E1", "t6")):
            v = ejemplo(clave)
            v.act("fijar", {"cambios":cambios})
            st = v.state();self.assertEqual(st["situation"], [origen])
            roles = self.paridad(v,st)
            self.assertNotIn(tid,roles)
            for e in v.model["links"]:
                if e["tid"] == tid:
                    self.assertEqual(dg._color_enlace(v.model,roles,e), "text")
            self.assertFalse(st["transitions"][tid]["validated"])
        # La receptividad sigue verdadera y legible, pero su transición no está validada.
        v = ejemplo("repeticion");v.act("fijar", {"cambios":{"inicio":True,"repetir":True}})
        self.assertTrue(v.state()["transitions"]["retorno"]["receptivity"])

    def test_SSAL02_alternativas_no_invierten_el_sentido_de_los_enlaces(self):
        """REQ-MOD-03, REQ-SIM-03: rápida y marcha no llevan de E2 a E1; repetir sí, y E0 no salta a E3."""
        v = ejemplo("alternativas");v.act("fijar", {"cambios":{"rapida":True}})
        v.act("fijar", {"cambios":{"rapida":False}})
        v.act("fijar", {"cambios":{"rapida":True,"marcha":True}})
        self.assertEqual(v.state()["situation"], ["E2"])
        v.act("fijar", {"cambios":{"repetir":True}})
        self.assertEqual(v.state()["situation"], ["E1"])
        v = ejemplo("alternativas");v.act("fijar", {"cambios":{"fin2":True,"repetir":True,"marcha":True}})
        self.assertEqual(v.state()["situation"], ["E1"])

    def test_SSAL03_valor_actual_sobre_destino_asignacion_centrado_y_solo_lectura(self):
        """REQ-SIM-03, REQ-ACT-02: valor observado sobre la variable destino, centrado y tabular en Qt/JS, ausente en edición."""
        m = M().var("p").var("contador","internal","int").step("A",True).stored("A","contador","event","contador + 1",event="rise(p)")
        v = vista(m,{"A":(100,150)});v.act("fijar", {"cambios":{"p":True}})
        antes = copy.deepcopy(v.s.z);st = v.state();self.assertEqual(v.s.z,antes)
        self.assertEqual(st["variableReadouts"]["contador"], "1")
        self.assertEqual(st["variableReadouts"]["p"], "1")
        sc, cajas = dibujo(v);valor = texto(sc,"1");asigna = texto(sc,"contador := contador + 1")
        centro = asigna.x()+dg._Pintor.ancho([{"t":"contador"}],15)/2
        self.assertAlmostEqual(valor.sceneBoundingRect().center().x(),centro,delta=.1)
        self.assertLessEqual(valor.y()+valor.boundingRect().height(),asigna.y()+2)
        self.assertEqual(valor.font().pixelSize(),10);self.assertTrue(valor.font().fixedPitch())
        sc,_ = dibujo(v,{})
        self.assertFalse(any(getattr(i,"toPlainText",lambda:None)()=="1" for i in sc.items()))
        if QJS:
            tree = dibujar_con_js(v.model,st)
            def rec(n):
                yield n
                for c in n.get("hijos",[]):yield from rec(c)
            valores = [n for n in rec(tree) if n.get("attrs",{}).get("class")=="variable-value"]
            self.assertEqual(len(valores),1)
            eng=QJSEngine();js=(ROOT/"tools/dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}","Object.assign({x, y}, attrs)")
            self.assertFalse(eng.evaluate(MOCK_DOM+js).isError())
            a=v.model["steps"][0]["actions"][0]
            r=eng.evaluate("var g=new MockEl('g');drawAction(g,248,150,%s,%s);JSON.stringify(g.children[0].children.filter(e=>e.attrs.class==='variable-value').map(e=>e.textContent))"%(json.dumps(a),json.dumps(st)))
            self.assertEqual(json.loads(r.toString()),["1"])
            self.assertEqual(valores[0]["attrs"]["text-anchor"],"middle")

    def test_SSAL04_retornos_desde_derecha_rodean_condicion_y_banderita(self):
        """REQ-EDT-02, REQ-MOD-03: el retorno pasa por encima de las marcas y conserva su unión final, también con ruta manual."""
        m = (M().var("p").var("y","output").var("n","internal","int").step("A",True).step("B")
             .trans("ida",["A"],["B"],"p").trans("vuelta",["B"],["A"],"NOT p")
             .cont("A","y","p").stored("A","n","event","n + 1",event="rise(p)"))
        v = vista(m,{"A":(100,100),"ida":(100,220),"B":(100,340),"vuelta":(420,400)})
        for manual in (False,True):
            modelo = copy.deepcopy(v.model)
            if manual:modelo["linkStyles"]={"vuelta|A|post":{"route":{"laneX":520,"entryY":62}}}
            e = next(e for e in enlaces(modelo) if e["id"]=="vuelta|A|post")
            self.assertEqual(e["pts"][-1],(200,78))
            self.assertEqual(e["pts"][-2][1],62)
            self.assertEqual(e["pts"][-3][0],230)
            self.assertLessEqual(e["pts"][-4][1],46)
            self.assertTrue(e["arrows"])
            if manual:self.assertEqual(e["pts"][2][0],620)
        # La web consume exactamente los recorridos compartidos, sin calcular otros.
        self.assertEqual(v.model["links"],enlaces(v.model))

    def test_SSAL05_convergencia_con_predecesores_debajo_sale_por_debajo_y_lleva_flecha(self):
        """REQ-MOD-03, REQ-EDT-02: los retornos hacia una sincronización no atraviesan etapas ni otras transiciones."""
        m = M().var("p").step("A",True).step("B").step("C").trans("t",["B","C"],["A"],"p")
        v = vista(m,{"A":(100,80),"t":(100,300),"B":(100,460),"C":(340,460)})
        for e in v.model["links"]:
            if e["rol"]!="pre":continue
            self.assertGreater(e["pts"][1][1],e["pts"][0][1])
            self.assertEqual(e["pts"][-1][1],300-dg.SIMUL-dg.BARRA_GROSOR)
            self.assertLess(e["pts"][-2][1],300-dg.SIMUL-dg.BARRA_GROSOR)
            self.assertTrue(e["arrows"])


class Barras(unittest.TestCase):
    def test_SSAL06_barra_y_no_representa_alternativas_bloqueo_y_deshacer(self):
        """REQ-MOD-03, REQ-EDT-05: Y con varias transiciones se diagnostica; Y agrupa las etapas de una sola transición, sin exigir pareja."""
        ed=nuevo();entradas(ed,"p")
        a=ed.add_step("g","1",True,at=(100,80));b=ed.add_step("g","2",at=(100,400))
        t,_=ed.add_transition("g","p",at=(100,240));u,_=ed.add_transition("g","p",at=(300,240))
        ed.connect(t,b);ed.connect(u,b)
        bar=ed.add_bar("Y",(80,180),300)
        ed.bar_link(bar,"arriba",a);ed.bar_link(bar,"abajo",t);ed.bar_link(bar,"abajo",u)
        r=ed.validate();self.assertFalse(r.can_simulate)
        self.assertEqual([d.element for d in r.diagnostics if d.code=="D-SIMULTANEIDAD"],[bar])
        ed.set_bar_kind(bar,"O");self.assertTrue(ed.validate().can_simulate)
        ed.undo();self.assertFalse(ed.validate().can_simulate)
        ed.bar_unlink(bar,a);ed.bar_unlink(bar,u);ed.bar_link(bar,"arriba",b)
        # B -> t -> B es una convergencia sin barra de cierre emparejada; no se inventa esa restricción.
        self.assertNotIn("D-SIMULTANEIDAD",[d.code for d in ed.validate().diagnostics])


@unittest.skipUnless(QT,"requiere PySide6")
class Incidencias(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SSAL07_cadena_transiciones_bloquea_play_e_icono_alineado_al_zoom(self):
        """REQ-MOD-02, REQ-EDT-09: transiciones consecutivas bloquean Play; icono anclado al zoom con cualquier ancho de aviso."""
        w,e=self.vacio();entradas(e.ed,"p")
        a=e.ed.add_step("g","1",True,at=(100,80));b=e.ed.add_step("g","2",at=(100,400))
        ts=[e.ed.add_transition("g","p",at=(100,y))[0] for y in (160,240,320)]
        e.ed.connect(a,ts[0]);e.ed.connect(ts[-1],b)
        for x,y in zip(ts,ts[1:]):e.ed.connect(x,y)
        e.cambia();w.resize(1366,768);w.show();QTest.qWait(20)
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertTrue(aviso.called);self.assertFalse(w.a_ejecutar.isChecked())
        self.assertIn("D-ALTERNANCIA",aviso.call_args.args[2])
        d=w.diagrama
        for ancho in (1366,1000):
            w.resize(ancho,768);QTest.qWait(20)
            self.assertEqual(d.indicador_diagnosticos.x(),d.barra.x())
            self.assertEqual(d.lista_diagnosticos.x(),d.barra.x()+48)
        imagen=d.indicador_diagnosticos.pixmap().toImage()
        self.assertEqual(imagen.pixelColor(20,30).name(),"#ffffff")
        self.assertEqual(imagen.pixelColor(21,30).name(),"#ffffff")

    def test_SSAL08_y_invalida_bloquea_vista_y_play_senala_su_barra(self):
        """REQ-MOD-03, REQ-EDT-09: la barra Y inválida bloquea el simulador y Play y se puede localizar en el dibujo."""
        w,e=self.vacio();entradas(e.ed,"p")
        a=e.ed.add_step("g","1",True,at=(100,80));b=e.ed.add_step("g","2",at=(100,400))
        t,_=e.ed.add_transition("g","p",at=(100,240));u,_=e.ed.add_transition("g","p",at=(300,240))
        e.ed.connect(t,b);e.ed.connect(u,b)
        bar=e.ed.add_bar("Y",(80,180),300)
        e.ed.bar_link(bar,"arriba",a);e.ed.bar_link(bar,"abajo",t);e.ed.bar_link(bar,"abajo",u);e.cambia()
        self.assertIn(bar,e.marcados())
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:w.a_ejecutar.setChecked(True)
        self.assertFalse(w.a_ejecutar.isChecked());self.assertIn("D-SIMULTANEIDAD",aviso.call_args.args[2])
        from grafcet.view import Vista
        from grafcet.profile import normalize_options
        v=Vista("m","","",lambda:(e.ed.model,e.layout()),normalize_options(None),presentation=e.ed.presentation)
        self.assertIsNone(v.s);self.assertIn("D-SIMULTANEIDAD",[d.code for d in v.compile_diags])

    def test_SSAL09_rodeo_de_marcas_conserva_arrastre_de_ruta_y_deshacer(self):
        """REQ-EDT-02, REQ-EDT-05: arrastrar los tres tiradores conserva la ruta manual y el rodeo, en una operación cada vez."""
        m=(M().var("p").var("n","internal","int").step("A",True).step("B")
           .trans("ida",["A"],["B"],"p").trans("vuelta",["B"],["A"],"NOT p")
           .stored("A","n","event","n + 1",event="rise(p)"))
        e=Edicion.desde(m.doc,{"A":(100,150),"ida":(100,270),"B":(100,390),"vuelta":(420,470)},"Retorno")
        self.w._establecer_edicion(e)
        ident="vuelta|A|post"
        for segmento,clave,delta in ((1,"exitY",QPointF(0,20)),(2,"laneX",QPointF(40,0)),(5,"entryY",QPointF(0,10))):
            e.seleccionar([ident]);r=next(r for r in enlaces(e.M) if r["id"]==ident)
            self.assertEqual(len(r["pts"]),8)
            handle=next(h for h in r["handles"] if h["segment"]==segmento)
            inicio=QPointF(*handle["pos"]);fin=inicio+delta
            antes=copy.deepcopy(e.ed.link_styles());n=len(e.ed.undo_stack)
            e.prensar(inicio);self.assertEqual(e.arrastre["tipo"],"tramo")
            e.mover(fin);e.soltar(fin)
            self.assertEqual(len(e.ed.undo_stack),n+1)
            despues=e.ed.link_styles();self.assertIn(clave,despues[ident]["route"])
            self.assertNotEqual(despues,antes)
            r=next(r for r in enlaces(e.M) if r["id"]==ident)
            self.assertLessEqual(r["pts"][-4][1],96)
            e.deshacer();self.assertEqual(e.ed.link_styles(),antes)
