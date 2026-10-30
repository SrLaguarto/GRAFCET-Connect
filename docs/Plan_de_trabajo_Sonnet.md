# Plan de trabajo para Sonnet: del simulador validado al editor y a Factory I/O

Plan preparado el 27-10-2026 a partir del commit `a4a6590` (P-IMP-29, primer simulador portable) y de la validación
del responsable de producto. Lo ejecuta Sonnet paso a paso. El responsable valida cada paso antes de pasar al
siguiente.

## 0. Cómo usar este plan (para el responsable)

1. Abre una sesión de Sonnet en la carpeta `implementacion` y pásale este fichero. Dile: «Lee
   `docs/Plan_de_trabajo_Sonnet.md`, aplica las reglas comunes y haz solo el paso N».
2. Un paso por sesión, o por encargo. Al terminar, Sonnet debe:
   - enseñarte una captura;
   - decirte qué probar en el `.exe` y esperar tu validación.
3. Cuando estés conforme, pídele el commit («Haz commit del paso N»). Sin esa orden, no confirma nada.
4. Si algo no te convence, díselo en la misma sesión antes de pasar al paso siguiente.
5. Si Sonnet encuentra una cuestión de semántica GRAFCET que no está decidida, debe preguntarte, no elegir.

Orden recomendado:

| Paso | Qué consigues |
|---|---|
| 1 | Correcciones de tu validación: Ajustes, tiempo como temporizadores, paneles plegables, zoom |
| 2 | El dibujo muestra nombres (no IDs internos): requisito para el editor |
| 3 | Editor I: crear, enlazar, mover, guardar y simular un grafcet secuencial propio |
| 4 | Editor II: variables, acciones y temporizaciones con ayuda de notación |
| 5 | Editor III: divergencias y convergencias en O y en Y, bucles, copiar y pegar, alinear |
| 6 | Editor IV (opcional): jerarquías (parciales, macroetapas, encapsulación, forzado) |
| 7 | Conexión con Factory I/O por Modbus TCP |
| 8 | Entrega: ejecutable, LÉEME y documentación al día |

El paso 7 solo necesita los pasos 1 a 4: con un grafcet propio sencillo ya se puede mover una escena de Factory
I/O. El 5 y el 6 pueden hacerse después.

---

## 1. Reglas comunes (para Sonnet, en todos los pasos)

### 1.1 Límites que no se negocian

- **No modifiques** los doce documentos del paquete en `../Definición del proyecto/`.
  `python tools/comprobar_paquete.py` debe seguir diciendo «superada».
- **No resuelvas cuestiones U por suposición.** Si una función nueva necesita decidir algo de semántica GRAFCET
  que no esté ya en `grafcet/profile.py` (`SEMANTIC_OPTIONS`) o en `docs/04`, para y pregunta al responsable. Si
  responde, regístralo:
  - como lectura por defecto, con su prueba;
  - en la hoja `docs/08`;
  - si es simulable, en el comparador (`tools/decisiones.py`).
- **Nunca declares conformidad** con IEC 60848 / UNE-EN 60848, ni en la interfaz, ni en la documentación, ni en
  los commits.
- **No uses otros productos como oráculo** (REQ-CR-04):
  - no mires editores GRAFCET o SFC, software de PLC ni sus capturas;
  - Factory I/O es solo la planta simulada que se conecta, nunca una referencia de cómo debe evolucionar un
    grafcet.
- **No cambies los oráculos de las pruebas** del documento 11 (`tests/test_t*.py`) para que coincidan con el
  código. Si una falla, corrige el código o pregunta.
- **No instales paquetes** sin permiso explícito del responsable en el chat. Ya están instalados
  PySide6-Essentials 6.12.0 y pyinstaller 6.22.3.
- **Sin red**, salvo la conexión local con Factory I/O del paso 7, que el usuario activa a mano.
- **Imágenes de la norma** (`C:\Users\Trabajo\Desktop\Proyecto GRAFCET Chatgpt\Norma UNE Grafcet\Imagenes UNE
  GRAFCET`):
  - solo las que cita el README, en «Procedencia»;
  - solo para tomar proporciones y convenciones de dibujo;
  - nunca copies un activo;
  - no abras el PDF, la carpeta «Claude outputs» ni nada más de «Proyecto GRAFCET Chatgpt».
- **Commits:**
  - solo cuando el responsable lo pida, y nunca `git push`;
  - el autor ya está configurado en git; no lo cambies;
  - termina el mensaje con la línea de coautoría que indique tu entorno.

### 1.2 Arquitectura que hay que respetar

| Carpeta | Qué es | Regla |
|---|---|---|
| `grafcet/` | Núcleo: modelo, validación, expresiones, motor, persistencia, editor sin interfaz, vista común | Solo biblioteca estándar. **Nunca importa Qt.** Toda la semántica vive en `grafcet/engine.py` |
| `grafcet/view.py` | `Vista`: estructura que se dibuja y estado observado, común al banco, al comparador y al simulador | Si cambias lo que muestra, comprueba también el banco web |
| `grafcet/editor.py` | Operaciones de edición con deshacer y rehacer, transacciones y diagnósticos | El editor gráfico **usa estas operaciones**; no toca el documento a mano |
| `escritorio/` | Aplicación Qt (PySide6): `ventana.py`, `diagrama.py`, `simulador.py` | La interfaz no aproxima nada: muestra lo que decide el motor |
| `tools/` | Banco web, comparador de decisiones, generadores de trazabilidad, construcción del `.exe` | `dibujo.js` y `escritorio/diagrama.py` dibujan igual: si cambias uno, cambia el otro |
| `tests/` | `test_t*.py` (oráculos del documento 11) y `test_s*.py` (suplementarios S-xx) | Cada cambio lleva su prueba |
| `docs/` | 01–08, `decisiones.json`, `resultados_pruebas.json` y este plan | 02, 05 y 06 se generan |

### 1.3 Comprobaciones antes de dar un paso por terminado

```bash
python tools/ejecutar_pruebas.py
```

```bash
python tools/generar_trazabilidad.py
```

```bash
python tools/comprobar_paquete.py
```

Captura de la ventana sin abrirla en pantalla, para enseñarla al responsable:

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts python escritorio/simulador.py --ejemplo temporizada --captura captura.png
```

Para generar el ejecutable:

```bash
python tools/construir_ejecutable.py
```

Después, prueba `dist/GRAFCET/GRAFCET.exe` con la opción `--captura` y deja que el responsable lo pruebe a mano.

### 1.4 Convenciones

- **Idioma:** la interfaz, los mensajes y los documentos van en español. En `grafcet/` los módulos tienen nombre en
  inglés y los textos en español. En `escritorio/` y `tools/`, los identificadores van en español. Imita el
  código de alrededor: densidad de comentarios, nombres y estilo.
- **Pruebas nuevas:** `test_S<GRUPO><nn>_<descripcion>`. Por ejemplo, `test_SAPP08_…` para la aplicación,
  `test_SEDI01_…` para el editor o `test_SFIO01_…` para Factory I/O. La primera línea del docstring cita los
  `REQ-…` que cubre. Las pruebas Qt usan la plataforma `offscreen` y se omiten si falta PySide6 (mira
  `tests/test_simulador_escritorio.py`).
- **Decisiones de producto:** cada decisión nueva (no semántica) es una fila `P-IMP-30`, `P-IMP-31`… en
  `docs/04_Decisiones_de_implementacion.md`, con los campos hallazgo o motivo, decisión, dónde y cómo revertir. Se
  insertan delante de la última añadida, como las anteriores.
- **Requisitos:** si un requisito avanza, actualiza su nota en `spec/clasificacion.py` (por ejemplo, REQ-EDT-01,
  REQ-EDT-02, REQ-EDT-03, REQ-EDT-08, REQ-EDT-12, REQ-EDT-13 o REQ-JER-07). Cambia su categoría solo si de verdad
  queda cubierto, y regenera la trazabilidad.
- **Commit** (formato de los anteriores; ver `git log`):
  - Título: qué cambia, en una línea.
  - Cuerpo, en secciones «Cambios», «Documentación» y «Pruebas». Cita los `REQ-…`, `S-…`, `P-IMP-…` y `U-…`
    afectados, el número de pruebas y el resumen de la matriz.
- **Entorno Windows:**
  - Python 3.12 de Microsoft Store.
  - PyInstaller se ejecuta con `python -m PyInstaller`, a través de `tools/construir_ejecutable.py`.
  - Los heredocs largos en bash fallan a veces: escribe los scripts en ficheros.
  - El banco web lee sus páginas al arrancar: reinícialo tras cambiar `dibujo.js`.

---

## Paso 1 — Correcciones de la validación del simulador

**Objetivo.** Aplicar lo que pidió el responsable al probar el primer `.exe`:

> «El tiempo lógico deja de contármelo debajo, haz que el tiempo sea un temporizador que se active con la variable
> que proceda en el temporizador. En lecturas de interpretación, quita la opción "No se elige" y quítalo de la vista
> derecha: eso son opciones dentro de ajustes (arriba, entre Simulación y Ayuda). Una flechita para colapsar del todo
> y expandir los paneles derechos y de abajo. Que deje hacer zoom en el área de trabajo.»

Las entradas le parecen bien: no se tocan.

**Ficheros:** `escritorio/ventana.py`, `escritorio/diagrama.py`, `grafcet/view.py` (solo si hace falta exponer datos)
y `tests/test_simulador_escritorio.py`.

### 1a. Menú «Ajustes»

- Añade el menú «Ajustes» entre «Simulación» y «Ayuda», con «Lecturas de interpretación…»: el diálogo `Lecturas`
  que ya existe.
- Quita del panel derecho la caja «Lecturas de interpretación», con su combo U-03 y su nota. El aviso de lecturas
  distintas de las decididas pasa a la barra de estado: un texto discreto, en rojo, que diga cuáles son.
- En el diálogo, **no muestres el valor `"detener"`** («Detener con D-SEM-PENDIENTE: no se elige»).
  - Ninguna lectura tiene hoy «detener» por defecto, así que ocultarlo no cambia nada.
  - **No lo quites de `SEMANTIC_OPTIONS`**: lo usan el motor y las pruebas, y es lo que detiene los casos aún
    abiertos (U-03 en eventos internos, U-06 en vencimientos simultáneos, U-08).
  - Si en el futuro alguna lectura tuviera «detener» por defecto, muéstrala como texto fijo: «Sin decidir: se
    detiene».

### 1b. El tiempo como temporizadores

**Interpretación** (confírmala con el responsable al enseñar la captura):

- El tiempo deja de manejarse a mano: la simulación corre en tiempo real nada más cargar, como un autómata.
- Cada temporización (`3s/X1`, `p/2s`…) aparece como un **temporizador**. Arranca cuando se cumple su condición
  (la variable o etapa que lleva dentro, como hace ya el motor) y muestra cuánto lleva y cuánto le falta.

Tareas:

- Quita la caja «Tiempo lógico»: el reloj grande, los botones +0,1 / +0,5 / +1 / +3 s y el texto explicativo.
- Añade una barra de herramientas con:
  - «▶ Ejecutar / ❚❚ Pausa»: tiempo real, activo por defecto al cargar;
  - «Paso»: una evolución;
  - «Reiniciar».
  - El reloj τ va en pequeño, en la barra de estado.
- Mueve «Avanzar el tiempo…» al menú «Simulación» como herramienta de depuración: un diálogo con la duración. Así
  las pruebas y los casos de vencimientos exactos siguen siendo posibles.
- En el dibujo, junto a cada receptividad o acción con temporización, pinta su estado:
  - Muestra «1,2 s / 3 s» mientras cuenta y «3 s ✓» cuando ha vencido. En reposo, nada.
  - Los datos ya están en `Vista.state()["temporal"]`: la clave es el ID de la expresión, y trae `intervalStart`,
    `deadline`, `phase` y `effectiveValue`.
  - Para colocarlo, `Vista.model` debe incluir el `conditionRef` de cada transición, y el de cada acción condicionada
    o por evento.
- Renombra la tabla «Condiciones temporales» a «Temporizadores», con las columnas «Dónde» (transición o acción),
  «Estado» (parado / contando / vencido), «Lleva» y «Preset».
- El tiempo real sigue siendo la extensión E del documento 08: el tiempo lógico avanza con el reloj, y los
  vencimientos siguen siendo exactos al µs.
- Si el motor se detiene (error o recorrido pendiente), el tiempo real se pausa solo, como ahora.

### 1c. Paneles plegables

- Pon una flechita (▸ / ◂ y ▾ / ▴) en el borde del panel derecho y otra en el de la traza/leyenda, para plegarlos
  del todo y volver a desplegarlos.
- Guarda el estado con `QSettings` y repítelo en «Ver > Panel derecho / Panel inferior», con atajos de teclado.

### 1d. Zoom en el área de trabajo

- Añade controles visibles sobre el dibujo: «−», porcentaje, «+» y «Ajustar».
- Que funcione la rueda con Ctrl, Ctrl+= y Ctrl+−.
- El zoom elegido **se mantiene al refrescar**: ahora cada refresco vuelve a ajustar. Solo «Ajustar» y el doble
  clic vuelven a encajar el dibujo.

### Aceptación

- Pruebas nuevas (`S-APP08…`):
  - el menú Ajustes existe y su diálogo no ofrece «detener»;
  - el panel derecho ya no tiene lecturas;
  - al cargar un ejemplo, el tiempo real está activo;
  - pausa y paso funcionan;
  - en «temporizada», tras activar E1 y avanzar 1 s, el dibujo y la tabla muestran «1 s / 3 s»;
  - plegar y desplegar paneles;
  - el zoom se conserva tras un refresco.
- Siguen pasando las 141 pruebas.
- Captura de «temporizada» con el temporizador contando, y nuevo `.exe`.
- Registra P-IMP-30.

---

## Paso 2 — El dibujo muestra nombres, no IDs internos

**Por qué.** Los ejemplos usan ID = etiqueta, pero el editor del núcleo crea IDs internos (`g-2dd5…`).
`grafcet/view.norm` escribe `m["reference"]`, que es un ID. Con un modelo hecho en el editor, el dibujo pondría
«X<sub>g-2dd5…</sub>» en vez de «X<sub>E1</sub>».

**Tareas**

- En `Vista`, crea un mapa de ID a nombre visible:
  - variable → `name`;
  - etapa → `label`;
  - parcial → `label`;
  - macroetapa → `label`.
- Haz que `norm` lo use (por ejemplo, con un parámetro `names`). Úsalo también en:
  - los textos de las acciones (`target := …`, la variable de una acción continua);
  - las órdenes de forzado (etapas destino);
  - las tablas de variables y temporizadores;
  - la traza, que hoy imprime IDs en situaciones y franqueos (`describe`).
- Las transiciones muestran su `label` si lo tienen; si no, su ID. En el paso 3 el editor dará a cada transición
  una etiqueta corta (`t1`, `t2`…).
- Haz lo mismo en el banco web (`dibujo.js` ya recibe textos ya formateados desde `Vista`).

**Aceptación**

- Un modelo creado con `grafcet.editor.Editor` (etapas «E0», «E1», variable «marcha», receptividad «marcha») se
  dibuja con «E0», «E1» y «marcha», y su traza dice «S = {E1}».
- Los ejemplos se ven igual que antes (compáralo con capturas).
- Prueba `S-APP…`. Sin decisiones nuevas, no hace falta P-IMP. Si la necesitas, regístrala.

---

## Paso 3 — Editor I: crear un grafcet secuencial propio

**Objetivo.** El responsable dibuja un grafcet sencillo (etapas, transiciones, enlaces), lo guarda, lo vuelve a abrir
y lo simula.

**Base.** `grafcet/editor.py` ya tiene operaciones con transacciones, deshacer y rehacer. **Úsalas; no reimplementes la
edición en la interfaz.**

Operaciones:

- `add_step(partial, label, initial, kind, at)` y `add_transition(partial, condition, pre, post, at)`;
- `connect(src, dst)`: etapa→transición o transición→etapa. Lo demás queda como borrador `D-ALTERNANCIA`;
- `set_condition`, `rename`, `move`, `align`, `distribute`;
- `plan_delete` / `delete`, `copy` / `plan_paste` / `paste`;
- `undo` / `redo`, `validate`, `usages`, `find`.

La presentación (posiciones) vive en `editor.presentation`. Guarda con `persistence.new_project` + `add_document`
(modelo y presentación) + `save_project`, y abre con `open_model`, como hace ya «Guardar como proyecto».

**Tareas**

- Modos «Editar» y «Simular», en una barra o con pestañas.
  - Al pasar a Simular, se valida. Si no compila, se muestran los diagnósticos y no se simula.
  - Al volver a Editar, la simulación se descarta.
  - Si el modelo cambia, la siguiente simulación es una ejecución nueva (REQ-EDT-14).
- «Archivo > Nuevo grafcet»: modelo vacío con el parcial raíz (mira cómo crea `M` el parcial `g`).
- Paleta o barra: «Etapa», «Etapa inicial», «Transición», «Enlace», «Seleccionar», «Borrar».
  - **Colocar:** clic en el lienzo. Usa una rejilla de 20 px, o la que encaje con las proporciones de
    `diagrama.py`.
  - **Enlazar:** arrastra de una etapa a una transición o de una transición a una etapa. Un enlace entre dos
    elementos del mismo tipo queda como borrador, con su diagnóstico.
  - **Atajo:** con una etapa seleccionada, «Añadir debajo» crea transición + etapa enlazadas. Es lo más rápido para
    un secuencial.
  - **Mover:** arrastrar. Cada arrastre es una sola operación de deshacer.
  - **Editar:** doble clic en una etapa cambia su etiqueta; en una transición, su receptividad, que se analiza con el
    analizador del núcleo. El error se ve en el momento, con su diagnóstico y corrección.
  - **Borrar** con Supr: usa `plan_delete` y avisa de lo que se arrastra.
- Panel «Diagnósticos»: la lista de `validate()`. Un clic selecciona y centra el elemento (REQ-EDT-09).
- Deshacer y rehacer con Ctrl+Z y Ctrl+Y. Al cerrar o abrir otro con cambios sin guardar, se pregunta (REQ-EDT-01).
- La recuperación automática cada 30 s ya existe en `persistence.Recovery` (REQ-EDT-10): conéctala.
- El dibujo del editor es el mismo `diagrama.py`, con selección, tiradores y el elemento en cuestión resaltado.
  No hagas un segundo dibujo.

**Aceptación**

- Pruebas Qt `S-EDI…`: crear E0 (inicial) → t1 «marcha» → E1 → t2 «paro» → vuelta a E0; guardar; abrir; simular;
  pulsar «marcha» y llegar a E1; deshacer y rehacer; borrar con aviso; receptividad mal escrita con diagnóstico.
- Captura del editor con ese grafcet.
- El responsable crea y simula su propio secuencial con el `.exe`.
- P-IMP-31 (decisiones de interacción: rejilla, atajos, modos). Notas de REQ-EDT-01, REQ-EDT-02, REQ-EDT-03 y
  REQ-EDT-09.

---

## Paso 4 — Editor II: variables, acciones y temporizaciones

**Objetivo.** Que el grafcet propio haga algo: entradas, salidas, contadores y temporizadores.

**Tareas**

- **Panel «Variables»**, el diccionario (REQ-EDT-07): nombre, papel (entrada, salida, interna), tipo (bool, int,
  decimal con escala, duración), unidad y valor inicial.
  - Usa `add_variable`, `change_variable` y `usages`.
  - Recuerda la regla 1.5 de la hoja 08: lo que no es entrada empieza en 0. `_check_initial` ya la aplica.
- **Acciones en una etapa** (menú contextual «Añadir acción»):
  - continua, con condición opcional: `add_continuous_action`;
  - memorizada al activar, al desactivar o por evento: `add_stored_action`.
  - Dibujo como el actual: trazo con condición, flecha ↑ o ↓, banderita de evento.
- **Ayuda de notación.** El usuario piensa en la notación de la norma (`↑I02`, `3s/X1`, `p/2s`, `[CT ≥ 3]`, la
  barra de negación). El núcleo usa su propia sintaxis de texto: `rise(I02)`, `delay(3 s, active(E1), 0 s)`,
  `NOT p`, `CT >= 3`. Hazlo así:
  - Al editar una receptividad o una condición, ofrece botones (↑, ↓, negación, ·, +, comparaciones, «Temporizar…»)
    que escriben la sintaxis del núcleo.
  - Muestra al lado una vista previa en notación de la norma con `view.norm`.
  - «Temporizar…» abre un asistente con t1, la condición y t2, y genera `delay(t1, cond, t2)`. Los 0 s se omiten al
    dibujar, por la respuesta 4.4 revisada.
  - Si quieres aceptar también la escritura directa `3s/X1`, haz un traductor aparte, en `grafcet/` y con pruebas,
    que solo convierta a la sintaxis del núcleo. **No cambies el analizador ni la semántica.**
- La tabla «Temporizadores» del paso 1 también vale en el modo Simular del editor.

**Aceptación**

- Prueba `S-EDI…`: reproducir con el editor el ejemplo «contador-flanco» del responsable y comprobar que simula
  igual que el ejemplo.
  - I00 lleva a 1 e I01 vuelve a 0.
  - Mientras 1 está activa, cada subida de I02 suma 1 a CT, y mantener I02 pulsada no vuelve a contar.
  - Q00 y Q01 están encendidas en 1.
- Prueba de un retardo `3s/X1` hecho con el asistente.
- El responsable rehace en el editor sus dos ejemplos del contador.
- P-IMP-32 si hay decisiones (por ejemplo, el traductor de notación).

---

## Paso 5 — Editor III: estructuras y comodidad

**Tareas**

- **Divergencia y convergencia en O:** varias transiciones desde una etapa, o hacia una. Herramienta «Añadir rama
  alternativa».
- **Divergencia y convergencia en Y:** una transición con varias etapas siguientes o anteriores. El dibujo ya pinta
  el doble trazo. Herramienta «Añadir rama simultánea».
- **Saltos y bucles:** enlace hacia arriba, que ya se dibuja con flecha. Comprueba que el enlace se ve bien al
  arrastrar etapas.
- Copiar, cortar y pegar con IDs nuevos (`copy`, `plan_paste`, `paste`), preguntando por las referencias externas
  (REQ-EDT-04).
- Alinear y distribuir la selección (`align`, `distribute`); selección por rectángulo; buscar por nombre (`find`,
  REQ-EDT-06).
- Renombrar una variable o etapa actualiza sus usos (`rename`, REQ-EDT-06).
- Teclado y accesibilidad básicos (REQ-EDT-13): todo lo de la paleta, con atajos; foco visible; textos alternativos.
- Diagramas grandes (REQ-EDT-12): vista general en miniatura y filtros. Opcional en este paso.

**Aceptación:** pruebas `S-EDI…` de cada herramienta, capturas de un grafcet con ramas O e Y, y validación del
responsable.

---

## Paso 6 — Editor IV (opcional): jerarquías

El motor ya ejecuta macroetapas, encapsulación y forzado (P-IMP-23 a P-IMP-27), pero `grafcet/editor.py` **no tiene
operaciones** para crearlos. Solo `add_partial` y el borrado los conocen.

**Estado.** Hecho en el núcleo y en la interfaz (P-IMP-61 y P-IMP-62; pruebas SEDI139–SEDI158 y SEDI170–SEDI192):

- Núcleo: `add_macro`, `add_enclosure` (con `new_enclosure` para crear el recinto con su parcial), `add_force`, y lo
  necesario para editarlas y borrarlas (`macro_info`, `set_step_kind`, `set_activation`, `set_force`, `delete_force`,
  `partial_roles`), con borrado, nombres y pegado coherentes con la jerarquía.
- Reglas: 8.1 C se aplica en `add_enclosure` (D-FORMATO si el parcial declara otro dueño). La regla 7.7 A (etapas
  iniciales dentro de una expansión) se comprobó en la verificación: el editor la acepta sin diagnóstico y la etapa
  arranca activa, como decide P-IMP-24.
- Interfaz: fichas Macroetapa y Encapsulante; recintos; enlace de activación; «Abrir expansión», doble clic y «Ir a…»;
  «Forzar un parcial…» con sus cuatro formas, y órdenes G{…} en rectángulo doble con «Editar orden de forzado…» y
  «Quitar orden de forzado».
- Aceptación: los ejemplos «macroetapa», «encapsulacion» y «forzado» reconstruidos con el editor simulan igual que los
  del constructor (SEDI140 a SEDI142; el de «forzado» también solo con gestos, SEDI190). U-08 sigue deteniéndose (SEDI148).

**Ronda posterior** (pruebas del responsable con Factory I/O; P-IMP-63 a P-IMP-65). Supera a lo descrito arriba en dos puntos: la paleta pide cuatro filas con la ficha «Forzado» (P-IMP-62, punto 7, superado por P-IMP-65: en una ventana baja se encoge a tres filas con barra de desplazamiento), y el temporizador ya no muestra «lleva / preset» a la derecha, sino el tiempo transcurrido encima de la duración (P-IMP-30, superado por P-IMP-64; el «1,2 s / 3 s» de la línea ≈183 del Paso 1 queda superado). Además, esta ronda añade: orden de forzado desde la paleta (sin órdenes sueltas), Supr sobre acciones y órdenes (y sobre variables en la tabla de variables), mover varios, equidistanciar alturas, la corrección de `Editor.bar_link` con barras mixtas, zoom anclado al puntero con «Centrar todo», y el panel de E/S externas con su botón conmutador. Pruebas: SEDI200–219, SEDI269 y SEDI271 (`tests/test_dibujo_vista.py`); SEDI220–235, SEDI240–259, SEDI267 y SEDI272 (`tests/test_editor_cadenas.py`); SEDI260–266, SEDI268 y SEDI270 (`tests/test_editor_escritorio.py`); SFIO33–36 (`tests/test_modbus_panel.py` y `tests/test_modbus_ciclo.py`) y SAPP10 (`tests/test_simulador_escritorio.py`). Sin decidir: los puntos (a) a (d) de P-IMP-65 y la multiselección de la tabla de variables (hoy de selección simple); ninguna cuestión U se cierra. Los atajos de teclado de las acciones nuevas siguen pendientes, salvo Supr.

**Segunda ronda** (pruebas del responsable, 30-10-2026; P-IMP-66 y P-IMP-67). Supera a lo descrito arriba en tres puntos: «Abrir expansión», «Ir a la macroetapa» e «Ir a la encapsulante» (P-IMP-61 y P-IMP-62) pasan a «Encuadrar la expansión», «Encuadrar la macroetapa», «Encuadrar el recinto» o «los recintos» y «Encuadrar la encapsulante» (24 px de margen, zoom máximo 1,6, parpadeo; no tocan el modelo ni el historial); los trazos discontinuos de macroetapa-expansión y encapsulante-recinto solo se ven con «Mostrar dependencias», apagado por defecto (P-IMP-24 en cuanto a su visibilidad); y la paleta pasa a ocho fichas, con «Grafcet parcial» séptima y «Forzado» octava, en cuatro filas que se encogen a tres (P-IMP-65). Con esto queda hecho el primer punto de la lista de abajo: un parcial suelto se crea con la ficha «Grafcet parcial» o con «Nuevo grafcet parcial aquí»; se renombra, es destino de «Forzado» y Supr lo borra con aviso. Queda abierto el nombre de la encapsulante: el responsable pide que vuelva a ir a caballo de la línea superior del marco de su recinto, como en la norma; se revisará en la ronda siguiente.

La segunda ronda cambia también la conexión con Factory I/O (Paso 7): Pausa pone a cero las coils y holding asignadas y deja el GRAFCET sin estado hasta un nuevo Play, que empieza siempre desde la situación inicial; Conectar pone a cero antes de la primera lectura, y Desconectar escribe el cero antes de cerrar el TCP. P-IMP-67 registra la decisión del responsable para Pausa y Desconectar, que cubre en parte lo que pregunta el apartado 7d (qué se escribe al pausar o desconectar). El aviso por red caída aparece al desconectar, pero no al cerrar la ventana: eso queda pendiente de decidir. El panel E/S se actualiza con el modelo y, con la conexión viva, avisa de las variables nuevas hasta desconectar.

Pruebas: SEDI273, SEDI280–285 y SEDI290–294 (`tests/test_editor_cadenas.py`); SEDI274–276, SEDI286–289 y SEDI296 (`tests/test_dibujo_vista.py`; no hay SEDI295); SFIO37–58 (`tests/test_modbus_panel.py`, `tests/test_modbus_ciclo.py` y `tests/test_modbus_configuracion.py`), y los ajustes de SAPP09 y SAPP17 (`tests/test_simulador_escritorio.py`). Esta nota no ejecutó las pruebas.

**Queda pendiente:**

- Crear un parcial suelto (que no sea recinto ni expansión) con gestos del editor.
- Atajos de teclado para las acciones nuevas (hoy, solo ratón y menús).
- La vuelta completa de la navegación («ir y volver», REQ-EDT-08).
- Comprobar los arrastres con ratón real en pantalla (las pruebas usan gestos programáticos).
- Limitaciones anotadas en P-IMP-62: renombrar un parcial no reescribe los textos «G.x»; el texto de los borradores de
  acción no tiene ámbito de parcial.

**Tareas**

- Añade al núcleo, con transacción y deshacer:
  - `add_macro(partial, label, at)`, que crea la expansión con sus etapas de entrada y salida;
  - `add_enclosure(owner_step, partial, activation_steps)`;
  - `add_force(source_step, target_partial, kind, steps)`;
  - lo necesario para editarlas y borrarlas.
  Con pruebas del núcleo, sin Qt.
- Respeta las reglas ya decididas: 7.7 A, y 8.1 C (un parcial dentro de otro sin encapsulante no compila).
- En la interfaz:
  - crear parciales;
  - «Abrir expansión» de una macroetapa, como navegación jerárquica (REQ-EDT-08, REQ-JER-07);
  - recintos con su encapsulante;
  - órdenes de forzado `G{…}` en rectángulo doble.
  Todo con el dibujo que ya existe.
- Lo que sigue abierto (U-08: vaciar por forzado un recinto con su encapsulante activa) debe seguir deteniéndose.

**Aceptación:** reproducir con el editor los ejemplos «macroetapa», «encapsulacion» y «forzado», y comprobar que
simulan igual.

---

## Paso 7 — Conexión con Factory I/O

**Objetivo.** Que un grafcet hecho en el editor gobierne una escena de Factory I/O: los sensores son entradas y los
actuadores, salidas.

### 7.0 Antes de programar: comprobaciones con el responsable

- ¿Qué versión y edición de Factory I/O tiene?
- ¿Aparece el driver **«Modbus TCP/IP Server»** en *File > Drivers*?
  - Con ese driver, Factory I/O hace de servidor Modbus y nuestro simulador se conecta como **cliente**.
  - Comprueba en su pantalla de configuración:
    - la IP (normalmente 127.0.0.1);
    - el puerto (normalmente 502);
    - el *Slave ID*;
    - cómo asigna los sensores (normalmente *Discrete Inputs*, y *Input Registers* para los analógicos);
    - cómo asigna los actuadores (normalmente *Coils*, y *Holding Registers* para los analógicos).
  - Es lo esperable, pero **verifícalo en su versión** antes de fijar direcciones.
- Si no hay Modbus, la alternativa es OPC UA. Supondría otra biblioteca, que necesita permiso de instalación.
- Escena para empezar: una sencilla de las incluidas (por ejemplo, una cinta con un sensor al principio y otro al
  final) o la que él elija.

### 7a. Cliente Modbus TCP con la biblioteca estándar

- Escribe el cliente en un paquete nuevo, `conexion/` (por ejemplo, `conexion/modbus.py`): fuera del núcleo semántico
  `grafcet/` y sin Qt, para poder probarlo sin interfaz. Solo usa `socket` y `struct`:
  - cabecera MBAP;
  - funciones 01 (leer coils), 02 (leer entradas discretas), 03 (leer holding registers), 04 (leer input
    registers), 05, 06, 15 y 16 (escrituras);
  - excepciones Modbus a mensajes claros;
  - tiempos de espera y reconexión.
- **Sin dependencias nuevas.** Si prefieres `pymodbus`, pide permiso antes.
- Pruebas `S-FIO…` contra un **servidor Modbus falso** levantado en la prueba (`socketserver`, solo en 127.0.0.1,
  puerto efímero): lecturas, escrituras, excepción, desconexión.

### 7b. Asignación de variables a direcciones

- Diálogo «Conexión > Factory I/O…» con:
  - IP, puerto y Slave ID;
  - una tabla que asigna cada **entrada** del grafcet a una dirección de lectura y cada **salida** a una de
    escritura;
  - un botón «Probar conexión».
- La asignación se guarda **fuera del modelo**, en un fichero aparte de la carpeta del proyecto (por ejemplo,
  `conexion-factoryio.json`). No es semántica: no cambia el formato del documento 09 (U-11) ni la revisión del
  modelo.
  - Comprueba que `save_project` no lo borra: solo borra `familia-*.json` de familias conocidas.
  - Regístralo como P-IMP.

### 7c. Ciclo en tiempo real

- Con la conexión activa, la simulación corre en tiempo real (la del paso 1). En cada ciclo:
  1. Lee los sensores.
  2. Si alguno cambió, entra como lote de entradas manuales en el instante lógico actual (`Session.manual_input` +
     `step_external`, como el botón de una entrada).
  3. Escribe los actuadores con el valor de las salidas (`state["outputs"]` y, si se asigna, el de las variables
     internas).
- Periodo configurable; propón 20–50 ms.
  - Avisa en la documentación: un pulso de sensor más corto que el periodo puede perderse, y eso es una limitación
    de la conexión, no del motor.
  - Los flancos los calcula el motor sobre los cambios que recibe.
- La conexión es **opcional y está apagada por defecto**: el producto sigue funcionando sin red (REQ-PLT-03). Solo
  se conecta a la IP que escriba el usuario.

### 7d. Estado seguro (pregunta al responsable antes de implementarlo)

Si el motor se detiene por un diagnóstico (D-LIM-EVOL, D-ESCRITURA-CONFLICTO, una U abierta), se pierde la conexión
o se pausa la simulación, ¿qué se escribe en los actuadores?

- Propuesta: todo a 0 y aviso visible.
- Es una decisión de producto: pregúntala, regístrala como P-IMP y pruébala con el servidor falso.

### 7e. Prueba con la escena real

- El responsable monta en el editor un grafcet para la escena, asigna sensores y actuadores, pulsa «Conectar» y
  «Ejecutar», y comprueba el comportamiento en Factory I/O.
- Sonnet deja una guía corta en el README: «Conectar con Factory I/O».

**Aceptación:**

- pruebas `S-FIO…` con el servidor falso, incluido el estado seguro;
- captura del diálogo de conexión;
- validación del responsable con la escena real;
- P-IMP de la conexión, del fichero de asignación y del estado seguro.

---

## Paso 8 — Entrega

- Sube `APP_VERSION` en `grafcet/profile.py`, por ejemplo a `0.2.0-dev`.
- Actualiza `escritorio/LEEME.txt` con el editor y la conexión, y regenera `dist/GRAFCET`.
- Pon al día:
  - el README («Uso», «Estructura», «Lo que falta»);
  - `docs/03`: estado de la interfaz y de la distribución;
  - `docs/04`: P-IMP nuevas;
  - `spec/clasificacion.py`, con la trazabilidad regenerada.
- Revisa que nada declare conformidad y que la barra de estado lo siga avisando.
- Prueba final del `.exe` en una carpeta copiada fuera del repositorio, para confirmar que no depende de nada del
  proyecto.

---

## Anexo — Datos útiles del código actual

- `Vista(key, title, help_text, build, options, init=None, batches=(), budget=10_000)`.
  - `build()` devuelve `(M o documento, posiciones o None)`.
  - `model` es la estructura que se dibuja; `state()`, el estado observado.
  - `act(op, body)` acepta las operaciones `entrada`, `valor`, `fijar`, `avanzar`, `hasta`, `evolucion` y
    `estabilizar`.
- `Vista.state()["temporal"]`: `{id_expresion: {phase, baseValue, effectiveValue, intervalStart, deadline, label,
  deadlineS}}`. Los tiempos son µs en texto, o `"inactive"`.
- Estados de sesión: `pausada-estable`, `pausada-recorrido`, `error`, `finalizada`. Las entradas manuales solo se
  admiten en `pausada-estable`.
- `persistence.open_model(ruta)` abre una carpeta de proyecto, su `manifest.json` o un `model-….json` suelto.
- `view.auto_layout(doc)` coloca un modelo sin presentación. `view.presentation_for(doc, posiciones)` y
  `view.layout_from_presentation(pres)` escriben y leen las posiciones.
- Ejemplos: `grafcet/examples.py` (`EJEMPLOS[clave] = (título, explicación, constructor)`). Los dos del responsable son
  `contador-inestable` y `contador-flanco`.
- Lecturas: `grafcet/profile.SEMANTIC_OPTIONS`. `normalize_options(None)` da las decididas. Cambiar una lectura es
  empezar una ejecución nueva.
- Dibujo: constantes de proporción en `escritorio/diagrama.py` y `tools/dibujo.js` (`H = 22`, semilado de la etapa;
  `TB = 14`; `ACT_LINK = 26`; `ACT_MIN = 80`; `MARK = 7`). Hay que mantenerlas iguales en los dos.
