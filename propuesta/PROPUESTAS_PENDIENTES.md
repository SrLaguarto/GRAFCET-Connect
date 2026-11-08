# Propuestas pendientes (no implementadas)

Cada punto se aparta de una decisión vigente (`docs/04_Decisiones_de_implementacion.md`) o de lo que fijan las pruebas, así
que **no está en el código**. Se describe con su motivo y, cuando se puede, una maqueta. Las maquetas salen de
`python propuesta/herramientas/capturar.py --escenas maqueta-panel-bajo` o son capturas reales con el estado indicado.

## P1. Propiedades en un cuarto de pantalla (apartaría P-IMP-128 / 118 / 120 / 93)

**Problema.** Con una transición seleccionada, el panel inferior crece hasta ≈ 334 px para ver entera la paleta de operadores
de la receptividad sin barra de desplazamiento (`alto_opciones.py`). A 960×520 el dibujo se queda en ≈ 90–190 px de alto
mientras el panel está abierto (se esconde solo al hacer clic fuera, salvo «Fijar»).

**Propuesta.** Por debajo de 560 px de alto, la paleta de operadores en una sola fila con desplazamiento horizontal y el panel
con ≈ 190 px; el dibujo conserva la mitad del alto. Por encima de 560 px, todo igual.

**Maqueta.** `capturas/maquetas/maqueta-panel-bajo-cuarto.png` (el panel a 190 px, tal como lo dejaría el usuario con el
divisor; la paleta de bloques ya se desplaza). **Motivo de no hacerlo:** la decisión fija el crecimiento a ≈ 334 px.

## P2. Panel de Entradas debajo del dibujo en pantalla partida (apartaría P-IMP-42 / 44 / 47 / 78)

**Problema.** En simulación a 960×1040 el panel derecho (ancho fijo de 218 px) deja 700 px al dibujo; las tablas de salidas y
temporizadores caben justo.

**Propuesta.** Por debajo de 1000 px de ancho, las entradas en una banda horizontal bajo el dibujo (botones en fila de 40 px)
y salidas y temporizadores en pestañas de esa banda; el dibujo recupera ≈ 220 px. **Motivo de no hacerlo:** las decisiones
fijan paneles laterales de ancho fijo y plegables del todo; este cambio mueve el panel de sitio.

## P3. Filas táctiles en la vista de E/S externas (apartaría P-IMP-63)

**Problema.** Los canales y las listas de variables miden 16 px de alto (`ALTO_FILA`): se arrastran con el ratón, pero con
el dedo es difícil acertar. A 1366×768 caben 20 + 10 canales por lado sin desplazamiento (lo fija `test_SESP14`).

**Propuesta.** Un modo «táctil» automático (filas de 28 px con desplazamiento) cuando el sistema avise de pantalla táctil, y
asignación por toque (tocar la variable, tocar el canal) además del arrastre. **Motivo de no hacerlo:** P-IMP-63 pide el estilo
plano y compacto y las pruebas fijan alturas y capacidad.

## P4. Pestañas plegadas de 32 px (lo fijan las pruebas, no una decisión)

Las pestañas de los paneles plegados miden 26 px (`PanelPlegable.GROSOR_PESTANA`) y varias pruebas comprueban ese número
(`SPAN02`, `SPAN04`…). Para un objetivo táctil de 32 px basta subir esa constante; las pruebas tendrían que cambiar.

## P5. Escala tipográfica para proyector (transversal)

**Propuesta.** Por encima de 1600 px de ancho, texto base de 14 px y secundario de 13 px (hoy 13 y 12). La hoja global ya
lo admite (`estilo.hoja_global` recibe los tokens), pero hay ≈ 25 hojas locales con tamaños propios; hay que revisarlas una a
una y comprobar las pruebas de ajuste (`SEDI122`, `SESP14`, la paleta de 218 px). Se deja para la ronda 2 por riesgo, no por
decisión.

## P6. Zoom del dibujo en la fila del título (lo fijan las pruebas)

El recuadro de zoom flota sobre el dibujo y «Centrar todo» reserva arriba su alto más 24 px (`MARGEN_AJUSTE`; lo comprueban
`SEDI324` y compañía). Pasar los controles a la fila del título devolvería ≈ 64 px de dibujo a 960×520. Cambiaría pruebas.
