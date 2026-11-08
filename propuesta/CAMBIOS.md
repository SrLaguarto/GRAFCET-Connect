# Propuesta de diseño de GRAFCET Connect: cambios aplicados (ronda 1)

Solo aspecto, organización y usabilidad. No se toca `grafcet/`, ni el simulador, ni la semántica GRAFCET, ni rótulos de menús,
pestañas o textos que fijan las pruebas, ni `tests/`. Todo lo que se aparta de una decisión vigente queda en
`PROPUESTAS_PENDIENTES.md` y **no** está implementado. Los números de línea son los del árbol de trabajo de esta ronda.

Criterios: C1 jerarquía, C2 legibilidad, C3 coherencia, C4 accesibilidad, C5 densidad y tamaño, C6 táctil, C7 estado de
simulación, C8 originalidad y acabado, C9 uso en clase.

## 1. Identidad y sistema de estilo (nuevo `escritorio/estilo.py`)

**Idea.** Tinta azul marino sobre papel gris frío; un único acento petróleo para lo accionable (Play, selección, sección);
verde «máquina en marcha» reservado a la simulación; azul tinta para la edición. El dibujo (`diagrama.COL`) no se toca: negro
sobre blanco, etapa activa `#40d641`, selección en azul, ámbar para avisos y rojo solo para errores (P-IMP-77, P-IMP-89).

| Token | Valor | Uso |
|---|---|---|
| `TINTA` / `TINTA_2` / `TINTA_3` | `#16263a` / `#4a5b6e` / `#5b6b7d` | texto principal, secundario, ayudas (15,3 / 7,0 / 4,9:1) |
| `FONDO` / `SUPERFICIE` / `SUPERFICIE_2` | `#eef2f6` / `#fff` / `#f6f8fb` | ventana, tarjetas, cabeceras |
| `BORDE` / `BORDE_CONTROL` | `#cdd6e0` / `#7b8a9c` | separadores / borde de control (3,5:1) |
| `ACENTO` (+ `_OSCURO`, `_HOVER`, `_SUAVE`, `_BORDE`) | `#0b6e75` … `#cfeee6` (el menta de lo activo) | un acento por zona (blanco encima: 6,0:1) |
| `EDICION` / `SIMULACION` (+ `SIMULACION_SUAVE`) | `#27415f` / `#157a35` (`#e3f4e8`) | chip, franja y fila de herramientas por modo |
| `OK`, `AVISO` (+ `_FONDO`), `ERROR` (+ `_FONDO`) | `#17803d`, `#8a5a00`, `#c62828` | estados (el rojo del dibujo, `#c62828`) |
| `FOCO` | `TINTA`, trazo discontinuo de 2 px | foco de teclado (13,6–15,3:1) |
| Ritmo / radios | `E1..E6` = 4, 8, 12, 16, 24; `R_S/M/L` = 4, 8, 12 | espaciado y esquinas |
| Tipografía | Segoe UI 13 px base, 12 secundaria, 14 sección, 16 título | todo el texto es ≥ 9 pt (12 px) |
| Alturas | `ALTO_CONTROL` 36 (campos y botones de panel), `ALTO_BARRA` 34 (barras de herramientas), `ALTO_CONTROL_COMPACTO` 32 (mínimo táctil: «Fijar», categorías, búsqueda), `ALTO_FILA` 30 | objetivos táctiles |

`estilo.hoja_global(compacto_alto)` genera la hoja de la ventana a partir de los tokens (`estilo.py:240`).
Conserva las cadenas que fijan las pruebas (`width: 12px`, `dashed`, `QComboBox::drop-down`, `width:24px`,
`desplegar.svg`). `estilo.icono()` (`estilo.py:336`) dibuja todos los iconos con un único trazo de 1,75 px, extremos
redondeados, rejilla de 24. `propuesta/herramientas/contrastes.py` comprueba 36 parejas (36/36 cumplen).

Migración de colores: la hoja global de `ventana.py` (antes líneas 904–961, 44 colores hex) y los colores de interfaz de
`ventana.py`, `paneles.py`, `propiedades.py`, `variables.py`, `entradas_salidas.py`, `planos.py`, `navegacion.py`, `bloques.py`
(solo la franja de categorías), `laminas.py` y `plantillas.py` (solo el tablero) pasan a tokens. Recuento de literales `#rrggbb` /
`#rgb` en `escritorio/*.py`: 279 → 114, de los que 32 son las definiciones de `estilo.py`; el resto son lienzo y documento
(`diagrama.COL`, colores de bloques y de acciones, plantillas, anotaciones) y los tipos de variable de E/S, que se dejan a
propósito. `ventana.py` pasa de 86 a 2 (las cadenas de la franja de PLANOS que no fijan las pruebas, pendientes de tokens) y
`entradas_salidas.py` de 72 a 8 (tipos de variable y el relleno `#e8f5ef` que fija una prueba). Los selectores de número (`QSpinBox`, `QDoubleSpinBox`) conservan su aspecto nativo, con sus flechas.

## 2. Cambios concretos

| Qué (widget) | Dónde | Antes → después | Por qué | Criterio |
|---|---|---|---|---|
| Hoja global | `estilo.py:240`, `ventana.py:881` | texto 12 px, controles de 22–26 px, 40+ hex dispersos → tokens, texto 13 px, controles de 34–36 px | sistema único | C3, C6, C8 |
| Botón **Play/Stop** (`botonPlay`) | `ventana.py:889`, regla en `estilo.py` | botón plano de 12 px → botón primario relleno (acento), icono blanco, 34 px; al simular pasa a «Stop» con relleno `TINTA` | jerarquía: el control principal | C1, C7, C8 |
| **Reiniciar** (`botonReiniciar`) | `ventana.py:890` | plano → secundario con borde | un solo primario | C1, C3 |
| Botones de `tb_edit` y `tb_vista` | `ventana.py:919`, `estilo.py` | iconos sueltos sin forma de botón → botones con borde de 34 px | se ve que se pueden pulsar | C6, C8 |
| **Chip de modo** (`estado`) | `ventana.py:663`, `_poner_chip` (`ventana.py:1447`) | «editando» / «estable» (pastilla de contorno) → «EDICIÓN», «EJEMPLO · SOLO LECTURA», «SIMULACIÓN EN CURSO» con relleno y mayúsculas; amarillo/rojo si inestable/detenida | el modo se lee, no solo se ve | C1, C4, C7 |
| **Franja de modo** (`banda_modo`) | `ventana.py:653`, `_AjustaBanda` (`ventana.py:331`) | no existía → 5 px en el borde de la tarjeta del dibujo (azul tinta / verde); no ocupa sitio | estado a 3 m | C7 |
| Fila de herramientas por modo | `ventana.py:940`, `_modo_visual` (`ventana.py:1458`) | blanca siempre → verde suave con filete verde de 3 px al simular | estado a 3 m | C7 |
| Entradas booleanas (`_BotonEntrada`) | `ventana.py:285`, `refrescar` (`ventana.py:2469`) | botón de 22 px, relleno inline azul → 40 px, borde de 2 px; activa: relleno `ACENTO_SUAVE`, borde de acento, punto lleno y «= 1» (anillo y «= 0» en reposo); candado/interruptor se mantienen | pulsadores grandes y legibles; estado por forma y texto | C6, C7, C4 |
| Tablas de simulación | `ventana.py:713`, `_tabla` (`ventana.py:1086`) | 4 columnas con barra horizontal inútil, «Cont» cortado → «Variable · Valor · Etapas» y «Dónde · Lleva · Preset» (las columnas «Modo» y «Estado» siguen en la tabla, ocultas, porque las pruebas leen sus celdas, y van en la ayuda de la fila; el estado se ve en el color de lo que lleva); filas de 30 px, sin barra horizontal | no se corta nada | C2, C5 |
| Ayuda bajo el título (`ayuda`) | `paneles.py:10` (`EtiquetaAyuda`), `ventana.py:669` | una línea cortada a media frase → hasta 2 líneas con «…» solo si aun así no cabe (texto entero en la ayuda emergente); misma fila que el título (lo fija una prueba) | C2 |
| Botones de zoom | `diagrama.py:1685`, `_BarraZoom` (`diagrama.py:1318`) | «Cent…todo» / «Cent…ción» → iconos + texto con el recuadro que se vuelve a medir; solo icono (con ayuda) por debajo de 1000 px | no se corta nada | C2, C5, C6 |
| Pestañas **GRAFCET / PLANOS** | `ventana.py:441`, `estilo.py` | pestañas grises redondeadas de 100 px mínimo (la activa, blanca) → pestañas de 32 px de alto con filete de acento de 3 px bajo la activa, sin flechas de desplazamiento | C3, C8 |
| **Luz de E/S** (`luz_es`) | `ventana.py:891`, `_luz_es` (`ventana.py:2703`) | punto gris/verde/rojo de 12 px → pastilla de 32 px con forma por estado: círculo con marca, círculo vacío, rombo con «!»; borde de 2 px en rojo si error y en acento si está abierta | el estado no depende del color | C4, C7 |
| Paneles plegables | `paneles.py:131`, `paneles.py:177` | flecha de 24 px (14 px) y pestaña con letra de 12 px → flecha de 32 px (16 px, negrita) y pestaña con letra de 13 px negrita, acento y foco visible (la pestaña sigue en 26 px: P4) | C6, C4 |
| Paleta de elementos | `propiedades.py:198` | rótulos de 11 px, cabecera plana → 12 px, cabeceras con filete de acento, hover y selección con tokens | C2, C3 |
| Panel inferior (Propiedades) | `propiedades.py:449`, `propiedades.py:518`, `estilo.campos_compactos` (`estilo.py:265`) | «Fijar» de 18 px sin forma → botón de 32 px con borde y relleno de acento al fijarlo; cabecera pegada (el primer campo sigue a ≤ 32 px, lo fija una prueba); campos y desplegables de 32 px en vez de 36 (con 36 la página de una etapa pediría más alto que la de una transición, y una prueba lo impide) | C6, C3 |
| Botones de la ficha de jerarquía | `propiedades.py:385` | botones de 26 px → 22 px con letra de 12 px (siguen en una fila de dos: una prueba exige que quepan en el panel) | duplican el botón derecho: excepción táctil documentada | C6 |
| Franja de categorías de bloques | `bloques.py:1701`, `bloques.py:1716` | botones de ≈ 25 px → 32 px, seleccionado con relleno y borde de acento, foco visible | C6, C4 |
| Panel Variables | `variables.py:137`, `variables.py:170` | filas de 20 px, letra de 11 px, «Ent…», botones de 26 px → filas de 30 px, 12 px, columnas con holgura, botones de 36 px en rejilla de 2×2 | C2, C6 |
| Búsqueda de elementos | `navegacion.py:61` | campo y botones ↑ ↓ × de ≈ 20–24 px → 32 px con borde (la fila de la cabecera mide lo mismo con o sin la búsqueda, lo fija una prueba) | C6 |
| Vista **E/S externas** | `entradas_salidas.py:46` (`ESTILO_PANEL`), `:952` | enlaces de texto «Conectar»/«Configuración» sobre fondo verdoso → botones (Conectar primario, Configuración secundario) de 32 px; títulos de 16/14 px; letra de 12 px (antes 11); cabecera conectada en verde con filete | C3, C6, C2 |
| **PLANOS** | `planos.py:50`, `:68`, `:146` | tres barras de texto plano en filas separadas, chip «editando plano» azul → barras con botones con borde que fluyen en 1–3 filas según el ancho, chip «EDICIÓN DE PLANO», acento y tablero de la hoja de la paleta | C3, C5, C8 |
| Franja de «Añadir selección a la hoja» | `ventana.py:449` | ámbar con botones de 25 px → mismo ámbar de tokens, botones de 34 px, foco visible; conserva `background:#27665c` y `background:white` | C3, C6 |

## 3. Adaptación al tamaño, sin tocar nada

`Ventana._adaptar_tamano()` (`ventana.py:1577`) se ejecuta al mostrar y al redimensionar:

- **Por debajo de 1000 px de ancho** (pantalla partida, 960×1040 y 960×520): el panel de Variables se pliega solo al editar
  (el dibujo gana ≈ 220 px); en simulación se mantiene el de Entradas. «Centrar todo» y «Centrar selección» pasan a icono.
- **Por debajo de 560 px de alto** (un cuarto de pantalla): las herramientas (Play, Reiniciar…) suben a la fila de las
  pestañas, entre ellas y la luz de la conexión (`_fusionar_filas`, `ventana.py:1466`), y los márgenes de la tarjeta del dibujo
  se estrechan: una fila menos, ≈ 38 px más para el dibujo. No se cambia la hoja de estilo al cruzar el umbral (aplicarla a toda
  la ventana tarda cerca de un segundo), así que los controles miden lo mismo a todos los tamaños.
- **Lo que el usuario plegó o desplegó a mano se respeta**: `_mostrar_panel(..., guardar=True)` marca el panel como manual
  (`_manual_paneles`); solo lo plegado solo por el modo compacto se vuelve a abrir al agrandar la ventana o al pulsar Play.
  Nada de esto se guarda en la configuración del usuario.
- A 1366×768 y 1000×600 el comportamiento es el de siempre (las pruebas lo fijan). El dibujo empieza en y ≈ 135 (límite de la
  prueba: 140); el mínimo de alto de la ventana no sube.

## 4. Accesibilidad (C4)

- Contraste: texto ≥ 4,5:1 y bordes de control, foco y marcas ≥ 3:1 (`contrastes.py`); lo deshabilitado queda exento.
- Foco: trazo discontinuo de 2 px en todos los controles, con relleno compensado para que no se mueva nada; blanco sobre los
  botones de acento. Escena `foco` en el script de capturas.
- El estado no va solo en color: chip con texto, luz con forma, entrada con icono y «= 1», etapa activa con relleno y punto.
- Todo se alcanza con teclado (sin cambios de orden); nombres accesibles nuevos: chip de modo, franja, vista, zoom.

## 5. Herramientas (en `propuesta/herramientas/`)

- `capturar.py`: capturas de las escenas `editor`, `propiedades`, `simulacion`, `planos`, `es` (y `foco`) a los 4 tamaños en
  `propuesta/capturas/despues/`. `GRAFCET_RAIZ=<otra copia>` captura `main` con las mismas escenas.
- `medir.py`: alto de cada franja y controles visibles de menos de 32 px. `contrastes.py`: parejas de color.
- `correr_pruebas.ps1`: suite completa o un módulo / nombre, sin escribir nada en el repositorio.

## 6. Límites conocidos

- Pestañas plegadas de 26 px (`GROSOR_PESTANA`), filas de 16 px del panel de E/S, y «Fijar»/categorías en 32 px: ver
  `PROPUESTAS_PENDIENTES.md` (P1–P5).
- A 960×520 el dibujo mide ≈ 680×360 px y el ajuste lo deja al 55 %; con una transición seleccionada y Propiedades abierto
  (decisión: ≈ 334 px) queda una franja de dibujo muy baja. Maqueta en `capturas/maquetas/`.

## 7. Pruebas

La suite (`python -m unittest discover -s tests -t tests`, plataforma `offscreen`) se ejecutó en 8 procesos en paralelo sobre una
copia del árbol de trabajo, con `tests/` sin tocar. Los únicos fallos son los que **también dan en una copia de `main`**
(se comprobó cada uno ejecutándolo allí): `test_SEDI266` (la letra de la prueba), `test_SFIO31` (tiempo de espera de la
conexión local), `test_SRCT01` (solo al correr el módulo entero), los seis errores de `test_plantillas` SPLT03–06 y SPLT14
(`pypdfium2` 4.x frente a la API que usa el código) y el cuelgue de `test_planos_integrados.SPAG18` (importar un PDF real,
también en `main`). `test_SMOD05` falló una vez con 8 procesos en paralelo y pasa a solas, en su módulo y en `main`:
es sensible al reparto de CPU (temporizador de recentrado de 200 ms).