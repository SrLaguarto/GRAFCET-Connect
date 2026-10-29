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

### Conectar con Factory I/O (P-IMP-50)

En Factory I/O seleccione **Modbus TCP/IP Server** y asigne sensores a entradas
discretas/input registers y actuadores a coils/holding registers. Confirme IP,
puerto, Slave ID y direcciones en su instalación; no se asignan automáticamente.

En GrafConnect, simule el modelo y abra **E/S externas**. Marque las variables,
elija área, dirección **base cero**, formato BOOL/INT16/UINT16 y escala. En señales
analógicas, `valor GRAFCET = registro / escala`; para 3,14 use escala 100 y registro
314. INT16 admite −32768…32767 y UINT16 0…65535, antes del escalado. Valores no
representables detienen la conexión; no hay redondeo ni saturación.

Use **Aplicar mapa**, **Guardar configuración…** y **Probar conexión** (sin escribir).
El mapa se guarda aparte en `conexion-factoryio.json` dentro del proyecto; también
puede cargarlo desde otro archivo. **Conectar** solicita cero y lee sensores; pulse
**Ejecutar** para comenzar. Pausa conserva estado y salidas. Un diagnóstico del
motor solicita cero; pérdida de red pausa sin garantizar el estado de los actuadores.
La reconexión es manual y exige volver a pulsar Ejecutar. Para editar o depurar,
desconecte; al cambiar modelo se descartan las respuestas pendientes.

El periodo de servicio es configurable (50 ms iniciales). El intervalo efectivo
incluye latencia y lecturas/escrituras por señal; pulsos breves pueden perderse.
El panel muestra la última lectura y la última escritura confirmada mientras está
conectado, no una confirmación física del actuador. La integración se prueba con
servidores locales simulados: **pendiente validar una escena real con Factory I/O**.

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
- Editor gráfico, navegación jerárquica, exportación SVG/PDF y accesibilidad. El simulador de escritorio (P-IMP-29, P-IMP-32) ya crea, edita, guarda y simula un grafcet secuencial; ya tiene panel de variables (con memorias), acciones en las etapas y un programador por bloques para receptividades y condiciones (paso 4, P-IMP-38, rehecho en P-IMP-39 y P-IMP-45); faltan comodidades del editor de ramas (paso 5) y jerarquías (paso 6); las selecciones, saltos y repeticiones ya se construyen con el ratón (P-IMP-33).
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

## Editar: paleta, panel de opciones y no solapar (P-IMP-45)

En modo Editar, la pantalla tiene tres zonas:

- **Paleta (panel izquierdo):** solo tiene la paleta, en una sola lista: la etapa, la transición, la simultaneidad (barra de doble trazo) y la acción (la ficha «Acción» es la continua; los otros tipos se eligen con el botón derecho, en «Tipo de acción»). Las fichas se colocan **arrastrándolas** al dibujo; un clic en una ficha solo muestra su ayuda. El panel izquierdo se pliega con su flecha en el borde del dibujo o con «Ver > Panel izquierdo» (Ctrl+L).
- **Dibujo (centro):** donde se ve y se toca el grafcet. Con el ratón se selecciona, se mueve y se enlaza; la rueda hace zoom.
- **Opciones (panel inferior):** ocupa todo el ancho de la ventana, debajo de los paneles laterales. Muestra la configuración de lo que está seleccionado. Sin selección, dice «Haga clic en un elemento del dibujo para ver y cambiar sus opciones». Se despliega y se pliega con su flecha; el divisor con el dibujo se arrastra, y el programa recuerda la altura que le dio en Editar y en Simular por separado.

### Dónde se cambia cada cosa

El panel de Opciones es uno solo, sin pestañas, y cambia según lo seleccionado:

- **Transición:** a la izquierda, la etiqueta, «Mostrar etiqueta» y el comentario. A la derecha, la receptividad, con el programador de bloques (ver «Bloques» más abajo).
- **Etapa:** etiqueta, tipo (normal o inicial), comentario y colocación de las acciones. Debajo, la lista de sus acciones con los botones «Añadir…», «Editar…», «Quitar», ◀ y ▶. En el panel de una acción, «Etapa X» solo indica a qué etapa pertenece (no lleva a ella).
- **Acción:** una frase que dice en lenguaje claro lo que hace (por ejemplo «Al activarse la etapa 2: CT := CT + 1.»), y debajo la variable, el valor (si es memorizada) y la condición o el evento con el programador de bloques (si es condicionada o por evento).
- **Enlace, barra de simultaneidad, varios elementos o nada:** lo que ya mostraba antes el panel para cada caso.

Cada cambio se aplica al momento y se deshace con Ctrl+Z, una vez por cambio. **No hay botón de Aceptar** ni ventana aparte para las acciones: el antiguo diálogo «Editar…» ya no existe. Doble clic en una acción, o «Editar…» en su menú, despliega el panel con esa acción; seleccionar un elemento no lo despliega.

Si una variable que se usa no existe, aparece en naranja y parpadea en el panel. Un valor a medias no se guarda hasta que está completo: la acción queda como borrador (con «?») hasta entonces.

### Traza y Leyenda

- **Traza:** en Simular, el panel inferior, que ocupa todo el ancho de la ventana, muestra la traza de la evolución. En Editar ya no hay pestaña de traza.
- **Leyenda:** está en el menú **Ayuda > Leyenda del dibujo**, en una ventana aparte que se puede dejar abierta mientras se trabaja.

### No se puede poner un elemento encima de otro

Ningún elemento (etapa, transición, barra de simultaneidad, acción o grupo de acciones) se puede soltar ni mover a mano encima de otro. Se mide con un margen de 8 unidades del dibujo alrededor de cada caja (no depende del zoom). Los comentarios no cuentan.

- **Desde la paleta:** si la caja cae sobre otro elemento, no se crea nada.
- **Al mover:** uno o varios elementos vuelven a su sitio.
- **Al añadir, pegar o unir acciones a una etapa, al editar una acción ya colocada o al cambiar la colocación de las acciones:** el programa comprueba que las acciones de la etapa (o del grupo) no queden encima de etapas, macroetapas, transiciones y sus textos, barras, otras acciones o grupos sueltos, ni crucen sus líneas. Si no caben, aparta hacia la derecha lo que estorba y lo que queda a su derecha, conservando sus posiciones relativas, hasta que quepan. Todo ello se deshace de una vez con Deshacer (Ctrl+Z). Si no puede (el estorbo está debajo de la etapa o hay que apartar demasiado), deja las acciones como se pusieron, encima, y avisa con el mensaje «Las acciones quedan encima de otro elemento: apártelo».
- **Al separar acciones** («Separar de la etapa» o «Eliminar el enlace»): no se aparta nada; cada acción queda donde estaba.
- **La colocación elegida no cambia sola:** si una colocación no cabe, la etapa conserva la que eligió y el programa aparta lo que estorba o avisa.
- **Durante el arrastre:** la caja se ve en rojo y el cursor es el de «prohibido». Al soltar, aparece el mensaje «No se puede poner encima de otro elemento».

Siguen funcionando el imán para pegar una acción a otra (con 16 píxeles) y unir una acción a una etapa; y una transición que se suelta sobre el enlace entre dos etapas se inserta en él, como antes.

Limitaciones: no se aparta lo que está en la columna de la etapa ni debajo de ella; una columna o una matriz de más de una fila bajo una etapa con transición suele quedar encima, con aviso. El desplazamiento mueve también lo que está a la derecha del corte, aunque no estorbe. Al estirar una barra de simultaneidad no se comprueban solapes. Los lazos de enlace no se tienen en cuenta al apartar lo que estorba. Una barra de alternativa no impide soltar un elemento encima de ella al arrastrarlo a mano.

## Variables, acciones y bloques (paso 4, P-IMP-38; rehecho en P-IMP-39, P-IMP-40, P-IMP-41, P-IMP-43, P-IMP-44 y P-IMP-45)

En modo Editar:

- **Etapas nuevas** con solo el número: 0, 1, 2… En las receptividades, `X1` es la etapa 1.
- **Variables** (lado derecho, al editar): tres columnas, Nombre, Papel y Tipo. El papel es entrada, salida o memoria; el tipo, booleana, entera o decimal con 2 decimales. Papel y Tipo se ven como texto y, al pulsar la celda, aparece su lista desplegable. Las variables internas se llaman **memorias** en la interfaz; el archivo las sigue guardando con el papel `internal`. El valor inicial y la unidad que tuviera un fichero se conservan en el modelo aunque la tabla no los muestre; las variables nuevas no los tienen. Los usos no se listan, pero una variable usada no se puede quitar, y el mensaje lo dice. Cambiar el nombre actualiza las receptividades y acciones que la usan. Un fichero antiguo con un decimal de 1 o 3 decimales, o de tipo duración, muestra su tipo («Decimal (3)», «Duración») y sigue funcionando; si se cambia su tipo, solo se elige entre los tres que se ofrecen.
- **Al crear, renombrar, quitar o cambiar el papel o el tipo de una variable**, la paleta de bloques, las listas de variables de las acciones y los desplegables del programador de valor se actualizan en el acto. Una variable nueva aparece enseguida donde se puede usar.
- **Nueva E, Nueva S, Nueva M** (encima de la tabla): añaden una fila sin nombre de entrada, salida o memoria, de tipo booleana (se cambia en su celda), con el cursor en el nombre; no propone ninguno. «Quitar» quita la variable elegida, si no se usa. Una variable no puede estar en el modelo sin nombre: la fila es solo de la interfaz hasta que se escribe un nombre válido, que la crea (una operación de deshacer). Un nombre no válido o repetido se rechaza con su mensaje y la fila sigue en blanco. Con una fila sin nombre no se simula ni se guarda («Guardar» o «Guardar como»): el aviso dice «Hay una variable sin nombre: escríbale un nombre o quítela» y la fila parpadea.
- **Errores en naranja:** el elemento con un error parpadea en naranja (unas tres veces en 1,5 s) y se centra en la vista si está fuera: una etapa, transición, barra, enlace, acción (del modelo o borrador) o fila de variable. Parpadea al rechazar una operación del editor que se refiere a un elemento; al pulsar «Simular» con errores de validación (cada elemento con error); al hacer clic en una línea de Diagnósticos, y al pulsar el aviso de un borrador de acción. Diagnósticos resume en una línea: «No se puede simular: N errores» o «El grafcet se puede simular».

### Acciones

Una acción es algo que la etapa hace mientras está activa, o cuando se activa o desactiva, según su tipo.

- **Tipos:** Continua (vale mientras la etapa está activa), Condicionada (continua que además exige una condición), Al activar (memorizada, flecha ↑), Al desactivar (memorizada, flecha ↓) y Por evento (memorizada con banderita, que asigna un valor cuando ocurre su evento). Cada tipo tiene su dibujo, que es el de la norma.
- **Cómo se crea:** arrastrando la ficha «Acción» (la continua) al dibujo, donde se suelta; con el botón derecho en una etapa, «Añadir acción…»; o con el botón «Añadir…» del panel de la etapa.
- **Acción suelta:** una ficha soltada en el dibujo crea una acción sin etapa y sin variable, con «?». No abre ningún diálogo. Una acción soltada sin tocar nada es continua. Se une a una etapa arrastrando desde su punto de unión de la izquierda hasta la etapa, o desde el de la derecha de la etapa hasta la acción.
- **Variable:** se elige en una lista con las que valen para esa acción. Una continua ofrece solo salidas y memorias booleanas. Una memorizada ofrece salidas y memorias de cualquier tipo. Las entradas nunca se ofrecen como destino. Las variables se crean solo en la tabla de variables (con «Nueva E», «Nueva S» o «Nueva M»); la lista de la acción no tiene «Nueva variable…». Sin variables, la lista dice «(sin variables: créelas en la tabla de variables)».
- **Valor** (solo en memorizadas), que se arma con bloques:
  - Si la variable es **booleana**, se elige la ficha «1» o la «0» (`:= 1` o `:= 0`).
  - Si es **numérica**, el valor puede ser un número (por ejemplo `5`), una variable numérica, o una operación «+», «−», «×» o «÷» entre dos huecos. Las operaciones se pueden anidar: `CT * 2 - 1` es una resta cuyo primer operando es «CT × 2».
  - Debajo se ve el texto del valor, de solo lectura. La casilla «Escribir a mano» lo deja editar; lo escrito pasa a bloques.
  - Un valor que el programa no entiende no se guarda, y el panel dice por qué.
- **Condición o evento:** se programan con bloques en el mismo panel. Una condicionada sin condición válida es un borrador: no se simula y se dibuja con «?». Elegir «Continua» quita la condición.
- **Aviso de variable:** si la variable no vale para esa acción (una entrada como destino, o una variable no booleana en una acción continua), el panel lo señala en naranja y parpadeante. Si la acción sigue incompleta, queda como borrador hasta que esté completa.
- **Borradores:** una acción suelta, o unida a una etapa pero sin variable (o sin lo que su tipo pide), no puede ser todavía una acción del modelo. Se guarda en el proyecto como borrador (`presentation.draftActions`, o `grupo` y `orden` si es un grupo suelto): no se simula, pero se guarda y entra en deshacer y rehacer. El panel Diagnósticos muestra un aviso por borrador, en gris y solo informativo. En cuanto tiene etapa y variable, pasa a ser una acción del modelo en la misma operación.
- **Unir y pegar:**
  - El punto de unión de la derecha de la etapa, en el centro de su lado derecho, se arrastra hasta una acción suelta; o se arrastra desde el punto de unión de la izquierda de la acción hasta la etapa. La acción pasa a ser de esa etapa, al final de sus acciones.
  - Una acción suelta que toca el lado derecho de otra (o el lado inferior, en colocación en columna) se pega a ella, con un imán de 16 píxeles. Varias acciones sueltas pegadas forman un grupo que se mueve junto y se une a una etapa de una vez.
- **Enlace de la etapa:** el trazo horizontal que une la etapa con sus acciones se selecciona con un clic. Supr, o botón derecho → «Eliminar el enlace», separa todas las acciones de la etapa: cada una queda suelta, donde estaba. «Separar de la etapa» separa solo la acción elegida; «Separar del grupo», en un grupo suelto, la saca del grupo; «Quitar» la borra.
- **Borrar una etapa:** borra también sus acciones y los borradores unidos a ella. Ctrl+Z lo restaura todo.
- **Tipo por botón derecho:** en una acción, «Tipo de acción» es un submenú con los cinco tipos, con sus dibujos, y marca el actual. Después van «Editar…», la separación, «Colocación de las acciones» (en un grupo suelto), «Mover a la izquierda» o «a la derecha» (en columna, «Mover arriba» o «Mover abajo») y «Quitar». Si al cambiar de tipo faltan datos, la acción queda con «?» en lo que falta y se abre el panel para completarlo.
- **Colocación de las acciones de una etapa:** con el botón derecho en la etapa, «Colocación de las acciones» ofrece cuatro formas, con la actual marcada: «En fila, pegadas» (por defecto), «En fila, separadas» (cada caja unida a una línea común que sale de la etapa), «En matriz de 2» (dos columnas, en orden de lectura: se llenan dos huecos y se cambia de fila; una barra común a la izquierda, que sale del enlace de la etapa) y «En columna» (una debajo de otra, unidas por una línea vertical). Cada caja se ensancha con su texto. La colocación se guarda en el proyecto, etapa por etapa, o por grupo suelto. Si la colocación elegida no cabe, se aparta lo que estorba (ver «No se puede poner un elemento encima de otro»); la colocación no cambia sola.
- **Acciones limitadas de ficheros antiguos:** una continua con límite de tiempo de un fichero anterior se sigue dibujando y simulando igual, con su límite como una condición más (`NOT 3s/X1`). En el menú y en el panel aparece como «Condicionada (con límite de tiempo)». Ese tipo ya no se ofrece; al editar su condición se conserva el límite, salvo que se quite.

### Bloques (programador de receptividades, condiciones y eventos)

El programador es de bloques, al estilo de Scratch: se arma una receptividad, una condición o un evento arrastrando piezas, en lugar de escribirlo.

- **Dónde está:** en el panel de Opciones, a la derecha de los datos de la transición o de la acción. Al seleccionar una transición, o hacer doble clic en ella, el panel muestra su receptividad. Al seleccionar una acción condicionada o por evento, muestra su condición o su evento, con un título como «Condición de la acción Q01 (etapa 0)».
- **Cómo se ve:** a la izquierda, una columna con siete carpetas, cada una con un círculo de su color y su nombre: Operadores, Entradas, Salidas, Etapas (X), Memorias, Comparaciones y Temporizadores. En el centro, las fichas de la carpeta elegida: **una ficha por cada elemento que existe**, en orden (las etapas por número, las variables por nombre). Si son muchas, la columna tiene desplazamiento vertical. Sin elementos, la carpeta muestra un bloque vacío. Cada ficha se arrastra al área con ese elemento ya elegido: por ejemplo, la ficha «X1» de Etapas (X) es la etapa 1. A la derecha, el área de trabajo, con la fórmula dibujada en una línea si cabe.
- **Debajo del área:** la fórmula en texto, «Escrito» (el texto que ha quedado guardado), «Se dibuja» (cómo se verá en el dibujo de la norma) y «Crear las que faltan» (declara como entradas booleanas las variables que se usan y no existen). En la última fila, el aviso, «⤢ Ampliar» (abre el programador en una ventana más grande, sincronizada) y la papelera.
- **Bloques ya puestos:** cada bloque del área tiene su ▾ para cambiar de elemento (otra etapa, otra variable).
- **Fórmula en texto:** es de solo lectura. La casilla «Escribir a mano» la deja editar; lo escrito pasa a bloques. Al desmarcarla vuelve a ser de solo lectura.
- **Operadores:** «y» (oliva) y «o» (fucsia) tienen colores distintos; «no», «flanco de subida ↑», «flanco de bajada ↓» y los demás son gris pizarra. Las condiciones son bloques hexagonales: una variable booleana o una etapa, con un ▾ para elegir cuál.
  - «y» y «o» tienen dos huecos y se pueden anidar. El «+» al final añade un hueco. Un hueco sobra cuando se saca un bloque de un «y» o un «o» de más de dos huecos; un hueco vacío sobrante se quita con botón derecho → «Quitar hueco», o seleccionándolo y pulsando Supr. Nunca bajan de dos. En el texto, varios operandos se escriben `a AND b AND c`, y los paréntesis salen donde la precedencia los exige y donde hay un bloque «( )».
  - «no», «↑» y «↓» envuelven a otro bloque. «temporizar» envuelve a otro bloque y tiene dos tiempos, t1 y t2, como en la norma (`3s/X1`, `X1/2s`).
  - «( )» tiene un hueco y sirve para agrupar, en todos los programadores (receptividad de transición, condición y evento de acción, y valor numérico). Los paréntesis escritos en el texto vuelven como bloques «( )» al pasar a bloques, incluso los que la precedencia exige; son solo agrupación y no cambian el significado. Las operaciones aritméticas encadenadas que se leen igual sin paréntesis se dibujan en línea.
  - Comparación: [variable ▾][= ≠ < ≤ > ≥ ▾][valor], por ejemplo `CT ≥ 3`. Constantes 1 y 0.
- **Cómo se mueven los bloques:** arrastrar un bloque a un hueco lo encaja. Soltar un bloque que envuelve (no, ↑, ↓ o temporizar) sobre otro lo envuelve. Arrastrarlo fuera o a la papelera lo quita y deja su hueco.
- **Hueco sin llenar:** se muestra como «?»; la receptividad queda pendiente y no se puede ejecutar.
- **Texto y bloques sincronizados:** lo que se escribe a mano pasa a bloques; si no se puede, el programa avisa y los bloques no cambian.
- **Deshacer:** Ctrl+Z deshace cada cambio, también en el panel.
- **Constantes:** 1 y 0 se escriben y se ven así. Cuando son una condición completa se guardan como `true` y `false`; en `CT = 1` o `n := 1` siguen siendo números.
- **X1 ambiguo:** si `X1` puede ser la etapa E1 o la etapa 1, se usa E1 y el programa avisa. Para la etapa 1 se escribe ``active(`1`)``.
- **Retardos** con paréntesis anidados, como `3s/(a AND (b OR c))`, ya se entienden.
- **Nombres no válidos:** las variables no pueden llamarse como una palabra de las fórmulas (NOT, AND, OR, true, false, rise, fall, active, activePartial, activeMacro, elapsed y delay, sin distinguir mayúsculas), ni tener espacios o símbolos (salvo «_»), ni empezar por algo que no sea letra o «_» (una cifra inicial vale si el nombre lleva además una letra: 1M1, 2S3, 10M), ni ser solo un número, ni parecer una duración (2s, 10ms, 3us, 0.5s), ni parecerse a una etapa (X seguida de cifras, como X1). En el texto de las fórmulas, esos nombres van entre acentos graves (`1M2`); bloques, «Se dibuja», la tabla y el dibujo los muestran sin acentos. Por ejemplo: «"AND" no puede ser nombre de variable: es una palabra de las fórmulas».

### Anchos de los paneles laterales

Al editar, el panel izquierdo (la paleta) y el derecho (Variables y Diagnósticos) tienen un ancho fijo de 212 píxeles, o más si su contenido lo necesita. Quedan arriba, a la altura del dibujo, encima del panel inferior. Se pliegan y se despliegan del todo, como antes. Al simular, el derecho conserva su ancho de siempre.

## Comentarios de etapas y transiciones (P-IMP-44)

En modo Editar, el panel de Opciones de una **etapa** y el de una **transición** tienen el campo «Comentario», de una línea. Vacío significa sin comentario. Cada cambio se deshace con Ctrl+Z.

- Se dibuja entre comillas tipográficas, en cursiva y gris: el de una transición, a la derecha de su receptividad (o de su etiqueta, si no tiene receptividad); el de una etapa, a la derecha de la etapa, o de su última acción si la tiene. Si es largo, se ajusta en varias líneas, con un ancho máximo de 190 px.
- No entra en la simulación, ni en la receptividad, ni en los diagnósticos. Se ve también en modo Simular, y `tools/dibujo.js` lo dibuja igual.
- Se guarda en `presentation.notes`, con `kind: "comment"`. Borrar el elemento borra su comentario, y Ctrl+Z lo devuelve.
- Las acciones no llevan comentario.
- Limitaciones: un comentario largo con elementos muy juntos puede pisar a un vecino (no se mueve nada solo); si el texto ya lleva comillas, salen dobles. Copiar y pegar elementos aún no existe. Más adelante se añadirá un elemento de texto de comentario que se pueda arrastrar.
