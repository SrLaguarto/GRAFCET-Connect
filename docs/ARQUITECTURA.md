# Arquitectura de GRAFCET Connect 2.0

Guía para quien llega nuevo al código. Describe cómo está organizado el programa en la rama `v2` (etapas E0 a E7 con código
hecho; E8, el rediseño de Propiedades, en curso; E9, el cierre). Si este documento y el código no coinciden, manda el código.

Las reglas que hay que respetar al cambiar algo están en la sección «Arquitectura (2.0)» de [CLAUDE.md](../CLAUDE.md).
Este documento da el detalle y el porqué.

## 1. Capas

El programa tiene tres paquetes con dependencias en una sola dirección, y las herramientas quedan fuera:

| Paquete | Qué es | Puede importar | No puede importar | Qt |
|---|---|---|---|---|
| `grafcet/` | Núcleo: modelo, validación, motor, traza, edición sin interfaz y formato `.grafnet` | nada del proyecto | `conexion/`, `escritorio/`, `tools/` | no |
| `conexion/` | Comunicación con la planta (Modbus TCP y HTTP directo), coordinador, hilo de control del ciclo | `grafcet/` | `escritorio/`, `tools/` | no |
| `escritorio/` | Simulador y editor de escritorio: dibujo, paneles, ventana | `grafcet/`, `conexion/` | `tools/` | sí (PySide6) |
| `tools/` | Bancos de pruebas y de imágenes, medidas, comparador, construcción del ejecutable | todo | (nada del programa lo importa) | según la herramienta |

Excepciones dentro de `escritorio/` que no usan Qt y se prueban sin él:

- `escritorio/geometria/`: posiciones, cajas de acciones y comentarios, choques, huecos, equidistancia y ajuste de enlaces.
- `escritorio/escena/descriptores.py`, `diferencia.py` y `modelo_visual.py`: descripción pura de lo que hay que dibujar.

Qt aparece solo en `escritorio/escena/realizador.py` y `escritorio/escena/escena.py` dentro de la escena.

No hay ninguna prueba automática que compruebe estas reglas de importación. Al cambiar imports, revísenlas a mano.

## 2. Módulos principales

Tabla breve de los módulos que más se tocan. No es un inventario completo.

| Módulo | Qué contiene |
|---|---|
| `grafcet/engine.py` | `Session`: el motor (interpretación, reloj, lotes de E/S manuales) |
| `grafcet/view.py` | `Vista`: lo que se muestra de un modelo en simulación (`state()`); lo usan el simulador, el banco y el comparador |
| `grafcet/editor.py` | Operaciones de edición sin interfaz |
| `grafcet/persistence.py` | Lectura y escritura del `.grafnet` |
| `conexion/coordinador.py` | `Coordinador`: máquina de estados de la conexión (leer, aplicar, calcular, escribir); no cambió en E7 |
| `conexion/adaptador.py`, `adaptador_directo.py` | Traducción de E/S a variables del motor (Modbus y HTTP directo) |
| `conexion/modbus.py` | `ClienteModbus`: cliente Modbus TCP síncrono, para un único trabajador |
| `conexion/intercambio_directo.py`, `http_directo.py` | Lectura y escritura por lotes de la conexión directa |
| `conexion/ciclo.py` | `CicloES` (hilo de control) y `Espera` (espera de alta resolución) |
| `conexion/hilos.py` | `Candado` y la guarda de hilos (`proteger`, `AccesoSinCandado`) |
| `escritorio/geometria/` | Geometría pura (E1): `base`, `choques`, `enlaces`, `marcos`, `seleccion`, `textos`, `acciones`, `equidistancia` |
| `escritorio/escena/` | Escena incremental (E3, E4): `descriptores`, `modelo_visual`, `diferencia`, `realizador`, `escena` (`EscenaIncremental`) |
| `escritorio/diagrama.py` | `VistaDiagrama`: la vista del dibujo |
| `escritorio/edicion/` | `Edicion` (fachada) y sus partes (sección 3) |
| `escritorio/ventana/` | `Ventana` (fachada) y sus mixins (sección 3) |
| `escritorio/refresco_conexion.py` | Refresco de catálogo, tiempos y muestra de la conexión en pantalla |
| `escritorio/bloques.py` | Programador por bloques de receptividades, condiciones y eventos: motor de fichas, catálogo, área, herramientas y modelo de modificadores (E8). La banda de categorías está en `banda_bloques.py` |
| `escritorio/banda_bloques.py` | `BandaBloques` y `BotonBloque` (E8): la banda de categorías del programador por bloques, con un botón por bloque que admite clic y arrastre. Crea el bloque y avisa; el programador decide dónde va |
| `escritorio/partes_propiedades.py` | Piezas de la ventana de Propiedades rediseñada (E8): `CampoComentario` (comentario de una línea que crece y se estira), `PiePropiedades` (etiqueta y comentario) y `ConmutadorPartes` («Condición \| Acción», «Evento \| Acción»), que `flotantes.py` monta en cada tarjeta |
| `escritorio/menu_variable.py` | El menú común de variable (E8): `ComboMenu`, base del desplegable nativo de Qt de la ventana y del lienzo; `DelegadoMenu` (grupos Salidas y Memorias, barra de origen, tipo corto donde varía) y `FiltroMenu` (filtro con más de 12 variables). No crea variables |
| `escritorio/propiedades.py`, `variables.py`, `entradas_salidas.py`, `paneles.py` | Paneles: Propiedades, Variables, E/S y los plegables |
| `escritorio/flotantes.py`, `ayudas_emergentes.py` | Ventanas emergentes y ayudas. `flotantes.py` es la ventana de Propiedades (E8): franja con la vista previa, conmutador de partes y pie |
| `escritorio/archivos.py`, `proyecto_archivo.py` | Archivo único `.grafnet` y su sello |
| `escritorio/simulador.py` | Punto de entrada del programa de escritorio |

## 3. Piezas de `escritorio/`

### Geometría pura

Las funciones de posiciones, choques, huecos y equidistancia están en `escritorio/geometria/`, sin Qt. Así se prueban
rápido, sin pantalla. `Edicion` y `VistaDiagrama` las llaman; no las reimplementan.

### Escena incremental

El dibujo del diagrama no se rehace entero en cada cambio. Sigue esta cadena (sección 5):

- `modelo_visual.construir` convierte el modelo y su estado en un `ModeloVisual`: una descripción pura por elemento.
- `diferencia.diferencia` compara el modelo visual nuevo con el anterior y dice qué dar de alta, de baja o de actualizar.
- `EscenaIncremental.aplicar` (en `escena/escena.py`) aplica solo esa diferencia con `realizador`, que crea y actualiza los objetos de Qt de cada elemento.


Si `construir` falla, la escena queda como estaba. La proporción de la escena y la notación del dibujo son las de
`tools/dibujo.js`; cambiar el dibujo implica repetir el banco de imágenes.

### `Edicion` como fachada

`escritorio/edicion/__init__.py` define `Edicion`, que hereda de `QObject` y de un mixin por parte:

| Mixin | Módulo | Responsabilidad |
|---|---|---|
| `_Modelo` | `modelo.py` | Modelo de edición y `reconstruir` |
| `_Seleccion` | `seleccion.py` | Selección |
| `_Gestos` | `gestos.py` | Eventos del lienzo, pulsar–mover–soltar y vista previa |
| `_Arrastre` | `arrastre.py` | Grupos móviles, imanes y cambio de marco |
| `_Colocacion` | `colocacion.py` | Colocación de acciones (adaptadores a la geometría) |
| `_Enlaces` | `interaccion_enlaces.py` | Enlaces, vías manuales, saltos, retornos y flechas |
| `_Diagnosticos` | `diagnosticos.py` | Avisos, resaltado y parpadeo |
| `_Acciones` | `acciones.py` | Acciones nuevas o existentes, borradores y promoción |
| `_Grupos` | `grupos.py` | Grupos de acciones |
| `_Menus` | `menus.py` | Menús contextuales de la edición |
| `_Variables` | `variables.py` | Tabla de variables |
| `_Formulas` | `formulas.py` | Conversión entre fórmulas, texto y condiciones |
| `_Jerarquia` | `jerarquia.py` | Macroetapas, parciales, recintos y encuadre |
| `_Forzados` | `forzados.py` | Órdenes de forzado |
| `_Portapapeles` | `portapapeles.py` | Copiar y pegar |
| `_Historial` | `historial.py` | Operaciones atómicas, deshacer y rehacer |

La interfaz pública (`prensar`, `soltar`, `cambia`…) se mantiene en la fachada, porque las pruebas y el resto del
programa la usan. Para añadir un comportamiento de edición, se pone en la parte que le corresponde.

### `Ventana` como fachada de mixins

`escritorio/ventana/__init__.py` define:

```
class Ventana(Menus, Archivos, Simulacion, ConexionES, Modos, VistaVentana, ArchivosProyecto, QMainWindow)
```

- Cada mixin es una clase sin estado propio: `menus.py`, `archivos.py`, `simulacion.py` (motor y reloj de la
  simulación), `es.py` (`ConexionES`: E/S externas y conexión), `modos.py` (edición o simulación), `vista.py`
  (`VistaVentana`). `dialogos.py`, `widgets.py` y `constantes.py` son auxiliares.
- `Ventana.__init__` crea el estado compartido: el candado (`self.candado`), el coordinador, el hilo de control y los
  temporizadores. Los mixins usan ese estado.
- `ArchivosProyecto` viene de `escritorio/archivos.py`.
- El intervalo de avance sin conexión es `TICK_MS = 100` (`ventana/constantes.py`).

## 4. Hilos

Hay tres hilos que tocan estado compartido:

| Hilo | Qué hace | Qué no hace |
|---|---|---|
| **Pantalla** (Qt) | Edición y gestos; simulación manual sin conexión; atiende los avisos de la conexión; refresca el dibujo conectado a 10 Hz como mucho | No hace el ciclo de E/S cuando hay hilo de control |
| **Control** (`CicloES`, `conexion/ciclo.py`) | Espera hasta el plazo de la próxima lectura o hasta un aviso; con el candado, avanza el reloj lógico y llama a `Coordinador.tick`; avisa a la pantalla | No toca Qt, ni widgets, ni diálogos |
| **Trabajador de red** (`Coordinador`, `conexion/coordinador.py`) | Hace las llamadas que bloquean (leer, escribir, conectar, cerrar) | No toca el motor ni Qt; al terminar, despierta al hilo de control |

### Candado único

`conexion/hilos.py` define `Candado`: un `RLock` reentrante que sabe qué hilo lo tiene y si el hilo de control está vivo
(`control_vivo`). `Ventana.candado` es la única instancia.

Reglas:

- El motor (`Session`) y el `Coordinador` solo los toca quien tiene el candado.
- El hilo de control lo coge para un ciclo (en torno a 1 ms más el avance del motor). No lo retiene durante una espera.
- La pantalla lo coge para copiar lo que enseña y para dar órdenes con conexión. Nunca lo retiene durante un dibujo, un
  diálogo ni una espera de red: si lo hiciera, el hilo de control se quedaría parado.
- Sin conexión no hay hilo de control: la pantalla maneja el motor directamente, como en la 1.x.

### Copiar bajo el candado, dibujar sin él

La pantalla no dibuja con el motor abierto. En `Simulacion.refrescar` (`escritorio/ventana/simulacion.py`), el modelo y
el estado se copian con el candado y el dibujo se hace después, sin él:

```
with self.candado:
    M, S = self.v.model, self.v.state()
# … dibujar con M y S, sin el candado
```

Al dibujar, otro hilo puede avanzar el motor; la pantalla enseña una foto coherente de un instante, no el estado en vivo.

### Órdenes al hilo de control

Las órdenes de la pantalla pasan por la interfaz de `CicloES`:

- `arrancar()` y `parar()`: `parar` espera a que acabe el hilo. Llamarlo sin el candado (el hilo puede estar esperándolo).
- `pedir_ejecucion(ejecutar)`: Play o Stop. Lo decide `_ejecutar_ahora()`, el único sitio donde se decide si el ciclo ejecuta el motor. Un estado de pausa futuro cabe ahí.
- `despertar()`: avisa al hilo de control sin esperar al plazo.
- `tomar_avisos()`: lee los avisos del ciclo (`motor_parado`, `conexion_caida`) con el candado.
- `ciclo()`: un ciclo. Lo llama el hilo de control; la pantalla también puede llamarlo si no hay hilo vivo.

Las órdenes con conexión son síncronas: `Play`, `Stop` o `conectar` devuelven cuando el efecto está hecho. Las pruebas
que llaman a `_act` y miran el estado justo después siguen valiendo.

### Guarda de hilos (`GRAFCONNECT_COMPROBAR_HILOS=1`)

Con la variable a `1`, `proteger` cambia la clase de `Coordinador` y de `Session` por una subclase que exige el candado
al leer o escribir sus atributos protegidos, mientras el hilo de control esté vivo. Si alguien los toca sin el candado,
lanza `AccesoSinCandado` con el nombre del objeto, del atributo y del hilo.

- Sin la variable, no hace nada y no cuesta nada.
- Lo protegen `Ventana.__init__` (los métodos y atributos de `COORDINADOR`) y `Simulacion` (los de `SESION`, al crear la sesión).
- Se usa en las pruebas de conexión y en el choque de conexión: `tools/choque_conexion.py` y `tests/test_choque_conexion.py`.
  Las pruebas de `tests/test_ciclo_es.py` cubren el hilo sin Qt.

Solo se protegen las lecturas que cambian el estado o que se leen en bloque. Los escalares sueltos (`estado`, `mensaje`,
`activo`) son atómicos y la pantalla los usa como banderas; no se protegen.

### Espera y regularidad

- `Espera` (`conexion/ciclo.py`) duerme con un temporizador de alta resolución de Windows y un evento, en una sola espera
  del sistema. Vuelve a la hora exacta o en cuanto alguien llama a `despertar`, lo que ocurra antes. Fuera de Windows usa
  `Event.wait` y un sueño corto.
- Mientras haya un hilo de control, el intervalo de cambio del GIL baja a 0,5 ms (`_ajustar_gil`). Al arrancar el primero
  se congela el gc (`gc.freeze`); cada 10 s (`REFREEZE_S`) se vuelve a congelar, y al parar el último se descongela.
  Motivo y medidas: `artifacts/v2_e7/INFORME_E7.md`.

### Fallos del hilo de control

Una excepción de un ciclo no mata el hilo. `_bucle` la pasa a `al_error`, que en la ventana (`_error_ciclo`) deja la
conexión en error y lo cuenta a la pantalla. Los avisos normales (`al_novedad`) se envían como mucho 10 veces por segundo,
o al momento si cambia el estado de la conexión.

### Cierre

Antes de cerrar el coordinador se para el hilo de control: `ventana/archivos.py` llama a `ciclo.parar()` antes del cierre
del coordinador, y `ventana/simulacion.py` lo para cuando la conexión termina. No se cierra el TCP con el hilo vivo.

## 5. Flujo de dibujo

```
edición (escritorio/edicion/*)  ──reconstruir──►  Vista.state()  (grafcet/view.py, con el candado si hay conexión)
                                                        │
                                                        ▼
                    modelo_visual.construir  ──►  ModeloVisual (descriptores puros)
                                                        │
                                                        ▼
                    diferencia.diferencia  ──►  Cambios (alta, baja, actualización, orden)
                                                        │
                                                        ▼
                    EscenaIncremental.aplicar  ──►  realizador (solo lo que cambia)
                                                        │
                                                        ▼
                                VistaDiagrama (escritorio/diagrama.py)
```

- Edición: las operaciones de edición llaman a `reconstruir` (y señalan `redibujar`), que actualizan la vista.
- Simulación sin conexión: `_tick` cada `TICK_MS` avanza el motor; el dibujo se refresca por su propio camino.
- Simulación con conexión: el refresco va como mucho a 10 Hz. Lo disparan el aviso del hilo de control
  (`_RespuestaModbus.lista`), el temporizador de la ventana y `_proxima_lectura`.

Hay también un camino de dibujo completo sin diferencia (`realizador.todo`, usado en `escritorio/diagrama.py`).
No se ha comprobado para qué se usa; ver la sección 8.

## 6. Flujo de simulación

Sin conexión:

1. `Ventana._tick` (cada `TICK_MS`) mide el tiempo transcurrido y lo pasa a `_act("avanzar", us=…)`.
2. `Session` avanza el reloj lógico y la traza. La pantalla refresca el dibujo con la copia del estado.

Con conexión (hilo de control):

1. `CicloES.ciclo()` coge el candado.
2. Si el motor está en marcha y estable, avanza el reloj lógico **antes** de aplicar las muestras (P-IMP-50).
3. `Coordinador.tick(ejecutar)` hace leer → aplicar → calcular → escribir. Esa secuencia y su orden no cambiaron en E7.
4. Si el motor se ha parado o la conexión se ha caído, lo anota en los avisos.
5. Suelta el candado, avisa a la pantalla (`al_novedad`) y espera al plazo de la próxima lectura o a un `despertar`.

La pantalla, al recibir el aviso, atiende los avisos (`_atender_conexion`): si el motor se ha parado, pasa a Pausa y lo cuenta,
refresca y, si la conexión ha terminado, para el hilo.

Play y Stop: `pedir_ejecucion(on)` y `despertar()`. Lo que hace el ciclo con el motor lo decide `_ejecutar_ahora()`.

## 7. Dónde va cada tipo de cambio

| Cambio | Dónde | Notas |
|---|---|---|
| Semántica, orden de evaluación, lotes, reloj del motor | `grafcet/` | Solo con autorización del responsable (regla 3 del plan 2.0). Una prueba de equivalencia (`tools/equivalencia_nucleo.py`) lo compara con la referencia. |
| Formato `.grafnet` | `grafcet/persistence.py` y `grafcet/canonical.py` | El `.grafnet` tiene que seguir abriéndose en la 1.x y al revés. |
| Modbus, conexión directa, mapa de E/S | `conexion/` (`adaptador*.py`, `modbus.py`, `intercambio_directo.py`, `configuracion*.py`) | Sin Qt. |
| Máquina de estados de la conexión | `conexion/coordinador.py` | No cambiar el orden leer → aplicar → calcular → escribir. |
| Hilo de control, candado, espera | `conexion/ciclo.py`, `conexion/hilos.py` | Sin Qt. Las órdenes a `CicloES` solo por su interfaz. |
| Cómo se apoya un elemento en pantalla (posición, cajas, choques) | `escritorio/geometria/` | Sin Qt. Pruebas rápidas sin pantalla. |
| Qué se dibuja de un elemento (forma, color, texto) | `escritorio/escena/descriptores.py`, `modelo_visual.py` | Sin Qt. Repetir el banco de imágenes. |
| Cómo se aplica a la escena | `escritorio/escena/realizador.py`, `escena.py` | Solo aquí se crean objetos de Qt del dibujo. |
| Gestos, selección, arrastre, enlaces, acciones, grupos, deshacer | `escritorio/edicion/<parte>.py` | La fachada `edicion/__init__.py` solo une las partes. |
| Menús, archivos, simulación, E/S, modos, vista de la ventana | `escritorio/ventana/<mixin>.py` | `ventana/__init__.py` solo crea y conecta controles. |
| Refresco de la conexión en pantalla | `escritorio/refresco_conexion.py` | Copia con el candado; dibuja sin él. |
| Propiedades de transición y acción (E8) | `escritorio/propiedades.py`, `flotantes.py`, `partes_propiedades.py`, `acciones.py`, `bloques.py`, `banda_bloques.py` | Hecho en E8 (sección 8). |
| Menú común de variable (ventana y lienzo) | `escritorio/menu_variable.py`; `acciones.py` (`_ComboVariable`) y `diagrama.py` (`SelectorAccion`) lo usan | Un solo componente en los dos sitios. |
| Etiquetas de transiciones (Ver) | `escritorio/edicion/modelo.py` (`poner_etiquetas`, `etiqueta_como_las_demas`), `escritorio/ventana/menus.py` | La casilla sale de `labelVisible`; no hay campo nuevo. |
| Paneles (Variables, E/S, plegables) | `escritorio/variables.py`, `entradas_salidas.py`, `paneles.py` | |
| Ayudas emergentes | `escritorio/ayudas_emergentes.py` | |
| Bancos, medidas, choque, comparador | `tools/` | Nada del programa importa `tools/`. |

## 8. Pendientes y límites

- **E8 implementado, cierre pendiente.** El rediseño de Propiedades (franja, pie, conmutador, banda y menú común) está
  hecho en sus cuatro tramos; falta el cierre (P14: hoja de contactos, pruebas de las herramientas de `docs/`). Los
  módulos nuevos de E8 son `banda_bloques.py`, `partes_propiedades.py` y `menu_variable.py`.
- **Reglas de importación sin prueba automática.** Ver la sección 1.
- **Camino de dibujo completo** (`realizador.todo`): uso por confirmar.
- **Órdenes con conexión.** Son síncronas (con el candado), no una cola. El plan de E7 hablaba de «fotos inmutables» y de
  una cola; lo implementado es copiar el estado con el candado y dar las órdenes de forma síncrona.
- **Guarda de hilos.** Solo protege los nombres listados en `COORDINADOR` y `SESION`. Un atributo nuevo que se toque
  desde otro hilo no está cubierto hasta que se añada a esas listas.
- **Mapa de módulos** (`artifacts/arquitectura/arquitectura.json`): es una fotografía del commit `e5c9952`, sin el
  generador en el repositorio. Sus datos de etapas están desactualizados (E7 y E8 no coinciden con el plan).
