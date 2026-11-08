# Propuestas pendientes (no implementadas) y propuestas descartadas

Cada punto se aparta de una decisión vigente (`docs/04_Decisiones_de_implementacion.md`) o de lo que fijan las pruebas, así
que **no está en el código**. Se describe con su motivo y, cuando se puede, una maqueta o la cifra medida. Las cifras salen de
`propuesta/herramientas/medir.py` y `contrastes.py`; **las maquetas son capturas de la ventana real, retocadas por script**
(`python propuesta/herramientas/maquetas.py`, salida en `propuesta/capturas/maquetas/`): el script recoloca controles o fuerza un
ajuste solo en la ventana que captura, sin tocar la interfaz.

«Táctil» significa aquí el **panel táctil del portátil** (*touchpad*): hay teclado, dos dedos desplazan, el pellizco acerca y el
toque con dos dedos es el clic derecho. No hay pantalla táctil que atender.

Qué ha cambiado en la ronda 3: P2, P3 y P7 llevan maqueta; P7 («Modo aula») queda cubierta en parte por la escala que cambia sola a
pantalla completa (ver abajo) y se reduce a lo que falta; se añade D1, la pulsación mantenida que se retiró (P-IMP-75).

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

**Propuesta.** Un modo «cómodo» (filas de 28 px con desplazamiento en la vista de E/S) elegible o automático cuando el sistema avise de un dispositivo señalador
de precisión baja, y asignación por clic (clic en la variable, clic en el canal) además del arrastre.

**Maqueta.** `capturas/maquetas/maqueta-p3-es-filas-28px-1366.png`: cada columna de canales con filas de 28 px; se ven unas 18 filas por columna antes de
desplazarse (hoy, unas 31). **Motivo de no hacerlo:** P-IMP-63 pide el estilo plano y compacto y las pruebas fijan alturas y capacidad.

### P4. Pestañas plegadas de 32 px (lo fijan las pruebas, no una decisión)

Las pestañas de los paneles plegados miden 26 px (`PanelPlegable.GROSOR_PESTANA`) y varias pruebas comprueban ese número
(`SPAN02`, `SPAN04`…). Para un objetivo de 32 px basta subir esa constante; las pruebas tendrían que cambiar. Es el único
control interactivo visible de menos de 32 px que deja `medir.py alturas` (se exceptúa a propósito).

### P7. «Modo aula»: escala de la interfaz elegida a mano (añade un ajuste)

**Lo que ya cubre la rama.** La letra base (14 px en lugar de 13), los títulos (19 px), el chip (15 px), las cifras (14 px) y los controles (40 px) **suben solos**
cuando la ventana mide 1600×900 o más, y vuelven al cruzar el umbral (`estilo.escala_para`, `Ventana._aplicar_escala`): un proyector a pantalla completa o un monitor grande
ya se leen desde el fondo del aula. No añade ningún ajuste ni entrada de menú. Los menús no cambian.

**Lo que falta.** Un proyector de **1366×768** (o un portátil de pantalla pequeña que se proyecta tal cual) queda por debajo del umbral y sigue en la escala normal. Hace falta un
ajuste «Tamaño de la interfaz» (normal / grande) en el menú Ajustes que fuerce la escala grande a cualquier tamaño.

**Maqueta.** `capturas/maquetas/maqueta-p7-modo-aula-1366.png`: la ventana de 1366×768 con la escala grande forzada. Lo que cabe se mantiene; lo que no cabe cede espacio al dibujo.
**Motivo de no hacerlo:** añade una entrada de menú y un ajuste persistente (no es solo aspecto), y las pruebas de ajuste y de menús recorren los menús con los textos actuales.

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

### P10. Paneles laterales de 232 px a 1366 y menos (lo fija `SPAL05/06`)

**Problema.** Las pruebas de la paleta (`SPAL05`, `SPAL06`) fijan el ancho del panel izquierdo en 218 px a 1366×768 y a 1000×600. En 218 px las tablas de la
simulación llevan las cuatro columnas con sus cabeceras enteras («Variable», «Modo», «Valor», «Contribuyen»), pero la columna del nombre queda en ≈ 50 px y el nombre se elide
por el medio (y sale entero en la línea de detalle de la barra de estado). A pantalla completa, donde las pruebas no miden 218, los paneles laterales ya miden 264 px.

**Propuesta.** `ANCHO_LATERAL = 232` (o 264 desde 1280 px de ancho). **Motivo de no hacerlo a ≤ 1366:** `SPAL05` y `SPAL06` comparan con 218.

### P11. Tope proporcional de Propiedades en ventanas bajas (apartaría P-IMP-128 / 118 / 120 / 93)

**Propuesta.** Que el panel inferior no pase del 55 % del alto de la ventana (con un mínimo para ver una fila de campos): a 768 px,
≈ 420 px, que no cambia nada; a 520 px, ≈ 286 px en lugar de ≈ 334 px. Sin tocar la paleta de operadores: lo que no quepa se
desplaza dentro del panel. **Maqueta:** la de P1 (`maqueta-p1-propiedades-cuarto.png`) enseña el mismo efecto con 190 px.
**Motivo de no hacerlo:** el alto que pide la receptividad lo fija P-IMP-93 y la prueba `SEDI122` comprueba que no haya
controles cortados con ese alto.
