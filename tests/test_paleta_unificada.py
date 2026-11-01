"""Fichas compartidas por icono y arrastre, con secciones en dos columnas."""
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt, QT
if QT:
    from PySide6.QtCore import QPoint, QPointF, QRect, Qt
    from PySide6.QtGui import QFont, QFontMetrics, QImage, QPainter, QPixmap
    from PySide6.QtTest import QTest
    from escritorio import propiedades as pr


@unittest.skipUnless(QT, "requiere PySide6")
class PaletaUnificada(BaseQt):
    def preparar(self):
        w,e=self.vacio();w.resize(1366,768);w.show()
        for _ in range(5):self.app.processEvents()
        return w,w.paleta

    def test_SPAL01_icono_y_arrastre_comparten_dibujo_y_pixeles(self):
        """REQ-EDT-02: las trece fichas usan la misma función y la misma imagen en lista y arrastre, solo escalada y centrada."""
        for clave in pr.COLOCABLES:
            with self.subTest(clave=clave):
                with mock.patch.object(pr,"_pintar_ficha",wraps=pr._pintar_ficha) as pintar:
                    icono=pr.icono(clave);pm,_=pr.figura(clave,1,2)
                    self.assertEqual([c.args[1] for c in pintar.call_args_list],[clave,clave])
                escalada=pm.scaled(192,192,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                escalada.setDevicePixelRatio(1)
                esperado=QPixmap(192,192);esperado.fill(Qt.GlobalColor.transparent)
                p=QPainter(esperado);p.drawPixmap(QPointF((192-escalada.width())/2,(192-escalada.height())/2),escalada);p.end()
                real=icono.pixmap(192,192).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                esperado=esperado.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                self.assertEqual(real.size(),esperado.size());self.assertEqual(bytes(real.constBits()),bytes(esperado.constBits()))

    def test_SPAL02_cajas_de_acciones_y_forzado_tienen_la_altura_de_etapa(self):
        """REQ-EDT-02: la altura de referencia es 44 en etapas, cinco acciones y forzado, con cajas de acción idénticas."""
        claves=["etapa",*["accion:"+t for t in ("continua","condicionada","activacion","desactivacion","evento")],"forzado"]
        for clave in claves:
            im=pr.figura(clave)[0].toImage();x=26 if clave=="etapa" else 8
            ys=[y for y in range(im.height()) if im.pixelColor(x,y).alpha()>10]
            self.assertEqual((min(ys),max(ys)),(21,66),clave)
            if clave!="etapa":
                self.assertEqual(im.size().toTuple(),(96,88))
                self.assertTrue(all(im.pixelColor(88,y).alpha()>0 for y in range(23,66)))

    def test_SPAL03_solo_transicion_tiene_conectores_y_barra_sin_ramas(self):
        """REQ-EDT-02, REQ-MOD-03: no hay tallos en etapas ni enlaces a acciones; la simultaneidad contiene solo dos trazos."""
        for clave in ("etapa","etapa_inicial","macroetapa","encapsulante"):
            im=pr.figura(clave)[0].toImage()
            self.assertTrue(all(im.pixelColor(48,y).alpha()==0 for y in [*range(21),*range(68,88)]))
        for clave in ("accion:continua","accion:condicionada","accion:activacion","accion:desactivacion","accion:evento","forzado"):
            im=pr.figura(clave)[0].toImage()
            self.assertTrue(all(im.pixelColor(x,y).alpha()==0 for x in range(6) for y in range(im.height())))
        im=pr.figura("simultaneidad")[0].toImage()
        filas={y for y in range(im.height()) if any(im.pixelColor(x,y).alpha()>0 for x in range(im.width()))}
        self.assertEqual(filas,{43,44,51,52})
        im=pr.figura("transicion")[0].toImage()
        self.assertTrue(all(im.pixelColor(48,y).alpha()>0 for y in range(18,71)))

    def test_SPAL04_g_sobre_el_borde_y_fuente_normal_proporcionada(self):
        """REQ-EDT-02, REQ-JER-02: la G corta el borde inferior tanto al arrastrar como en el icono, con peso normal."""
        im=pr.figura("parcial")[0].toImage()
        self.assertGreater(im.pixelColor(130,130).alpha(),0);self.assertEqual(im.pixelColor(137,130).alpha(),0)
        self.assertTrue(any(im.pixelColor(x,y).alpha()>0 for x in range(140,158) for y in range(131,139)))
        pm=QPixmap(188,140);pm.fill(Qt.GlobalColor.transparent);p=QPainter(pm)
        pr._pintar_ficha(p,"parcial");fuente=p.font();p.end()
        self.assertFalse(fuente.bold());self.assertLess(fuente.pixelSize(),120*.2)

    def test_SPAL05_dos_columnas_cabeceras_completas_y_nombres_debajo(self):
        """REQ-EDT-02, REQ-EDT-09: orden y cabeceras se conservan, dos fichas por fila y espacio para todos los nombres."""
        w,p=self.preparar();self.assertEqual(w.dock.width(),218)
        self.assertEqual([p.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.count()) if p.item(i).data(Qt.ItemDataRole.UserRole)],list(pr.COLOCABLES))
        self.assertEqual((p.ICONO.width(),p.ICONO.height()),(72,64))
        fila=0;fuente=QFont(p.font());fuente.setPixelSize(11);fm=QFontMetrics(fuente)
        for titulo,claves in pr.SECCIONES:
            cab=p.visualItemRect(p.item(fila));self.assertEqual(p.item(fila).text(),titulo)
            self.assertEqual((cab.x(),cab.width()),(0,p.viewport().width()));fila+=1
            for j,clave in enumerate(claves):
                r=p.visualItemRect(p.item(fila+j));self.assertEqual(r.x(),(j%2)*(p.viewport().width()//2))
                if j%2:self.assertEqual(r.y(),p.visualItemRect(p.item(fila+j-1)).y())
                texto=fm.boundingRect(QRect(0,0,r.width()-14,27),Qt.TextFlag.TextWordWrap,p.item(fila+j).text())
                self.assertLessEqual(texto.height(),27);self.assertLessEqual(texto.width(),r.width()-14)
            fila+=len(claves)
        self.assertEqual(fila,p.count())

    def test_SPAL06_ancho_y_minimo_no_crecen_y_scroll_alcanza_todas(self):
        """REQ-EDT-09: se conserva el ancho de 218 y el mínimo anterior; a 1366×768 y 1000×600 se alcanzan las fichas."""
        w,p=self.preparar()
        self.assertLessEqual(p.minimumSizeHint().height(),3*34+2*p.frameWidth()+2)
        for ancho,alto in ((1366,768),(1000,600)):
            w.resize(ancho,alto)
            for _ in range(5):self.app.processEvents()
            self.assertEqual((w.width(),w.height()),(ancho,alto));self.assertEqual(w.dock.width(),218)
            for i in range(p.count()):
                p.scrollToItem(p.item(i));self.app.processEvents()
                self.assertTrue(p.viewport().rect().contains(p.visualItemRect(p.item(i))),p.item(i).text())
            self.assertEqual(p.horizontalScrollBar().maximum(),0);self.assertGreater(p.verticalScrollBar().maximum(),0)

    def test_SPAL07_gestos_reales_arrastran_parcial_y_accion_a_su_escala(self):
        """REQ-EDT-02, REQ-EDT-03: pulsar y arrastrar conserva MIME, imagen compartida y punto de colocación con zoom y DPR."""
        w,p=self.preparar();capturas=[]
        class Drag:
            def __init__(self,padre):self.d={};capturas.append(self.d)
            def setMimeData(self,m):self.d["clave"]=m.text()
            def setPixmap(self,pm):self.d["pm"]=pm
            def setHotSpot(self,punto):self.d["punto"]=punto
            def exec(self,*a):return Qt.DropAction.IgnoreAction
        p.escala=lambda:1.5
        with mock.patch.object(pr,"QDrag",Drag):
            for clave in ("parcial","accion:condicionada"):
                item=next(p.item(i) for i in range(p.count()) if p.item(i).data(Qt.ItemDataRole.UserRole)==clave)
                p.scrollToItem(item);self.app.processEvents();r=p.visualItemRect(item);vp=p.viewport()
                antes=len(capturas)
                QTest.mousePress(vp,Qt.MouseButton.LeftButton,pos=r.center())
                QTest.mouseMove(vp,r.center()+QPoint(30,0));QTest.mouseMove(vp,r.center()+QPoint(45,0))
                QTest.mouseRelease(vp,Qt.MouseButton.LeftButton,pos=r.center()+QPoint(45,0))
                self.assertEqual(len(capturas),antes+1);c=capturas[-1];self.assertEqual(c["clave"],clave)
                esperado,punto=pr.figura(clave,1.5,p.devicePixelRatioF())
                self.assertEqual(c["punto"],punto);self.assertEqual(c["pm"].toImage(),esperado.toImage())
        for clave in pr.COLOCABLES:
            for escala,dpr in ((.5,1),(1,2),(1.7,2)):
                pm,punto=pr.figura(clave,escala,dpr)
                self.assertEqual(pm.devicePixelRatioF(),dpr)
                self.assertTrue(QRect(0,0,round(pm.width()/dpr),round(pm.height()/dpr)).contains(punto))
