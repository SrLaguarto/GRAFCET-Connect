# Propuestas pendientes (no implementadas)

Cada punto se aparta de una decisión vigente (`docs/04_Decisiones_de_implementacion.md`) o de lo que fijan las pruebas, así
que **no está en el código**. Se describe con su motivo y, cuando se puede, una maqueta o la cifra medida. Las cifras salen de
`propuesta/herramientas/medir.py` y `contrastes.py`; las maquetas, de
`python propuesta/herramientas/capturar.py --escenas maqueta-panel-bajo --tamanos cuarto --salida propuesta/capturas/maquetas`.

Qué ha cambiado desde la ronda 1: P5 (escala para proyector) pasa a ser «Modo aula» (P7) y se describe con su ajuste; P6 (zoom en
la fila del título) **ya está aplicado** por debajo de 1000 px de ancho o 560 px de alto (`Diagrama.integrar_barra`), y queda
pendiente solo a tamaño normal; P2 pierde urgencia (con las cuatro columnas a la vista en 218 px, las tablas caben); se añaden
P8 (verde de «verdadero»), P9 (borde de la etapa activa), P10 (ancho de los paneles laterales) y P11 (tope proporcional de
Propiedades).

## P1. Propiedades en un cuarto de pantalla: la paleta de operadores en una fila (apartaría P-IMP-128 / 118 / 120 / 93)

**Problema.** Con una transición seleccionada, el panel inferior crece hasta ≈ 334 px para ver entera la paleta de operadores de
la receptividad sin barra de desplazamiento. A 960×520 el dibujo se queda en una franja de ≈ 90 px de alto mientras el panel
está abierto; a 640×520, igual (cifras en `medir.py propiedades`). Con lo aplicado (el dibujo se desplaza solo para que la
transición elegida siga a la vista) se puede trabajar, pero se ve poco del grafcet.

**Propuesta.** Por debajo de 560 px de alto, la paleta de operadores en una sola fila con desplazamiento horizontal y el panel
con ≈ 190 px; el dibujo conserva la mitad del alto. Por encima de 560 px, todo igual.

**Maqueta.** `capturas/maquetas/maqueta-panel-bajo-cuarto.png` (el panel a 190 px, tal como lo dejaría el usuario con el
divisor). **Motivo de no hacerlo:** P-IMP-93 fija el crecimiento a ≈ 334 px y las pruebas de `alto_opciones` lo comprueban.

## P2. Panel de Entradas debajo del dibujo en pantalla partida (apartaría P-IMP-42 / 44 / 47 / 78)

**Problema.** En simulación a 960×1040 el panel derecho (ancho fijo de 218 px) deja ≈ 700 px al dibujo. Con las tablas de cuatro
columnas ya caben, así que es menos urgente que en la ronda 1.

**Propuesta.** Por debajo de 1000 px de ancho, las entradas en una banda horizontal bajo el dibujo (botones en fila de 36 px)
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
(`SPAN02`, `SPAN04`…). Para un objetivo táctil de 32 px basta subir esa constante; las pruebas tendrían que cambiar. Es el único
control interactivo visible de menos de 32 px que deja `medir.py alturas` (se exceptúa a propósito).

## P7. «Modo aula»: escala de la interfaz para proyector (añade un ajuste)

**Propuesta.** Un ajuste «Tamaño de la interfaz» (normal / grande) en el menú Ajustes, que sube el texto base a 15 px y el
secundario a 14 px, y los controles a 40 px. Para el proyector de un aula a 1366×768 basta «grande»; a partir de 1600 px de ancho
podría proponerse solo. **Motivo de no hacerlo:** añade una entrada de menú y un ajuste persistente (no es solo aspecto), y las
pruebas de ajuste (`SEDI122`, `SESP14`, la paleta de 218 px) miden con los tamaños actuales. La hoja global ya admite el cambio
(`estilo.hoja_global` recibe los tokens), pero quedan hojas locales con tamaños propios: habría que revisarlas una a una.

## P8. Verde de «verdadero» con 4,5:1 (`COL["true_text"]`; lo fija `SUIV02`)

**Problema.** El texto y las barras de lo que es verdadero en la simulación (`COL["true_text"]`) usan el mismo `#40d641` que
la etapa activa: sobre blanco son **1,92:1** (`contrastes.py`, última sección). **`test_SUIV02` exige
`COL["true_text"] == COL["active"]`**, y `test_remates_interfaz` exige que `tools/dibujo.css` lo refleje (`--truth`).

**Propuesta.** `COL["true_text"] = "#18771a"` (**5,69:1** sobre blanco) en `escritorio/diagrama.py` y `--truth:#18771a` en `tools/dibujo.css`
(tema claro), y en la prueba `SUIV02` comparar con `#18771a` en lugar de con `COL["active"]`. `COL["active"]` sigue en `#40d641`.
El cambio ya se probó en la rama (SCOL06 y SCOL08 pasaban) y se **revirtió** porque rompe `SUIV02`, una prueba de `main`.
**Motivo de no hacerlo:** el encargo prohíbe tocar `tests/`.

## P9. Borde de la etapa activa con 3:1 (apartaría P-IMP-77)

**Problema.** El borde y el relleno de la etapa activa son `#40d641` y `#e4f9e4`: el borde sobre blanco da 1,92:1, por debajo de los
3:1 de un elemento gráfico (WCAG 1.4.11). La etapa no depende solo del color (lleva un punto lleno y el texto «X1» en la tabla), pero con
mala luz de proyector el borde casi desaparece.

**Propuesta.** Borde de la etapa activa en `#157a35` (`estilo.SIMULACION`, 5,4:1) conservando el relleno `#e4f9e4`; el lima `#40d641` queda
para el trazo de transiciones y el texto. **Motivo de no hacerlo:** P-IMP-77 fija `#40d641` como color de la etapa activa y varias
pruebas lo comparan (`COL["active"]`).

## P10. Paneles laterales de 232 px (lo fija `SPAL05/06`)

**Problema.** Las pruebas de la paleta (`SPAL05`, `SPAL06`) fijan el ancho de los paneles laterales en 218 px. Con 232 px, la
tabla de Variables y la de Salidas llevarían los nombres y el modo sin elidir («salida continua» en una línea).

**Propuesta.** `ANCHO_LATERAL = 232`. Se probó en la rama y se revirtió al fallar `SPAL05` y `SPAL06`.

## P11. Tope proporcional de Propiedades en ventanas bajas (apartaría P-IMP-128 / 118 / 120 / 93)

**Propuesta.** Que el panel inferior no pase del 55 % del alto de la ventana (con un mínimo para ver una fila de campos): a 768 px,
≈ 420 px, que no cambia nada; a 520 px, ≈ 286 px en lugar de ≈ 334 px. Sin tocar la paleta de operadores: lo que no quepa se
desplaza dentro del panel. **Maqueta:** la de P1 (`maqueta-panel-bajo-cuarto.png`) enseña el mismo efecto con 190 px.
**Motivo de no hacerlo:** el alto que pide la receptividad lo fija P-IMP-93 y la prueba `SEDI122` comprueba que no haya
controles cortados con ese alto.
