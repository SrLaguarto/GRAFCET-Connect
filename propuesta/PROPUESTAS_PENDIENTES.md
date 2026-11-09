# Propuestas pendientes (no implementadas) y propuestas descartadas

Cada punto se aparta de una decisión vigente (`docs/04_Decisiones_de_implementacion.md`) o de lo que fijan las pruebas, así
que **no está en el código** (salvo P12 y P13, dos apartamientos *menores* de la forma de una tabla que sí están aplicados y se
documentan aquí con su motivo). Se describe con su motivo y, cuando se puede, una maqueta o la cifra medida. Las cifras salen de
`propuesta/herramientas/medir.py` y `contrastes.py`; **las maquetas son capturas de la ventana real, retocadas por script**
(`python propuesta/herramientas/maquetas.py`, salida en `propuesta/capturas/maquetas/`): el script recoloca controles o fuerza un
ajuste solo en la ventana que captura, sin tocar la interfaz.

«Táctil» significa aquí el **panel táctil del portátil** (*touchpad*): hay teclado, dos dedos desplazan, el pellizco acerca y el
toque con dos dedos es el clic derecho. No hay pantalla táctil que atender.

Qué ha cambiado en la ronda 3: P2, P3 y P7 llevan maqueta; P7 («Modo aula») queda cubierta en parte por la escala que cambia sola a
pantalla completa (ver abajo) y se reduce a lo que falta; se añade D1, la pulsación mantenida que se retiró (P-IMP-75).
Qué ha cambiado en la ronda 4: P7 explica con cifras qué cubre la escala automática y qué no (proyectores de 1366×768 y de 1280×720/800);
P3 y P10 cuentan lo que la rama ya hace sin tocar lo que fijan las pruebas (la vista de E/S sube de tamaño a pantalla completa; la columna
del nombre de Variables ya no se aplasta).
Qué ha cambiado en la ronda 5: se añade **P12** («Papel» y «Tipo» abreviados en el panel de Variables de 218 px: apartamiento menor de P-IMP-42, que
pedía el árbitro) y **P13** (las columnas que ceden ante el nombre en las tablas de estado de la simulación); P10 recoge que a 1920×1080 los paneles
laterales llegan a 300 px y que la columna del nombre ya mide ≥ 96 px a cualquier tamaño.

## Descartada

### D1. Pulsación mantenida sobre una entrada para abrir el menú (se retiró de la rama; apartaba P-IMP-75)

En la ronda 2 se añadió que mantener ≈ 500 ms una entrada de la simulación soltara el pulsador y abriera el menú contextual
(«Convertir en interruptor / pulsador», NA/NC), con la idea de dar al dedo lo que el botón derecho da al ratón.

**Motivo de descartarla.** Cambia lo que hace una entrada: **P-IMP-75** fija cada entrada booleana como un pulsador momentáneo
(«presionar y soltar dan dos cambios») y la tarea central del aula —pulsar y mantener «marcha» mientras corre un temporizador de 3 s— deja de
poder hacerse, porque a los 0,5 s el pulsador se suelta solo y sale un menú. Además el rótulo prometía «mantener: enclavar», y el menú no enclava.
No hay pantalla táctil que lo justifique: con el panel táctil del portátil el toque con dos dedos ya es el clic derecho.

**Estado.** Retirada del código. Mantener pulsado se comporta como en `main` (la entrada sigue a 1 y apretada mientras dure el clic); el rótulo bajo
«Entradas» dice «Clic: pulsar · Ctrl+clic: enclavar · Clic derecho: tipo». `propuesta/herramientas/pulsacion.py` lo comprueba (1,5 s mantenido: valor 1,
`down` verdadero, ningún menú) y se ejecuta igual contra `main`.

## Pendientes

### P1. Propiedades en un cuarto de pantalla: la paleta de operadores en una fila (apartaría P-IMP-128 / 118 / 120 / 93)

**Problema.** Con una transición seleccionada, el panel inferior crece hasta ≈ 334 px para ver entera la paleta de operadores de
la receptividad sin barra de desplazamiento; a 960 px de ancho, las categorías de bloques pasan además a dos filas (todas visibles, ninguna cortada) y el
panel pide unos 36 px más. A 960×520 el dibujo se queda en una franja muy baja mientras el panel está abierto (cifras en `medir.py propiedades`).
Con lo aplicado (el dibujo se desplaza solo para que la transición elegida siga a la vista) se puede trabajar, pero se ve poco del grafcet.

**Propuesta.** Por debajo de 560 px de alto, la paleta de operadores en una sola fila con desplazamiento horizontal y el panel
con ≈ 190 px; el dibujo conserva la mitad del alto. Por encima de 560 px, todo igual.

**Maqueta.** `capturas/maquetas/maqueta-p1-propiedades-cuarto.png` (el panel a 190 px, tal como lo dejaría el usuario con el
divisor). **Motivo de no hacerlo:** P-IMP-93 fija el crecimiento a ≈ 334 px y las pruebas de `alto_opciones` lo comprueban.

### P2. Panel de Entradas debajo del dibujo en pantalla partida (apartaría P-IMP-42 / 44 / 47 / 78)

**Problema.** En simulación a 960×1040 el panel derecho (ancho fijo de 218 px) deja ≈ 700 px al dibujo, y las entradas con nombres largos compiten
con las tablas por un panel muy estrecho.

**Propuesta.** Por debajo de 1000 px de ancho, las entradas en una banda horizontal bajo el dibujo (botones en fila, de 190 px cada uno, con el nombre
entero a la vista) y salidas y temporizadores en el panel de la derecha, que ya no reparte su alto con las entradas; la banda quita ≈ 50 px de alto al dibujo (se ve en la maqueta).

**Maqueta.** `capturas/maquetas/maqueta-p2-entradas-en-banda-partida.png` (el script saca las entradas de su cuadro y las pone en una banda bajo el dibujo).
**Motivo de no hacerlo:** las decisiones fijan paneles laterales de ancho fijo y plegables del todo; este cambio mueve las entradas de sitio.

### P3. Filas más altas en la vista de E/S para el panel táctil del portátil (apartaría P-IMP-63)

**Problema.** Los canales y las listas de variables miden 16 px de alto (`ALTO_FILA`): con el ratón se arrastra bien, con el panel táctil del portátil
acertar una fila de 16 px (y arrastrar una variable) exige más pulso. A 1366×768 se ven unas 31 filas de canales por columna antes de desplazarse (`capturas/despues/es-1366.png`); lo fijan `test_SESP14` y las demás pruebas de la vista de E/S.

**Lo que ya hace la rama.** A pantalla completa (≥ 1600×900) la vista de E/S sube a letra de 14 px y filas de 18 px (el alto de fila que fijan
las pruebas, 16 px, rige por debajo de ese tamaño: `ALTO_FILA`, `SESP06`, `SFIO33`).

**Propuesta.** Un modo «cómodo» (filas de 28 px con desplazamiento en la vista de E/S) elegible o automático cuando el sistema avise de un dispositivo señalador
de precisión baja, y asignación por clic (clic en la variable, clic en el canal) además del arrastre.

**Maqueta.** `capturas/maquetas/maqueta-p3-es-filas-28px-1366.png`: cada columna de canales con filas de 28 px; se ven unas 18 filas por columna antes de
desplazarse (hoy, unas 31). **Motivo de no hacerlo:** P-IMP-63 pide el estilo plano y compacto y las pruebas fijan alturas y capacidad.

### P4. Pestañas plegadas de 32 px (lo fijan las pruebas, no una decisión)

Las pestañas de los paneles plegados miden 26 px (`PanelPlegable.GROSOR_PESTANA`) y varias pruebas comprueban ese número
(`SPAN02`, `SPAN04`…). Para un objetivo de 32 px basta subir esa constante; las pruebas tendrían que cambiar. Es el único
control interactivo visible de menos de 32 px que deja `medir.py alturas` (se exceptúa a propósito).

### P7. «Modo aula»: escala de la interfaz elegida a mano (añade un ajuste)

**Lo que ya cubre la rama (sin añadir ningún ajuste ni entrada de menú).** A partir de **1600×900** (un proyector o un monitor a pantalla
completa: 1920×1080, 1600×900, 2560×1440…) la interfaz sube sola de escala (`estilo.escala_para`, `Ventana._aplicar_escala`): letra base de 14 px
(13 en la normal), letra pequeña de 13 (12), títulos de 19 (16), chip de 15 (13), cifras de 14 (12), controles de 40 px (34-36) y la **vista de
E/S** con letra de 14 px y filas de 18 px (12 y 16 en la normal). Los paneles laterales pasan de 218 a 264 px poco a poco entre 1366 y 1600 px
de ancho (y a 300 px a 1920), para que las tablas de la simulación lleven sus cuatro columnas sin que el dibujo dé un salto al cruzar el umbral. Cruzar el umbral
cuesta unos 100 ms (`arbitro_r3/umbral.py`) porque la vista de E/S y Propiedades se ponen al día cuando se muestran, no al cruzar.

**Lo que falta: el proyector de 1366×768 y de 1280×720 / 1280×800.** Esas resoluciones quedan por debajo del umbral (de ancho, de alto o de
los dos) y siguen en la escala normal: letra base de 13 px (12 en las tablas y en E/S) y controles de 34-36 px. Se leen peor desde el fondo
del aula que a 1920×1080, y la rama no puede subirlas sola por tamaño: a 1366×768 las pruebas fijan el dibujo antes de los 140 px de alto
(`minimumSizeHint().height() <= 564`) y los paneles laterales de 218 px (`SPAL05`, `SPAL06`), y la escala grande no cabe en ese presupuesto
(controles de 40 px: el dibujo empezaría hacia los 160 px; paneles de 264 px: ≈ 92 px menos de dibujo). Bajar el umbral a 1366×768 o a
1280×720 rompería esas pruebas; elegirla a mano, no.

**Propuesta.** Un ajuste «Tamaño de la interfaz» (normal / grande) en el menú Ajustes que fuerce la escala grande a cualquier tamaño y se
recuerde. Con ella, el profesorado que proyecta a 1366×768 o a 1280×720 la elige una vez; por tamaño nada cambia, y las pruebas, que no
la tocan, siguen en la normal. A 1366×768 con la escala grande forzada se pierden ≈ 20 px de alto y ≈ 92 px de ancho de dibujo; las tablas
caben, y la vista de E/S se desplaza (como hoy a 1366×768).

**Maqueta.** `capturas/maquetas/maqueta-p7-modo-aula-1366.png`: la ventana de 1366×768 con la escala grande forzada (letra, controles y paneles
laterales como a pantalla completa). Lo que cabe se mantiene; lo que no cabe cede espacio al dibujo.
**Motivo de no hacerlo:** añade una entrada de menú y un ajuste persistente (no es solo aspecto), y las pruebas de ajustes y de menús
recorren los menús con los textos actuales.

### P8. Verde de «verdadero» con 4,5:1 (`COL["true_text"]`; lo fija `SUIV02`)

**Problema.** El texto y las barras de lo que es verdadero en la simulación (`COL["true_text"]`) usan el mismo `#40d641` que
la etapa activa: sobre blanco son **1,92:1** (`contrastes.py`, última sección). **`test_SUIV02` exige
`COL["true_text"] == COL["active"]`**, y `test_remates_interfaz` exige que `tools/dibujo.css` lo refleje (`--truth`).

**Propuesta.** `COL["true_text"] = "#18771a"` (**5,69:1** sobre blanco) en `escritorio/diagrama.py` y `--truth:#18771a` en `tools/dibujo.css`
(tema claro), y en la prueba `SUIV02` comparar con `#18771a` en lugar de con `COL["active"]`. `COL["active"]` sigue en `#40d641`.
El cambio ya se probó en la rama (SCOL06 y SCOL08 pasaban) y se **revirtió** porque rompe `SUIV02`, una prueba de `main`.
**Motivo de no hacerlo:** el encargo prohíbe tocar `tests/`.

### P9. Borde de la etapa activa con 3:1 (apartaría P-IMP-77)

**Problema.** El borde y el relleno de la etapa activa son `#40d641` y `#e4f9e4`: el borde sobre blanco da 1,92:1, por debajo de los
3:1 de un elemento gráfico (WCAG 1.4.11). La etapa no depende solo del color (lleva un punto lleno y el texto «X1» en la tabla), pero con
mala luz de proyector el borde casi desaparece.

**Propuesta.** Borde de la etapa activa en `#157a35` (`estilo.SIMULACION`, 5,4:1) conservando el relleno `#e4f9e4`; el lima `#40d641` queda
para el trazo de transiciones y el texto. **Motivo de no hacerlo:** P-IMP-77 fija `#40d641` como color de la etapa activa y varias
pruebas lo comparan (`COL["active"]`).

### P10. Paneles laterales de ≈ 270 px a 1366 y menos (lo fija `SPAL05/06`)

**Problema.** Las pruebas de la paleta (`SPAL05`, `SPAL06`) fijan el ancho del panel izquierdo en 218 px a 1366×768 y a 1000×600. En 218 px las tablas de la
simulación no llevan las cuatro columnas con el nombre en sus 96 px: «Modo» cede su columna, «Estado» pasa bajo el nombre y «Papel» y «Tipo» van abreviados
(P12 y P13). A pantalla completa, donde las pruebas no miden 218, los paneles laterales ya miden 264 px (a 1600) y 300 px (a 1920).

**Lo que ya hace la rama.** La columna del nombre de las tablas (Variables y las de estado de la simulación) **manda y mide al menos ≈ 96 px a cualquier
tamaño** (`paneles.ReparteColumnas`): las demás columnas se abrevian o se esconden antes de que baje de ahí (ver P12 y P13) y el nombre, si no cabe en una
línea, se parte por los «_» en dos o tres. Entre 1366 y 1600 px de ancho los paneles laterales crecen poco a poco hasta 264 px y, entre 1600 y 1920, hasta
**300 px** (a pantalla completa sobra sitio: ahí las tablas llevan sus cuatro columnas con las palabras enteras).

**Propuesta.** `ANCHO_LATERAL = 270` desde 1280 px de ancho (con él, «Papel» y «Tipo» enteros y las cuatro columnas de las tablas de estado también a 1366).
**Motivo de no hacerlo a ≤ 1366:** `SPAL05` y `SPAL06` comparan con 218.

### P11. Tope proporcional de Propiedades en ventanas bajas (apartaría P-IMP-128 / 118 / 120 / 93)

**Propuesta.** Que el panel inferior no pase del 55 % del alto de la ventana (con un mínimo para ver una fila de campos): a 768 px,
≈ 420 px, que no cambia nada; a 520 px, ≈ 286 px en lugar de ≈ 334 px. Sin tocar la paleta de operadores: lo que no quepa se
desplaza dentro del panel. **Maqueta:** la de P1 (`maqueta-p1-propiedades-cuarto.png`) enseña el mismo efecto con 190 px.
**Motivo de no hacerlo:** el alto que pide la receptividad lo fija P-IMP-93 y la prueba `SEDI122` comprueba que no haya
controles cortados con ese alto.

### P12. «Papel» y «Tipo» abreviados en el panel de Variables de 218 px (apartamiento menor de P-IMP-42)

**Qué dice la decisión.** P-IMP-42: «Papel y Tipo se ven como texto y, al pulsar la celda, aparece su lista desplegable»; los paneles laterales (188–216 px)
«caben» con ello.

**Qué hace la rama (`variables.PanelVariables._planes`, con `paneles.ReparteColumnas`).** El texto entero donde cabe **con el nombre en sus 96 px**: a pantalla
completa (el panel mide 300 px a 1920×1080) «Entrada», «Salida», «Memoria» y «Booleana», «Entera», «Decimal (2)»; con los paneles de 218 px (1366×768 y menos,
pantalla partida, un cuarto de pantalla y media pantalla) se pintan abreviados: «Entr.», «Sal.», «Mem.» y «Bool.», «Entera», «Dec. 2». La celda conserva el
texto entero (lo leen las pruebas), lo lleva su ayuda («Booleana · clic para cambiarlo») y la línea de detalle, y la lista desplegable de la celda lo enseña
entero. El reparto lo decide el ancho de los paneles tal como se abren, no el arrastre del divisor: `test_SPAN03` fija que ensanchar el panel solo da ancho al
nombre y deja «Papel» y «Tipo» como estaban.

**Motivo.** El panel de 218 px deja 188–200 px a la tabla. Con «Papel» y «Tipo» enteros (≈ 58 + 73 px) el nombre se quedaba en ≈ 57 px, que es lo que hacía
ilegibles los nombres en la ronda 3 (38–50 px); con 96 px como mínimo para el nombre solo caben las abreviaturas (38 + 41 px). El árbitro de la ronda 4 lo anotó
(R2, observación). **Para que fueran enteros también a 1366:** paneles laterales de ≥ 262 px (ver P10: lo impiden `SPAL05` y `SPAL06`).

### P13. «Modo» y «Estado» ceden su columna al nombre en las tablas de estado de la simulación con el panel de 218 px

**Qué hace la rama (`ventana.Ventana._planes_vars` y `_planes_temp`).** Con 218 px (198–210 px útiles) caben el nombre en sus 96 px, «Valor» y «Contribuyen»;
**«Modo»** (continua / memoria) no tiene columna: su texto va en la ayuda de la celda y en la línea de detalle de la barra de estado («luz · salida continua · OFF»).
**«Estado»** de «Temporizadores» (parado / contando / vencido) se pinta **bajo el nombre**, con su color. A partir de ≈ 250 px útiles (a 1920×1080 el panel mide
300 px) las cuatro columnas, con «Modo» abreviado («cont.», «mem.») y, con ≈ 275 px o más, entero («continua», «memoria»).

**Motivo.** Con el nombre de ≥ 96 px, las otras tres columnas de «Salidas y variables» (≈ 54 + 43 + 71 px) no caben en 198 px; el árbitro de la ronda 4 propuso
precisamente abreviar «Modo» o llevar «Contribuyen» a la línea de detalle. Se prefirió quitar «Modo» (lo que menos dice: el alumnado ve el nombre, el valor y qué
etapa lleva la salida) y conservar «Contribuyen». **Alternativa:** un panel de simulación de ≥ 270 px también a 1366 (P10), o una línea secundaria bajo cada nombre con «continua · a.E1.motor.0».
