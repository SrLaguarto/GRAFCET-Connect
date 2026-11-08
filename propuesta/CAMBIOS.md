# Propuesta de diseño de GRAFCET Connect: cambios aplicados (rondas 1 y 2)

Solo aspecto, organización y usabilidad. No se toca `grafcet/`, ni el simulador, ni la semántica GRAFCET, ni rótulos de menús,
pestañas o textos que fijan las pruebas, ni `tests/`. Lo que se aparta de una decisión vigente o de una prueba queda en
`PROPUESTAS_PENDIENTES.md` y **no** está implementado. «Basado en IEC 60848»: no se declara conformidad.

**Cada cifra de este documento sale de un script de `propuesta/herramientas/`**: `medir.py` (franjas, alturas, letras, ancho,
teclado, contraste sobre los píxeles de la ventana, propiedades, literales), `contrastes.py` (53 parejas de tokens) y
`correr_pruebas.py` (suite por módulos). Las cifras de `medir.py` son las de la última pasada, a 1920×1080, 960×1040, 960×520,
1366×768, 640×800 y 640×520, con el ejemplo «temporizada» abierto para editar o en Play.

Criterios: C1 jerarquía, C2 legibilidad, C3 coherencia, C4 accesibilidad, C5 densidad y tamaño, C6 táctil, C7 estado de
simulación, C8 originalidad y acabado, C9 uso en clase.

## 1. Identidad y sistema de estilo (`escritorio/estilo.py`)

**Idea.** Tinta azul marino sobre papel gris frío; un acento petróleo para lo accionable (Play, selección, sección); verde
«máquina en marcha» reservado a la simulación; azul tinta para la edición. El dibujo (`diagrama.COL`) no se toca en colores:
negro sobre blanco, etapa activa `#40d641`, selección en azul, ámbar para avisos y rojo solo para errores.

| Token | Valor | Uso |
|---|---|---|
| `TINTA` / `TINTA_2` / `TINTA_3` | `#16263a` / `#4a5b6e` / `#5b6b7d` | texto principal, secundario, ayudas (15,3 / 7,0 / 5,5:1 sobre blanco) |
| `FONDO` / `SUPERFICIE` / `SUPERFICIE_2` | `#eef2f6` / `#fff` / `#f6f8fb` | ventana, tarjetas, cabeceras |
| `BORDE` / `BORDE_CONTROL` | `#cdd6e0` / `#7b8a9c` | separadores / borde de control (3,5:1) |
| `ACENTO` (+ `_OSCURO`, `_HOVER`, `_SUAVE`, `_BORDE`) | `#0b6e75` … `#cfeee6` | un acento por zona (blanco encima: 6,0:1) |
| `EDICION` / `SIMULACION` (+ `_SUAVE`, `_HOVER`) | `#27415f` / `#157a35` | chip, franja y fila de herramientas por modo (blanco encima: 10,5 / 5,4:1) |
| `PARPADEO` | `#2f8a91` | tono claro del parpadeo de «+ Añadir hoja» (blanco encima: 4,1:1) |
| `FOCO` / `FOCO_FUERTE` | `TINTA` / `#000000` | anillo discontinuo de 2 px; de 3 px en Play/Stop |
| Ritmo / radios | `E1..E6` = 4, 8, 12, 16, 24; `R_S/M/L` = 4, 8, 12 | espaciado y esquinas |
| Tipografía | `FUENTE` Segoe UI 13 px base, 12 secundaria, 14 sección, 16 título; `FUENTE_TITULO` Bahnschrift (reserva Segoe UI); `FUENTE_MONO` Consolas | Bahnschrift en títulos, rótulos de sección, chip y pestañas; Consolas en cifras (tiempos, valores, % de zoom) |
| Alturas | `ALTO_CONTROL` 36, `ALTO_BARRA` 34, `ALTO_CONTROL_COMPACTO` 32, `ALTO_FILA` 30 | objetivos táctiles |

`estilo.hoja_global()` genera la hoja de la ventana a partir de los tokens y conserva las cadenas que fijan las pruebas
(`width: 12px`, `dashed`, `QComboBox::drop-down`, `width:24px`, `desplegar.svg`, `#e36209`, `#1f6feb`, `#ffd2ad`, `#cfeee6`,
`#e8f5ef`). `estilo.icono()` dibuja los iconos con un único trazo de 1,75 px y extremos redondeados; `estilo.icono_grafcet()`,
`estilo.forma_luz()` y `ChipModo` (paneles.py) traen la notación a la interfaz: el cuadrado del chip es la etapa vacía al editar y la
etapa activa (rellena) al simular, y la franja de modo del borde del dibujo lleva los segmentos de una cadena de transiciones.
La rejilla de puntos del editor ya existía (`diagrama.py`, `#e3e6ec`) y no se ha tocado.

**Literales de color** (`medir.py literales`): 113 `#rrggbb`/`#rgb` en `escritorio/*.py`, de los que 35 son las definiciones de
`estilo.py`; en ficheros de interfaz quedan 9 (`entradas_salidas.py` 8: los tres tipos de variable, `#cbd2d5`/`#7c8a90` de la
barrita sin señal y `#e8f5ef` que fija una prueba; `variables.py` 1) y el resto son colores del documento (`diagrama`, `bloques`,
`edicion`, `anotaciones`, plantillas de plano). `ventana.py`, `paneles.py`, `acciones.py`, `leyenda.py`, `planos.py`, `propiedades.py`
y `navegacion.py`: 0. Ningún `font-size` escrito a mano baja de 12 px.

## 2. Cambios de la ronda 2 (los 13 puntos del árbitro)

| Punto | Qué | Cifra medida |
|---|---|---|
| 1 | `correr_pruebas.py`: un proceso por módulo con tiempo máximo (1800 s; 120 s las pruebas aparte), `SPAG18` aislada, resumen ran/fallos/errores/omitidas, raíz como argumento, paralelismo por defecto 2 | suite en la sección 5 |
| 2 | **Luz de E/S «abierta»** (P-IMP-126): fondo blanco, borde de 2 px de `TINTA`, negrita; conserva la forma por estado (círculo con marca, círculo vacío, rombo con «!») | `medir.py contraste`: abierta 15,3:1 con `abierta=True` |
| 3 | Tabla de salidas con las columnas **Variable · Modo · Valor · Contribuyen** y la de temporizadores **Dónde · Estado · Lleva · Preset**, las cuatro a la vista en el ancho de 218 px; el chip distingue los estados de `ESTADOS` | cabeceras completas a 1366 y a 640 (`capturas/despues/simulacion-*`) |
| 4 | Título del grafcet elidido (`EtiquetaElidida`, tope 380 px) y chip con su primera palabra entera como mínimo; ningún texto variable ensancha la ventana | mínimo de la ventana con un título de 113 caracteres y nombres de variable de 69 y 56: 598 px (1366) y 602 px (640×520), igual que con nombres cortos |
| 5 | La ventana llega a 640×520 sin cortar nada; los paneles laterales se pliegan solos (anchura < 1000: Variables al editar; altura < 560: las herramientas suben a la fila de las pestañas) y se respeta lo plegado a mano (`_manual_paneles`) | mínimo del ancho: 602 (editar), 593 (simular), 593 (E/S) a 640×520 |
| 6 | Tamaños pequeños: barra de zoom en la fila del título (`integrar_barra`), sin tapar el dibujo; simulación sin barras anidadas con la fila de temporizadores a la vista; PLANOS con «Más ▾» en una fila y «Margen» entero (el panel derecho y sus páginas llenan los 232 px); entradas de uno en uno si el nombre no cabe en media fila | 640×520: dibujo 348×343 desde y = 114; Propiedades abierto: panel 278 px, dibujo 91 px, la transición elegida queda a la vista (`medir.py propiedades`) |
| 7 | Teclado y foco: ninguna tabla atrapa Tab, botones `TabFocus` (el anillo solo sale al navegar con teclado), foco inicial en el dibujo sin anillo, sin recuadro nativo en la entrada con foco, Intro activa como Espacio, Play con anillo de 3 px | `medir.py teclado`: 17 paradas a 1366 y 12 a 640×520; 17 de 17 y 12 de 12 controles se activan con Espacio e Intro; anillo de Play 3,50:1 contra su relleno y 21,0:1 contra el fondo |
| 8 | Contrastes: «+ Añadir hoja» y barras de E/S ≥ 3:1 (el tono entero de las barras de tipo y el de la barrita sin señal se oscurecieron: `#d96a0c`, `#7c8a90`) | parpadeo 6,00:1 / 4,07:1 en píxeles; barra de canal 3,52:1 en píxeles; `contrastes.py` 53/53 |
| 9 | Nombres largos de entrada: se elide el nombre, nunca « = 0 / = 1» (`_BotonEntrada.paintEvent`) | `marcha = 1` se ve entero a 640×520 |
| 10 | Táctil: pulsación larga de ≈ 500 ms en una entrada abre el menú contextual; ayuda «Clic: pulsar · Ctrl+clic o mantener: enclavar»; los botones de la barra ganan texto cuando hay sitio; objetivos ≥ 32 px | ningún botón, desplegable o campo visible de menos de 32 px, salvo las pestañas plegadas de 26 px; categorías de bloques 32 px; «Fijar» 32 px; entrada de simulación 38 px |
| 11 | Nada por debajo de 12 px; «Salida N» nunca cortada | menor letra efectiva: 12 px (13 en PLANOS y a 640 px); «Salida 0…11» enteras a 640 (`es-minima`) |
| 12 | Colores, radios y tamaños de letra salen de `estilo.py`; una sola familia de verde para «activo»; ritmo de 4 y 8; el panel Elementos alineado con la barra de herramientas | literales: ver sección 1 |
| 13 | Identidad propia: Bahnschrift, Consolas para cifras, motivo derivado de la notación (cuadrado del chip, franja de modo), rejilla de puntos del editor (la de siempre) y estados hover, pulsado y deshabilitado en la hoja global | sección 1 |
| 14 | Este documento y sus scripts | — |

### Detalles que conviene saber

- **Alto de las franjas** (`medir.py franjas`): menú 25, fila de pestañas 34 (42 fusionada con las herramientas), herramientas 42. El
  dibujo empieza en y = 139 a 1366×768 y a 1920×1080 (el límite de la prueba es 140), 148 a 960 y 640 px con 1040 y 800 de alto, y
  114 con la fila fusionada (960×520 y 640×520).
- **Alto de los controles** (`medir.py alturas`): Play/Stop, Reiniciar y luz de E/S 34; zoom 35; «+ Entrada» y «Eliminar» 36.
- **Cabecera de la tabla** de simulación: la hoja de la tabla usa `padding: 4px -6px 4px 0px` en la sección (el margen propio de la
  cabecera ya separa el texto del borde izquierdo) para que «Contribuyen» quepa en 218 px; el texto largo de las celdas se elide con «…» y
  va entero en la ayuda de la celda.
- **En un cuarto de pantalla** el panel de simulación baja los títulos de caja de 24 a 20 px y quita el margen inferior, para que
  se vea la fila de temporizadores sin desplazarse; la fila de las pestañas junta barras con 4 px de separación.
- **El ancho lateral sigue en 218 px** (`SPAL05`/`SPAL06`, ver `PROPUESTAS_PENDIENTES.md` P10) y **el verde de «verdadero» del
  lienzo sigue en `#40d641`** (`SUIV02`, P8): son los dos puntos del encargo que no se pueden aplicar sin tocar pruebas.

## 3. Adaptación al tamaño, sin tocar nada

`Ventana._adaptar_tamano()` se ejecuta al mostrar y al redimensionar:

- **Por debajo de 1000 px de ancho**: el panel de Variables se pliega solo al editar; «Centrar todo» y «Centrar selección» pasan a icono y
  la barra de zoom sube a la cabecera. Por debajo de 760 px, «Reiniciar» es solo icono, la luz dice «E/S: …» y las pestañas se estrechan.
- **Por debajo de 560 px de alto**: las herramientas suben a la fila de las pestañas, se estrechan los márgenes y el dibujo gana una fila.
- **Lo plegado a mano se respeta**; solo lo plegado solo se vuelve a abrir al agrandar la ventana o al pulsar Play. Nada se guarda.
- No se cambia la hoja de estilo al cruzar un umbral (aplicarla a toda la ventana tarda cerca de un segundo).
- A 1366×768 y 1000×600 el comportamiento es el de siempre (las pruebas lo fijan).

## 4. Herramientas (`propuesta/herramientas/`)

- `capturar.py`: escenas `editor`, `propiedades`, `simulacion`, `planos`, `es` y `foco` a seis tamaños (los cuatro de siempre más
  `estrecha` 640×800 y `minima` 640×520) en `propuesta/capturas/despues/` (36 imágenes); `GRAFCET_RAIZ=<otra copia>` captura `main`
  con las mismas escenas. La maqueta de P1 sale con `--escenas maqueta-panel-bajo`.
- `medir.py`: las ocho mediciones de la cabecera, también a un tamaño o a un grupo (`medir.py teclado ancho --tamanos minima`).
- `contrastes.py`: 53 parejas de tokens, con el verde de «verdadero» actual y el propuesto aparte.
- `correr_pruebas.py`: suite por módulos (`--raiz`, `--paralelo`, `--modulos`, `--json`), sin escribir en el repositorio.

## 5. Pruebas

Suite por módulos (`correr_pruebas.py --paralelo 3`, plataforma `offscreen`, sobre una copia del árbol de trabajo con `tests/` sin
tocar): **ran 1079, fallos 3, errores 0, omitidas 7**, que es el mismo total que da una copia de `main`. Los tres fallos son los
que **también dan en `main`**: `test_SEDI266` (el alto de una etiqueta de la prueba), `test_SRCT01` (solo al correr su módulo
entero; pasa a solas) y `test_SFIO31` (tiempo de espera; pasa a solas). `test_SPAG18` (importar un PDF real) se cuelga igual
en `main` y en la rama, y la suite lo corre aparte con 120 s; `test_plantillas` omite 6 pruebas y `test_plantillas_tecnicas` 1,
como en `main`. Con mucha carga fallan además, por tiempo, `SMOD05`, `SFIO49` y `SFIO60`; por eso el paralelismo por defecto es 2.
`test_editor_escritorio` tarda ≈ 15 minutos (174 pruebas con ventana).
