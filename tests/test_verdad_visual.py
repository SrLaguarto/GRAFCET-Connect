"""Color de simulación por subexpresión, separado de la selección del editor."""
import copy
import json
import re
import unittest
from test_dibujo_vista import (QT, QJS, ROOT, vista, dibujo, texto, textos, ejemplo,
                               MOCK_DOM, dibujar_con_js)
from grafcet.builder import M
from grafcet.view import norm
if QT:
    from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsScene
    from PySide6.QtGui import QTextCursor
    from PySide6.QtCore import QPointF
    from escritorio import diagrama as dg
if QJS:
    from PySide6.QtQml import QJSEngine


def modelo():
    m = (M().var("p").var("paro").var("y", "output").var("mem", "internal")
         .var("Potenc", kind="int", init="7").step("A", True).step("B"))
    m.trans("t", ["A"], ["B"],
            "p AND y AND mem AND active(A) AND Potenc >= 5 AND delay(3 s, p, 2 s) AND true AND false")
    m.cont("A", "y", "Potenc >= 5")
    m.stored("A", "mem", "event", "true", event="rise(paro) AND Potenc >= 5")
    m.stored("A", "mem", "activation", "true")
    return vista(m, {"A": (180, 100), "t": (180, 230), "B": (180, 350)})


def colores(item):
    out=[]
    for i in range(len(item.toPlainText())):
        cur=QTextCursor(item.document()); cur.setPosition(i); cur.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        out.append(cur.charFormat().foreground().color().name())
    return out


def nodos(arbol):
    yield arbol
    for hijo in arbol["hijos"]:
        yield from nodos(hijo)


@unittest.skipUnless(QT, "requiere PySide6")
class VerdadVisual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_SCOL01_vista_valora_referencias_comparacion_temporal_y_constantes_sin_mutar(self):
        """REQ-SIM-03, REQ-TMP-01: verdad de cada nodo con el entorno del motor, sin alterar estado, tiempos ni traza."""
        v=modelo(); v.act("fijar", {"cambios":{"p":True}}); v.act("avanzar", {"us":3_000_000})
        antes=copy.deepcopy(v.s.z); traza=copy.deepcopy(v.s.trace.records)
        segs=v.model["transitions"][0]["cond"]; st=v.state()
        for nombre in ("p","y","mem","XA"," ≥ ","3s","/","2s","1"):  # (la variable de etapa es un solo segmento: XA, sin subíndice)
            ss=[s for s in segs if s["t"]==nombre]; self.assertTrue(ss,nombre)
            self.assertTrue(all(any(st["truth"].get(k) is True for k in s["eval"]) for s in ss),nombre)
        cero=next(s for s in segs if s["t"]=="0")
        self.assertFalse(any(st["truth"][k] for k in cero["eval"]))
        self.assertEqual(st,v.state()); self.assertEqual(antes,v.s.z); self.assertEqual(traza,v.s.trace.records)
        # En la desconexión el retardo sigue verdadero hasta agotar su preset.
        v.act("fijar", {"cambios":{"p":False}})
        self.assertTrue(any(v.state()["truth"][k] for k in next(s for s in segs if s["t"]=="3s")["eval"]))
        v.act("avanzar", {"us":2_000_000})
        self.assertFalse(any(v.state()["truth"][k] for k in next(s for s in segs if s["t"]=="3s")["eval"]))

    def test_SCOL02_qt_colorea_toda_comparacion_temporal_y_acciones_solo_en_simulacion(self):
        """REQ-SIM-03, REQ-EDT-02: operandos, operadores y duración verdaderos en azul eléctrico; edición y falso conservan su color."""
        v=modelo(); v.act("fijar", {"cambios":{"p":True}}); v.act("avanzar", {"us":3_000_000})
        sc,_=dibujo(v); plano="".join(s["t"] for s in v.model["transitions"][0]["cond"])
        cs=colores(texto(sc,plano))
        for fragmento in ("p","y","mem","XA","[Potenc ≥ 5]","3s/p/2s","1"):
            inicio=plano.index(fragmento)
            self.assertEqual(cs[inicio:inicio+len(fragmento)],[dg.COL["true_text"]]*len(fragmento),fragmento)
        self.assertNotEqual(cs[-1],dg.COL["true_text"])
        self.assertTrue(all(dg.COL["true_text"] not in colores(it) for it in textos(sc) if ":=" in it.toPlainText()))
        for it in textos(sc):
            if it.toPlainText() in ("[Potenc ≥ 5]","↑paro · [Potenc ≥ 5]"):
                self.assertEqual(colores(it)[-len("[Potenc ≥ 5]"):],[dg.COL["true_text"]]*len("[Potenc ≥ 5]"))
        sc0,_=dibujo(v,{})
        self.assertNotIn(dg.COL["true_text"],colores(texto(sc0,plano)))
        v.act("fijar", {"cambios":{"Potenc":1}}); sc1,_=dibujo(v)
        c=next(it for it in textos(sc1) if it.toPlainText()=="[Potenc ≥ 5]")
        self.assertNotIn(dg.COL["true_text"],colores(c))

    def test_SCOL03_activo_azul_electrico_y_seleccion_azul(self):
        """REQ-SIM-03, REQ-EDT-02: etapa y acción activas en azul eléctrico; selección independiente azul."""
        v=modelo(); sc,_=dibujo(v)
        rellenos=[it for it in sc.items() if isinstance(it,QGraphicsRectItem) and it.brush().color().name()==dg.COL["active_soft"]]
        self.assertGreaterEqual(len(rellenos),2)
        self.assertTrue(all(it.pen().color().name()==dg.COL["active"] for it in rellenos))
        dg.dibujar(sc,v.model,v.state(),sel={"A","accion:"+v.model["steps"][0]["actions"][0]["id"]})
        self.assertTrue(any(hasattr(it,"pen") and it.pen().color().name()==dg.COL["accent"] for it in sc.items()))

    def test_SCOL04_parcial_y_recinto_rotulos_izquierdos_y_zona_de_nombre(self):
        """REQ-JER-05, REQ-EDT-02: ambos rótulos alineados a 30 px; nombre inferior del parcial mantiene su zona de arrastre."""
        v=ejemplo("encapsulacion"); sc,_=dibujo(v)
        pt=next(p for p in v.model["partials"] if p.get("ownerStep")); b=dg.cajas_parciales(v.model)[pt["id"]]
        top=next(it for it in textos(sc) if it.toPlainText()==v.model["names"][pt["ownerStep"]] and abs(it.pos().x()-b["x0"]-30)<.01)
        self.assertAlmostEqual(top.pos().x(),texto(sc,pt["label"]).pos().x())
        pt.pop("ownerStep"); pt["kind"]="partial"; sc,_=dibujo(v)
        nombre=texto(sc,pt["label"])
        self.assertAlmostEqual(nombre.pos().x(),b["x0"]+30)
        self.assertEqual(dg.marco_en(v.model,QPointF(b["x0"]+34,b["y1"]+10)),pt["id"])

    def test_SCOL05_norm_sin_clave_compatible_y_constante_numerica_no_booleana(self):
        """REQ-SIM-03: norm conserva sus segmentos históricos; el 1 numérico no recibe verdad booleana."""
        v=modelo(); lit={"operator":"lit","literal":{"type":"bool","value":True}}
        self.assertEqual(norm(lit),[{"t":"= 1"}])
        numero={"operator":"lit","literal":{"type":"int","value":"1"}}
        self.assertEqual(norm(numero,key="e"),[{"t":"1"}])

    def test_SCOL07_limite_temporal_de_accion_refleja_su_duracion_sin_cambiar_el_motor(self):
        """REQ-TMP-01, REQ-SIM-03: el límite dibujado como negación se resalta mientras la condición negada es verdadera."""
        v=vista(M().var("y","output").step("A",True).cont("A","y",limit_us=1_000_000),{"A":(180,100)})
        segs=v.model["steps"][0]["actions"][0]["cond"]
        sc,_=dibujo(v); condicion=texto(sc,"1s/XA")
        self.assertEqual(colores(condicion),[dg.COL["true_text"]]*len("1s/XA"))
        v.act("avanzar",{"us":1_000_000}); sc,_=dibujo(v)
        self.assertNotIn(dg.COL["true_text"],colores(texto(sc,"1s/XA")))
        self.assertFalse(v.state()["outputs"]["y"]["value"])

    def test_SCOL08_negadas_en_receptividad_condicion_y_evento_segun_valor_de_negacion(self):
        """REQ-SIM-03, REQ-EDT-02: NOT p y NOT X se resaltan cuando la negación es verdadera, tanto texto como barra."""
        from test_dibujo_vista import barras_negado
        m=(M().var("p").var("bloqueo").var("y","output").var("n","internal","int")
           .step("A",True).step("B"))
        m.trans("t",["A"],["B"],"p AND NOT p AND NOT active(A) AND NOT active(B) AND bloqueo")
        m.cont("A","y","NOT p").stored("A","n","event","n + 1",event="rise(NOT p)")
        v=vista(m,{"A":(180,100),"t":(180,220),"B":(180,340)})
        for valor in (False,True,False):
            v.act("fijar",{"cambios":{"p":valor}}); st=v.state(); sc,_=dibujo(v)
            plano="".join(s["t"] for s in v.model["transitions"][0]["cond"])
            t=texto(sc,plano); cs=colores(t)
            self.assertEqual(cs[0]==dg.COL["true_text"],valor)
            self.assertEqual(cs[plano.index(" · ")+3]==dg.COL["true_text"],not valor)  # (la p negada, tras «p · »)
            self.assertNotEqual(cs[plano.index("XA")],dg.COL["true_text"])
            self.assertEqual(cs[plano.index("XB")],dg.COL["true_text"])
            self.assertEqual(colores(texto(sc,"p"))==[dg.COL["true_text"]],not valor)
            evento=next(it for it in textos(sc) if it.toPlainText()=="↑(p)")
            segmentos = next(a["event"] for a in v.model["steps"][0]["actions"] if a.get("trigger") == "event")
            flanco = st["truth"].get(segmentos[0]["eval"][0], False)
            self.assertEqual(colores(evento)[2]==dg.COL["true_text"],flanco)
            verdes=[it for it in barras_negado(sc) if it.pen().color().name()==dg.COL["true_text"]]
            self.assertEqual(len(verdes),(1 if valor else 4) - int(not valor and not flanco))
            # El estado sigue exponiendo el valor propio de cada nodo, sin invertir las variables.
            self.assertEqual(st["values"]["p"],valor)


@unittest.skipUnless(QJS,"requiere QtQml")
class ParidadVerde(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_SCOL06_web_y_qt_mismos_segmentos_y_azul_electrico_para_actividad_y_verdad(self):
        """REQ-SIM-03, REQ-EDT-02: JS ejecutado colorea los mismos segmentos que Qt y usa el mismo azul eléctrico para actividad y verdad."""
        v=modelo(); v.act("fijar", {"cambios":{"p":True}}); v.act("avanzar", {"us":3_000_000})
        st=v.state(); sc,_=dibujo(v)
        eng=QJSEngine(); js=(ROOT/"tools/dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}","Object.assign({x, y}, attrs)")
        self.assertFalse(eng.evaluate(MOCK_DOM+js).isError())
        expresiones=[v.model["transitions"][0]["cond"]]
        for valor in (False,True):
            m={"operator":"not","operands":[{"operator":"ref","reference":"p"}]}
            segs=norm(m,key="neg")
            verdad={"neg":not valor,"neg.0":valor}
            scn=QGraphicsScene()
            pt=dg._Pintor(scn); pt.verdaderos={k for k,v in verdad.items() if v}
            pt.text(0,20,segs,14,"text",1)
            self.assertEqual(colores(texto(scn,"p"))==[dg.COL["true_text"]],not valor)
            code="var gn=new MockEl('g'); segText(gn,0,20,%s,'tcond','start',%s); JSON.stringify(volcar(gn));" % (json.dumps(segs),json.dumps(verdad))
            r=eng.evaluate(code); self.assertFalse(r.isError(),r.toString()); arbol=json.loads(r.toString())
            self.assertEqual(arbol["hijos"][0]["hijos"][0]["attrs"].get("class")=="verdadero",not valor)
            self.assertEqual(arbol["hijos"][1]["attrs"]["class"]=="neg verdadero",not valor)
        expresiones.extend(a[k] for a in v.model["steps"][0]["actions"] for k in ("cond","event") if a.get(k))
        for segs in expresiones:
            code="var g=new MockEl('g'); segText(g,0,0,%s,'tcond','start',%s); JSON.stringify(volcar(g));" % (json.dumps(segs),json.dumps(st["truth"]))
            r=eng.evaluate(code); self.assertFalse(r.isError(),r.toString()); arbol=json.loads(r.toString())
            spans=arbol["hijos"][0]["hijos"]
            esperado=[any(st["truth"].get(k) is True for k in s.get("eval",[])) for s in segs]
            self.assertEqual([s["attrs"].get("class")=="verdadero" for s in spans],esperado)
            item=texto(sc,"".join(s["t"] for s in segs)); qt=colores(item); n=0
            for s,verde in zip(segs,esperado):
                self.assertEqual(qt[n:n+len(s["t"])]==[dg.COL["true_text"]]*len(s["t"]),verde); n+=len(s["t"])
        css=(ROOT/"tools/dibujo.css").read_text(encoding="utf-8")
        self.assertEqual(dg.COL["active"],"#40d641")
        self.assertNotEqual(dg.COL["true_text"],dg.COL["accent"])
        self.assertIn("--sim:"+dg.COL["active"],css); self.assertIn("--sim-soft:"+dg.COL["active_soft"],css)
        for selector in (".step.active rect.outer",".act.on rect",".verdadero"):
            regla=re.search(re.escape(selector)+r"\{([^}]+)\}",css)[1]
            self.assertIn("var(--truth)" if selector==".verdadero" else "var(--sim)",regla)
        arbol=dibujar_con_js(v.model,st)
        clases=[n["attrs"].get("class","").split() for n in nodos(arbol)]
        self.assertTrue(any("step" in c and "active" in c for c in clases))
        self.assertTrue(any("act" in c and "on" in c for c in clases))
