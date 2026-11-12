# Guía de maquetación de la interfaz

Reglas de colocación y medida de la interfaz de escritorio (`escritorio/`). Completan los tokens de `escritorio/estilo.py`
(colores, letra, altos y espaciado E1–E6 = 4, 8, 12, 16 y 24 px) y se comprueban solas en `tests/test_auditoria_maquetacion.py`
en las dos escalas (1366×768 y 2000×1250). Una excepción se anota en la prueba con su motivo; no se deja sin anotar.

Origen: decisión del responsable del 12-nov-2026, tras varias rondas de retoques sueltos (P-IMP-137 y P-IMP-138).

## 1. Cajas y paneles

- **M1. Nada se sale de su caja.** Todo control visible queda dentro del rectángulo de su padre, salvo el contenido de un área
  de desplazamiento, una ventana emergente o un elemento flotante declarado (zoom sobre el dibujo).
- **M2. Nada pisa nada.** Dos hermanos visibles no se solapan, salvo un elemento flotante declarado.
- **M3. El borde se ve entero.** El fondo de un hijo no tapa la línea de borde ni la esquina redondeada de su caja: entre el
  borde y el contenido queda al menos 1 px.
- **M4. Margen interior común.** Dentro de una caja con borde (Elementos, Variables, Propiedades, Hojas, Sensores, PLC,
  Actuadores, Configuración), el contenido empieza a E2 (8 px) del borde izquierdo y termina a E2 del derecho. Todas las cajas
  del mismo nivel usan el mismo margen.

## 2. Títulos de sección

- **T1. Título con cuadrado.** El cuadrado y el texto del título de una sección están enteros, con la sangría de M4 y el
  cuadrado centrado en vertical con el texto. Todos los títulos de sección del mismo tipo están a la misma distancia del borde.
- **T2. Título de una sección centrada.** Si el contenido principal de una sección va centrado (el marco del PLC), su título
  también va centrado sobre él.
- **T3. Hueco bajo el título.** Entre el título y lo primero de la sección quedan E2.

## 3. Controles

- **C1. Alto del token.** Botones, campos, desplegables y spinbox sueltos miden `ALTO_CONTROL` de su escala (±1 px), también
  con el anillo de foco. Dentro de tablas y listas miden lo que la fila.
- **C2. El texto cabe.** El texto de un botón, etiqueta, desplegable o celda se lee entero dentro de su caja. Si no puede
  caber, se acorta con «…» y la ayuda emergente lo da entero; nunca se corta a medias.
- **C3. Contenido centrado.** El icono y el texto de un botón van centrados en él (también los de ancho fijo, como Play).
- **C4. Botón ancho centrado.** Un botón que ocupa el ancho de su caja (p. ej. «+ Añadir hoja») deja el mismo margen a izquierda
  y derecha (M4), ±1 px.
- **C5. Ancho justo para cifras.** Un campo numérico mide lo que pide su mayor valor más las flechas (puerto, 5 cifras;
  esclavo, 3; dirección, 5), sin hueco sobrante.

## 4. Tablas

- **TB1. Columnas sin hueco.** Una columna mide lo que pide su contenido o su cabecera, lo que sea mayor. Un control dentro de
  una celda la ocupa entera. Solo la última columna (o la que se declare) se queda el sobrante.
- **TB2. Casillas centradas.** Una casilla de verificación va centrada en su columna.
- **TB3. Sin barra horizontal** a 2000×1250 en las tablas de Configuración; a 1366×768, si no cabe, se desplaza la tabla y
  no se corta ninguna columna.

## 5. Barras

- **B1. Separadores de zona.** Los grupos de una barra se separan con un separador; no hay grupos pegados sin él.
- **B2. Sin cortes al estrecharse.** Al estrechar la ventana se oculta antes el texto de un botón que el botón.

## 6. Revisión antes de entregar

Antes de dar por buena una tanda que toque la interfaz, se genera la hoja de contactos de todas las pantallas
(`tools/hoja_contactos.py`) en las dos escalas y se revisa ampliada. La prueba de auditoría pasa sin excepciones nuevas.
