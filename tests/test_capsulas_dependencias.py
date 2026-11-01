"""Regresiones visuales: tiempos sin cápsula y dependencias entre esquinas."""
import copy
import json
import re
import unittest
from test_dibujo_vista import (QT, QJS, ROOT, vista, modelo_temporizado, corriendo, dibujo, texto,
                               ejemplo, dibujo_con, rayas, MOCK_DOM, dibujar_con_js)
from grafcet.builder import M
if QT:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontMetricsF
    from escritorio import diagrama as dg
if QJS:
    from PySide6.QtQml import QJSEngine


@unittest.skipUnless(QT, "requiere PySide6")
class CapsulasDependencias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SVIS06_dos_decimales_sin_cambiar_lleva_ni_preset(self):
        """REQ-TMP-01, REQ-SIM-03: shown mantiene dos decimales al contar y vencer; la tabla conserva sus unidades."""
        v = corriendo(*modelo_temporizado())
        v.act("avanzar", {"us": 1_100_000})
        t = next(t for t in v.state()["temporal"].values() if t["token"] == "3s")
        self.assertEqual((t["shown"], t["lleva"], t["preset"]), ("2,10 s", "2,1 s", "3 s"))
        v.act("avanzar", {"us": 900_000})
        t = next(t for t in v.state()["temporal"].values() if t["token"] == "3s")
        self.assertEqual(t["shown"], "3,00 s ✓")

    def test_SVIS07_digitos_tabulares_alineados_al_token_de_desconexion(self):
        """REQ-TMP-01, REQ-SIM-03: el tiempo sigue el extremo derecho del token de desconexión con dígitos tabulares."""
        m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(3 s, p, 2 s)")
        v = vista(m, {"A": (220, 180)})
        v.act("fijar", {"cambios": {"p": True}}); v.act("avanzar", {"us": 3_000_000})
        v.act("fijar", {"cambios": {"p": False}})
        bordes=[]
        for dt, esperado in ((420_000,"0,42 s"),(1_000_000,"1,42 s")):
            v.act("avanzar", {"us":dt}); t=next(iter(v.state()["temporal"].values()))
            self.assertEqual((t["token"],t["off"],t["shown"]),("2s",True,esperado))
            sc,_=dibujo(v); it=texto(sc,esperado); r=it.sceneBoundingRect()
            bordes.append(it.sceneBoundingRect().right())
            fm=QFontMetricsF(it.font())
            self.assertAlmostEqual(fm.horizontalAdvance("1111"),fm.horizontalAdvance("8888"),delta=.01)
            cond=texto(sc,"3s/p/2s"); segs=v.model["steps"][0]["actions"][0]["cond"]
            limites=dg._Pintor.limites(segs,13); i=[s["t"] for s in segs].index("2s")
            self.assertAlmostEqual(r.right(),cond.pos().x()+limites[i+1],delta=.01)
        self.assertAlmostEqual(*bordes,delta=.01)

    def test_SVIS10_tiempo_receptividad_no_tapa_el_enlace_vertical(self):
        """REQ-EDT-02, REQ-SIM-03: el tiempo sobre el primer token deja libre el enlace vertical."""
        from PySide6.QtCore import QRectF
        m=M().var("p").step("A",True).step("B").trans("t",["A"],["B"],"delay(3 s, p, 0 s)")
        v=vista(m,{"A":(220,60),"t":(220,140),"B":(220,220)})
        v.act("fijar",{"cambios":{"p":True}}); v.act("avanzar",{"us":420_000})
        sc,_=dibujo(v); r=texto(sc,"0,42 s").sceneBoundingRect()
        self.assertFalse(r.intersects(QRectF(220+dg.SX-1,100,2,80)))

    def test_SVIS08_dependencias_por_esquinas_en_ocho_orientaciones_qt_y_js(self):
        """REQ-JER-04, REQ-EDT-02: las dependencias unen las esquinas enfrentadas, superiores de E e inferiores de S; con empate horizontal conservan el trazado anterior."""
        for dx,dy in ((-320,0),(320,0),(0,-320),(0,320),(-320,-240),(320,-240),(-320,240),(320,240)):
            with self.subTest(dx=dx,dy=dy):
                v=ejemplo("macroetapa"); mac=v.model["macros"][0]
                mac.update(x=500+dx-dg.SX,y=400+dy)
                for s in v.model["steps"]:
                    if s["id"] in (mac["entry"],mac["exit"]):
                        s.update(x=500-dg.SX,y=340 if s["id"]==mac["entry"] else 460)
                pos=dg.posiciones(v.model); a=pos[mac["id"]]
                sc,_=dibujo_con(v,True); lineas=sorted((r.line().x1(),r.line().y1(),r.line().x2(),r.line().y2()) for r in rayas(sc))
                self.assertEqual(len(lineas),2)
                if dx:
                    h = -dg.H if dx > 0 else dg.H
                    esperado = sorted((a[0]+h,a[1]+vert,pos[mac[k]][0]-h,pos[mac[k]][1]+vert)
                                      for k,vert in (("entry",-dg.H),("exit",dg.H)))
                    self.assertEqual(lineas, esperado)
                else:
                    for x,y,u,w in lineas:
                        self.assertAlmostEqual(x,a[0])
                        self.assertAlmostEqual(u,a[0])
                        self.assertEqual(abs(y-a[1]),dg.H)
                if QJS:
                    arbol=dibujar_con_js(v.model,v.state()); paths=arbol["hijos"][0]["hijos"]
                    js=sorted(tuple(map(float,re.findall(r"-?\d+(?:\.\d+)?",p["attrs"]["d"]))) for p in paths if p["tag"]=="path")
                    self.assertEqual(js,lineas)


@unittest.skipUnless(QJS, "requiere QtQml")
class CapsulasJs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SVIS09_js_usa_nth_y_token_sin_capsula(self):
        """REQ-TMP-01, REQ-SIM-03: JS sitúa el tiempo sobre la aparición exacta y ancla a izquierda o derecha según el retardo."""
        eng=QJSEngine(); fuente=(ROOT/"tools"/"dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}","Object.assign({x, y}, attrs)")
        r=eng.evaluate(MOCK_DOM+fuente); self.assertFalse(r.isError(),r.toString())
        for token,nth,cx in (("3s",0,110),("3s",1,310),("2s",0,510)):
            t={"expr":"e","shown":"0,42 s","estado":"contando","token":token,"nth":nth}
            code="""var parent=new MockEl('g');
var tx={children:[100,300,500].map(x=>({getBBox:()=>({x:x,width:20})}))};
timerText(parent,tx,[{t:'3s'},{t:'3s'},{t:'2s'}],100,'e',{temporal:{t:%s}});
JSON.stringify(volcar(parent));""" % json.dumps(t)
            r=eng.evaluate(code); self.assertFalse(r.isError(),r.toString()); g=json.loads(r.toString())["hijos"][0]
            (tx,)=g["hijos"]
            self.assertEqual(tx["tag"],"text")
            self.assertEqual((tx["attrs"]["x"],tx["attrs"]["text-anchor"]),(cx-10,"start"))
            t["off"]=True
            r=eng.evaluate(code.replace(json.dumps({k:v for k,v in t.items() if k!="off"}),json.dumps(t)))
            self.assertFalse(r.isError(),r.toString())
            tx=json.loads(r.toString())["hijos"][0]["hijos"][0]
            self.assertEqual((tx["attrs"]["x"],tx["attrs"]["text-anchor"]),(cx+10,"end"))
