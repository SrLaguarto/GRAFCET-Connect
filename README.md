# Núcleo GRAFCET — implementación parcial del paquete 0.1

Implementación de la **segunda IA** a partir de los doce documentos de `../Definición del proyecto/`, que no se modifican. Cubre los requisitos que no dependen de las cuestiones U pendientes. Lo que sí depende de una U no se aproxima: se detiene con un diagnóstico que nombra la cuestión.

> **No se declara conformidad** con IEC 60848:2013 ni con UNE-EN 60848:2022. Las capacidades I son provisionales (U-01); las que dependen de una U abierta están bloqueadas. Ver `docs/06_Declaracion_de_cobertura.md`.

## Uso

El núcleo requiere Python ≥ 3.12, sin dependencias externas. Solo el simulador de escritorio usa PySide6-Essentials (Qt 6, LGPL v3), y construir su `.exe` usa pyinstaller.

```bash
python tools/comprobar_paquete.py
```

```bash
python tools/ejecutar_pruebas.py
```

```bash
python tools/generar_trazabilidad.py
```

```bash
python tools/medir_presupuestos.py
```

El primer comando comprueba la parte automatizable de R-02: el paquete sigue siendo exactamente doce Markdown con las huellas registradas. El segundo ejecuta la batería y deja la evidencia en `docs/resultados_pruebas.json`. El tercero regenera la matriz y los documentos 02, 05 y 06. El cuarto hace una medición indicativa que no es aceptación (U-10).

### Simulador de escritorio (P-IMP-29)

Primera versión para Windows: simula los ejemplos y los modelos guardados con el dibujo de la norma. Tiene entradas
con un clic, tiempo real desde que se carga (como un autómata; los retardos se ven como temporizadores que cuentan:
«1,2 s / 3 s»), pausa y paso, evolución a evolución, traza, salidas, variables y todas las lecturas de interpretación
(menú «Ajustes»). Los paneles derecho e inferior se pliegan, y el dibujo admite zoom (P-IMP-30). «Abrir modelo» admite
un proyecto (su `manifest.json`) o un documento de modelo; «Guardar como proyecto» guarda el modelo en curso con su
dibujo. Con «Archivo > Nuevo grafcet», o «Editar» sobre un ejemplo o un modelo abierto, se pasa al editor de un secuencial: etapas, transiciones, enlaces, receptividades, deshacer, diagnósticos y recuperación (P-IMP-32).

- Desde el código: doble clic en «Abrir simulador.bat», o `python escritorio/simulador.py [modelo]`.
- Versión portable: «Construir ejecutable.bat» (o `python tools/construir_ejecutable.py`) deja el programa en
  `dist/GRAFCET/`. Esa carpeta entera es el programa: se copia donde se quiera y se abre `GRAFCET.exe`, sin instalar
  Python. `dist/` y `build/` no se versionan.

### Banco de pruebas y comparador de decisiones

Doble clic en «Probar banco de pruebas.bat» abre el banco en el navegador: ejemplos que se pueden ejecutar cambiando entradas y avanzando el tiempo. «Comparar decisiones.bat» abre el comparador (P-IMP-21): para cada cuestión abierta de la hoja 08, el mismo ejemplo se ejecuta una vez por lectura, lado a lado, con un guion de pasos. Se elige con «Esta es la buena» o «Dejar abierta», y la respuesta queda en `docs/decisiones.json`. También se puede abrir desde la consola:

```bash
python tools/banco_de_pruebas.py --abrir --comparar
```

## Documentos

| Documento | Contenido |
|---|---|
| [docs/01_Revision_de_coherencia.md](docs/01_Revision_de_coherencia.md) | Revisión del paquete: hallazgos H-01…H-22 con caso discriminante y tratamiento |
| [docs/02_Alcance_implementable.md](docs/02_Alcance_implementable.md) | Clasificación de los 82 requisitos frente a las U; propuesta para cerrar U-12 (generado) |
| [docs/03_Decision_tecnologica.md](docs/03_Decision_tecnologica.md) | Tecnología propuesta y su justificación |
| [docs/04_Decisiones_de_implementacion.md](docs/04_Decisiones_de_implementacion.md) | Decisiones P-IMP pendientes de aceptación y lecturas del paquete |
| [docs/05_Trazabilidad.md](docs/05_Trazabilidad.md) | Matriz requisito ↔ módulo ↔ caso ↔ resultado (generado) |
| [docs/06_Declaracion_de_cobertura.md](docs/06_Declaracion_de_cobertura.md) | Capacidades y su estado; materias excluidas (generado) |
| [docs/07_Medicion_indicativa.md](docs/07_Medicion_indicativa.md) | Medición de presupuestos en este equipo (no ratificada) |
| [docs/08_Cuestiones_abiertas_para_responder.md](docs/08_Cuestiones_abiertas_para_responder.md) | Hoja de trabajo con las cuestiones abiertas y las respuestas ya dadas |
| [docs/decisiones.json](docs/decisiones.json) | Respuestas guardadas desde el comparador (y las de la hoja 08) |

## Estructura

| Módulo | Responsabilidad (documento 10) | Requisitos principales |
|---|---|---|
| `grafcet/model.py` | Modelo y validación | MOD-01..07, ACT-04, JER-03, DAT-01, DAT-08 |
| `grafcet/expressions.py`, `values.py`, `timeutil.py` | Expresiones, tipos y tiempo exactos | EXP-01/02, TMP-01 |
| `grafcet/engine.py` | Interpretación, escenarios y reloj, sesión | SEM-*, EVT-01, TMP-02, ACT-01..03, SIM-* |
| `grafcet/hierarchy.py` | Macroetapas, encapsulación y forzado | JER-02..06 |
| `grafcet/profile.py`, `declaration.py` | Perfil, capacidades y bloqueos U | NOR-01/02, ALC-03 |
| `grafcet/scenario.py` | Lotes, entradas iniciales, parada | EVT-02, SIM-02 |
| `grafcet/trace.py` | Traza, cierre, digest | SIM-05, DAT-08 |
| `grafcet/persistence.py`, `canonical.py`, `ids.py` | Persistencia abierta, canónica y atómica | DAT-01..07, ROB-02, EDT-10, PLT-02 |
| `grafcet/editor.py` | Operaciones de edición sin interfaz | EDT-01..07, 09, 14; MOD-03, MOD-06 |
| `grafcet/builder.py`, `examples.py`, `view.py` | Constructor de modelos, ejemplos y vista común del banco, el comparador y el simulador (P-IMP-29) | SIM-02, SIM-03, DAT-02 |
| `escritorio/` | Simulador de escritorio con Qt (PySide6) y su dibujo; `tools/construir_ejecutable.py` hace el `.exe` portable | EDT-01, SIM-03, PLT-03 |
| `spec/clasificacion.py` | Clasificación de requisitos y tratamiento de casos | U-12 (propuesta) |
| `tools/banco_de_pruebas.py`, `comparador.html`, `decisiones.py`, `dibujo.js` | Banco de pruebas y comparador de decisiones (no es la interfaz del producto) | SEM-09, NOR-02 |
| `tests/` | Casos T-01…T-26 del documento 11 y suplementarios S-xx | — |


## Selección, salto y repetición (corrección del paso 3, P-IMP-33)

- **Selección:** arrastre desde la salida inferior de una etapa, o desde su enlace de salida, hasta un hueco lateral: se crea otra transición. De su salida, arrastre a una etapa o a otro hueco para crearla. Las ramas comparten la línea horizontal.
- **Salto de etapas:** arrastre desde la salida inferior de la etapa inicial del salto hasta un enlace que llegue a la etapa de destino. Se crea una transición lateral con receptividad pendiente. También funciona desde la entrada superior del destino hasta un enlace de salida del origen.
- **Repetición:** haga el mismo gesto hacia el enlace de entrada de una etapa anterior. También puede crear una transición lateral y unir su salida a esa etapa. El retorno lleva flecha ascendente automáticamente.
- **Unir una entrada:** desde el punto superior de una transición hasta un enlace que salga de una etapa se toma esa etapa como anterior; no se añade una segunda etapa a la transición del enlace.
- Arriba recibe y abajo emite, independientemente de dónde esté el otro elemento. Un clic en un enlace lo selecciona; arrastrarlo abre una rama. Cada conexión o creación se deshace con Ctrl+Z.
- Una transición con varias etapas anteriores o siguientes sigue siendo una simultaneidad, y usa la barra de la paleta.

El menú Ejemplos incluye «Selección de secuencia», «Salto de etapas» y «Repetición de secuencia» para probar cada caso por separado. El retorno se actualiza al mover los elementos; se guarda la topología y la posición, no una flecha decorativa independiente.

## Convención de commits

Cada commit traza requisito, cambio y prueba:

- Título: qué cambia, en una línea.
- Cuerpo: requisitos afectados (`REQ-…`), casos (`T-…`, `S-…`) y cuestiones o hallazgos (`U-…`, `H-…`, `P-IMP-…`) que motivan o limitan el cambio.
- Antes de confirmar, ejecutar `tools/ejecutar_pruebas.py` y `tools/generar_trazabilidad.py`, e incluir `docs/resultados_pruebas.json` y los documentos regenerados en el mismo commit, de modo que cada commit lleve su propia evidencia.
- Un cambio de oráculo nunca va en el mismo commit que el código que lo satisface. Debe aprobarlo antes el revisor correspondiente (documento 12).

## Procedencia (REQ-CR-02, REQ-CR-03, REQ-CR-04)

El núcleo se ha hecho solo con los doce documentos del paquete. El 25-10-2026, a petición del responsable de producto, se consultaron algunas imágenes de la norma aportadas por el responsable de producto (fuente IMG del documento 02, de uso autorizado) para ajustar la **notación gráfica del banco de pruebas**: P18-01, P19-04, P19-05, P20-02, P22-03, P26-01, P27-03, P28-02, P31-06, P32-02 y P32-04. El 27-10-2026, también a petición suya, se consultaron las de jerarquía: P40-02, P42-01, P42-02, P42-03, P42-04, P42-05, P43-01, P43-02, P44-01, P45-01, P47-01, P47-02 y P47-03. Solo se tomaron proporciones y convenciones de dibujo (P-IMP-17, P-IMP-24); no se copió ningún activo ni se abrió otro contenido de esa carpeta (ni el PDF ni la subcarpeta «Claude outputs»). No se han consultado otros productos, sus repositorios ni sus capturas. No se ha accedido a la red. Ningún oráculo procede de otro producto: las pruebas implementan los oráculos del documento 11 y, como variantes declaradas, los casos suplementarios S-xx. No se ha detectado contaminación. Como advierte el documento 02, no se afirma un aislamiento absoluto respecto al entrenamiento del modelo.

## Lo que falta

- Jerarquías: forzado, macroetapas y encapsulación se ejecutan (P-IMP-23) y sus interacciones están decididas (P-IMP-24 a P-IMP-26), salvo vaciar por forzado un recinto con su encapsulante activa, que se detiene.
- `elapsed(etapa)` en expresiones: no se ejecuta todavía (su valor con la etapa inactiva ya está decidido, 4.5 A).
- Siguen deteniéndose, sin preguntar todavía: eventos internos y de franqueamiento (U-03, caso T-11b), vencimientos simultáneos que dependen del orden (U-06) y vaciar por forzado un recinto con su encapsulante activa (U-08). Las cuestiones del comparador están todas respondidas.
- Editor gráfico, navegación jerárquica, exportación SVG/PDF y accesibilidad. El simulador de escritorio (P-IMP-29, P-IMP-32) ya crea, edita, guarda y simula un grafcet secuencial; ya tiene panel de variables (con memorias), acciones en las etapas y un programador por bloques para receptividades y condiciones (paso 4, P-IMP-38, rehecho en P-IMP-39); faltan comodidades del editor de ramas (paso 5) y jerarquías (paso 6); las selecciones, saltos y repeticiones ya se construyen con el ratón (P-IMP-33).
- Instalador y actualización, matriz de sistemas y medición en el equipo de referencia (U-10). Por ahora solo hay una versión portable para Windows, sin instalador.
- Ratificación del formato 0.1 (U-11) y cierre de las U normativas, que permitiría desbloquear capacidades.


## Ajustar flechas y realimentaciones (P-IMP-35 a P-IMP-37)

En modo Editar:

1. Por defecto solo lleva flecha un enlace que sube, y una por lazo, en el enlace más largo. Un enlace que baja no lleva flecha.
2. Arrastre una flecha directamente para desplazarla por su enlace, incluidos los tramos horizontales. Con el enlace seleccionado, «Mostrar flecha» la oculta o la muestra (también la de un enlace corto de un lazo, o la de unión donde llegan dos ramas). La flecha siempre sigue el sentido del enlace; para invertir un enlace, quítelo y vuelva a enlazar.
3. Seleccione el enlace de realimentación. Aparecen cuadrados: arrastre el del tramo vertical para llevar el retorno a izquierda o derecha; los de los tramos horizontales cambian sus alturas. El recorrido se recoloca a mano.
4. «Restablecer flecha automática» devuelve la flecha a su sitio.

Cada arrastre se deshace con Ctrl+Z y se rehace con Ctrl+Y. Los extremos del enlace siguen a las etapas/transiciones; los tramos fijados a mano conservan sus coordenadas. Todo se guarda con el proyecto y se mantiene al simular.

Un enlace siempre sale de una etapa y llega a ella con un tramo vertical (16), y a cada lado de una transición con otro algo mayor (24); si no caben, se acortan, y solo si los elementos están casi a la misma altura el enlace da un rodeo y sube con flecha. Una transición se agarra por su trazo para moverla; la rama solo sale de los puntos de unión, al final de sus tramos rectos. Al mover una etapa o una transición cerca de la vertical de un elemento enlazado (dos pasos de rejilla), se alinea con él y el enlace queda recto.

Los elementos de la paleta se arrastran con su figura, al zoom del dibujo. La paleta tiene también la ficha «Acción» (ver «Acciones» abajo). El panel izquierdo (paleta y propiedades) se pliega con su flecha en el borde del dibujo o con «Ver > Panel izquierdo» (Ctrl+L), como los otros.

## Variables, acciones y programador por bloques (paso 4, P-IMP-38; rehecho en P-IMP-39 y P-IMP-40)

En modo Editar:

- **Etapas nuevas** con solo el número: 0, 1, 2… En las receptividades, `X1` es la etapa 1.
- **Variables** (lado derecho): nombre, papel (entrada, salida o memoria), tipo (booleana, entera, decimal, duración), valor inicial (solo las entradas; las demás empiezan en 0), unidad y cuántos usos tiene. Las variables internas se llaman **memorias** en la interfaz; el archivo las sigue guardando con el papel `internal`. Cambiar el nombre actualiza las receptividades y acciones que la usan; una variable usada no se puede quitar.
- **Acciones:** botón derecho en una etapa, «Añadir acción…», o el botón «Añadir…» de su panel. También con la ficha «Acción» de la paleta (Elementos): se arrastra sobre una etapa y abre «Añadir acción» de esa etapa; soltada fuera de una etapa, avisa «Suelte la acción sobre una etapa». Como herramienta (Edición > Acción, Alt+5), un clic en una etapa abre el mismo diálogo; Esc cancela. Tipos: continua (con condición opcional), memorizada al activar, al desactivar o por evento (por ejemplo `CT := CT + 1` con `↑I02`). Si la variable no existe, el diálogo la crea (salida o memoria, booleana o entera). El diálogo muestra en «En la norma» cómo quedarán la condición o el evento antes de aceptar. Si la variable no vale para esa acción (una entrada como destino, o una variable no booleana en una acción continua), avisa; si se acepta otra vez, se guarda como borrador y la validación lo señala. Un clic en la caja de una acción la señala; doble clic la edita; el botón derecho la mueve o la quita.
- **Programador por bloques** (receptividades y condiciones), al estilo de Scratch:
  - **Dónde está:** en el panel inferior, pestaña «Bloques» (junto a Traza y Leyenda), solo en modo Editar. Al seleccionar una transición, esa pestaña se abre con su receptividad. Si el panel inferior está plegado, no se despliega solo: el botón «Bloques abajo ▾» del panel de la transición lo abre. En el panel izquierdo de la transición quedan la etiqueta, el texto, «Escrito», «Se dibuja» y «Crear las que faltan». El panel inferior ocupa el ancho del dibujo y del panel derecho, que quedan algo más bajos; el divisor se arrastra.
  - **Cómo se ve:** a la izquierda, una columna con las siete categorías, cada una con un círculo de su color y su nombre (Entradas, Salidas, Memorias, Etapas X, Operadores, Comparaciones y Tiempo); en el centro, los bloques de la categoría elegida; a la derecha, el área con la fórmula, dibujada en una línea si cabe. Debajo, el aviso, «⤢ Ampliar» y la papelera. Esta misma disposición aparece en el diálogo de acciones y en «⤢ Ampliar».
  - En Operadores, «y» (oliva) y «o» (fucsia) tienen colores distintos entre sí; el resto (no, flancos, constantes) es gris pizarra.
  - Las condiciones son bloques hexagonales: una variable booleana o una etapa, con un desplegable ▾ para elegir cuál.
  - «y» y «o» tienen dos huecos y se pueden anidar.
  - «no», «flanco de subida ↑» y «flanco de bajada ↓» envuelven a otro bloque.
  - «temporizar» envuelve a otro bloque y tiene dos tiempos, t1 y t2, como en la norma (`3s/X1`, `X1/2s`).
  - Comparación: [variable ▾][= ≠ < ≤ > ≥ ▾][valor], por ejemplo `CT ≥ 3`. Constantes 1 y 0.
  - Arrastrar un bloque a un hueco lo encaja. Soltar un bloque que envuelve (no, ↑, ↓ o temporizar) sobre otro lo envuelve. Arrastrarlo fuera o a la papelera lo quita y queda su hueco.
  - Un hueco sin llenar se muestra como «?»: la receptividad queda pendiente, con el texto con «?», y no se puede ejecutar.
  - El texto de debajo está sincronizado en los dos sentidos. Lo que se escribe pasa a bloques; si no se puede, se avisa y los bloques no cambian.
  - Ctrl+Z deshace cada cambio de bloques. En el diálogo de acciones, Ctrl+Z deshace lo del propio diálogo.
  - «⤢ Ampliar» abre el programador en una ventana más grande, sincronizada con el del panel.
- **Constantes:** 1 y 0 se escriben y se ven así. Cuando son una condición completa se guardan como `true` y `false`; en `CT = 1` o `n := 1` siguen siendo números.
- **X1 ambiguo:** si `X1` puede ser la etapa E1 o la etapa 1, se usa E1 y el programa avisa. Para la etapa 1 se escribe ``active(`1`)``.
- **Retardos** con paréntesis anidados, como `3s/(a AND (b OR c))`, ya se entienden.
- El panel izquierdo se puede estrechar: los rótulos pasan encima de los campos y los botones a la línea siguiente. Si el programador no cabe, se apila en vertical.
