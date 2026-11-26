# CLAUDE.md

Instrucciones para Claude Code en este repositorio: aplicación de edición y simulación de GRAFCET (núcleo en
`grafcet/`, simulador y editor de escritorio en `escritorio/`, banco de pruebas y comparador en `tools/`).

Las reglas del proyecto ya escritas siguen vigentes y mandan sobre este fichero en lo que regulan:
`docs/DESARROLLO.md` (uso, estructura, convención de commits y procedencia) y la sección 1 de
`docs/Plan_de_trabajo_Sonnet.md` (límites, arquitectura, comprobaciones y convenciones).

## Arquitectura de agentes

La sesión principal es el **coordinador** y se ejecuta con Opus: `.claude/settings.json` fija `"model": "opus"`
para el proyecto. No es un fichero de `.claude/agents/`, sino la conversación desde la que se lanzan los
subagentes. Los subagentes de proyecto están en `.claude/agents/`:

| Agente | Modelo | Papel | Puede modificar |
|---|---|---|---|
| coordinador (sesión principal) | Opus | Analiza, planifica, decide y valida | Lo que haga falta para validar; no programa lo rutinario |
| `implementador` | Sonnet | Programa, corrige y añade pruebas | Código y pruebas del encargo |
| `verificador` | Sonnet | Revisa y prueba de forma independiente | Nada (solo lectura y ejecución de pruebas) |
| `documentador` | Haiku | Documentación técnica y tareas sencillas | Solo documentación escrita a mano |
| `resolvedor` | Opus, esfuerzo extra alto | Problemas técnicos delicados que, si no, el coordinador consultaría al responsable: diagnóstico con evidencia y propuesta | Nada del repositorio (solo experimentos en `artifacts/`) |
| `sensei` | Opus, esfuerzo máximo | Último recurso: un problema que el `resolvedor` no ha podido cerrar, o uno excepcionalmente grave | Nada del repositorio (solo experimentos en `artifacts/`) |

Se usan **subagentes convencionales** (herramienta Agent con `subagent_type`). No se crean agent teams.

### Protocolo del coordinador

1. **Analiza** el problema y **define el plan**: objetivo, ficheros, criterios de aceptación y decisiones ya
   tomadas. Antes de tocar semántica o comportamiento, consulta las especificaciones y decisiones (ver más abajo).
2. **Delega la programación** al `implementador` con un encargo autosuficiente. No uses Opus para programación
   rutinaria si se puede delegar.
3. Tras la implementación, pide **verificación independiente** al `verificador`, con el mismo objetivo y criterios.
4. Delega la **documentación** al `documentador` cuando haga falta (README, LÉEME, filas `P-IMP`, notas de uso).
5. **Revisa los informes** y decide si hay que corregir. Las decisiones técnicas importantes (arquitectura,
   semántica, cambios de interfaz o de formato) las toma el coordinador o, si son de producto o cuestiones U, el
   responsable.
6. Las **correcciones** las aplica el `implementador`; el coordinador **valida los cambios críticos** (motor,
   persistencia, semántica, formato de datos), revisando el diff y las pruebas.
7. **Sin escrituras simultáneas:** dos agentes no modifican a la vez los mismos ficheros. Asigna ficheros a cada
   encargo y no lances en paralelo encargos que se solapen (el `verificador` no escribe, así que puede revisar
   mientras el `documentador` trabaja en documentación).
8. **El `resolvedor`** se llama solo ante un problema técnico delicado que el coordinador no puede cerrar con
   seguridad. Por ejemplo: un fallo intermitente, un cierre brusco, un problema de hilos o una causa que no se deja
   reproducir. Es el caso en que, si no, preguntaría al responsable. No sustituye al responsable en las decisiones de
   producto, de semántica ni en las cuestiones U. El `sensei` (esfuerzo máximo, muy costoso) es el último recurso: solo
   si el `resolvedor` no ha podido cerrar el problema o si este es excepcionalmente grave.
9. **No invoques subagentes sin necesidad:** una consulta, una lectura o un cambio trivial los hace el coordinador
   directamente.
10. **Registro de autoría:** en modificaciones significativas, el cuerpo del commit lleva una sección «Agentes» que
   dice qué agente hizo cada tarea (por ejemplo: «Implementación: implementador. Verificación: verificador.
   Documentación: documentador. Plan y validación: coordinador»).

## Especificaciones y decisiones

Antes de modificar semántica o comportamiento, consulta:

- `docs/definicion_proyecto/`: el paquete de doce documentos (orden de lectura en el 12; requisitos `REQ-…`,
  cuestiones `U-…`, casos `T-…`). No se modifica.
- `grafcet/profile.py` (`SEMANTIC_OPTIONS`): lecturas de interpretación y sus valores por defecto.
- `docs/04_Decisiones_de_implementacion.md` (filas `P-IMP-…`), `docs/08_Cuestiones_abiertas_para_responder.md` y
  `docs/decisiones.json`: lo decidido y lo que sigue abierto.
- `docs/01_Revision_de_coherencia.md`: hallazgos `H-…` del paquete.

Reglas:

- **No inventes requisitos.** Si algo no está especificado ni decidido, se pregunta al responsable; no se elige.
  Una cuestión U no se cierra con un valor por defecto de implementación.
- **GRAFCET (IEC 60848) no es SFC (IEC 61131-3) ni Siemens GRAPH.** No traslades su semántica (ciclo de PLC,
  tipos de acción SFC, reglas de franqueo de un producto concreto). Cualquier equivalencia debe justificarse con el
  paquete o con una decisión registrada.
- No uses otros productos como oráculo (REQ-CR-04).

## Arquitectura (2.0)

Detalle, capas, hilos y mapa de módulos en `docs/ARQUITECTURA.md`. Reglas al cambiar código:

- **Capas.** `grafcet/` no importa nada del proyecto. `conexion/` solo importa `grafcet/`. `escritorio/` importa `grafcet/` y
  `conexion/`. Ningún módulo del programa importa `tools/`.
- **Sin Qt** en `grafcet/` ni en `conexion/`, ni en `escritorio/geometria/` ni en `escritorio/escena/descriptores.py`,
  `diferencia.py` y `modelo_visual.py`. Qt del dibujo solo en `escritorio/escena/realizador.py` y `escena.py`.
- **Hilo de control.** El motor (`Session`) y el `Coordinador` solo los toca quien tiene el candado de control
  (`conexion/hilos.py`, `Candado`; en la ventana, `self.candado`). Las órdenes al hilo de control (`CicloES`) van solo por
  su interfaz (`arrancar`, `parar`, `pedir_ejecucion`, `despertar`, `tomar_avisos`, `ciclo`), y bajo el candado cuando toca.
- **No dibujar con el candado cogido.** La pantalla copia el estado con el candado y dibuja después, sin él. Tampoco se
  retiene el candado durante un diálogo, un dibujo o una espera de red.
- **Guarda de hilos.** Los cambios que toquen el motor o el coordinador desde la pantalla se prueban con
  `GRAFCONNECT_COMPROBAR_HILOS=1` (pruebas de conexión y `tools/choque_conexion.py`).
- **`grafcet/` no se toca** sin autorización del responsable. Si un cambio de escritorio parece exigirlo, se pregunta antes.
- **Banco de imágenes idéntico.** Cada cambio que afecte al dibujo deja las mismas imágenes que la referencia
  (`python tools/banco_imagenes.py generar CARPETA` y `comparar`, contra `artifacts/v2_cierre/imagenes_2.0_final/`, fijada
  por el responsable el 26-nov-2026 tras los retoques de Carbon y el ajuste de la cápsula del temporizador. Cambian 22
  capturas respecto a `imagenes_2.0`: la cápsula del temporizador y la tarjeta de avisos).

## Relevo entre sesiones

Esta carpeta la usan distintas sesiones, una cada vez. Una sesión puede cortarse en cualquier momento, por ejemplo al
agotarse el crédito, así que el estado del trabajo vive en el repositorio y no en el chat.

- **Al empezar:** lee `ESTADO_TRABAJO.md` (en la raíz) y ejecuta `git status` y `git log --oneline -5`. Sigue desde
  «Siguiente paso». Si lo que ves en git no coincide con el fichero, manda git: dilo y corrige el fichero.
- **Después de cada paso,** no solo al final, actualiza `ESTADO_TRABAJO.md`:
  - qué está hecho;
  - qué queda a medias y en qué ficheros;
  - el siguiente paso exacto;
  - qué falta comprobar;
  - las decisiones nuevas del responsable.

  Añade además una línea en «Registro de sesiones».
- **Commits pequeños y frecuentes,** uno por paso terminado, con la suite en verde y los ficheros añadidos por su nombre.
  Nunca se hace commit de algo roto: si queda a medias, se describe en `ESTADO_TRABAJO.md`.
- **Nunca se hace commit de** `ESTADO_TRABAJO.md`, `AGENTS.md`, `artifacts/`, `.codex/`, `build/` ni `dist/`.
- **Decisiones:** las decisiones del responsable que aparecen en `ESTADO_TRABAJO.md` mandan sobre los planes antiguos.

## Comprobaciones

```bash
python tools/ejecutar_pruebas.py
```

```bash
python tools/generar_trazabilidad.py
```

```bash
python tools/comprobar_paquete.py
```

`ejecutar_pruebas.py` escribe `docs/resultados_pruebas.json` y `generar_trazabilidad.py` regenera `docs/02`, `05`
y `06`. Para probar sin escribir en el repositorio (lo que usa el `verificador`):

```bash
python -m unittest discover -s tests -t tests
```

`tools/paquete.py` busca el paquete en `../Definición del proyecto/`, fuera del repositorio. En un clon sin esa
carpeta, `test_SPKG_paquete_de_transferencia_intacto`, `comprobar_paquete.py` y `generar_trazabilidad.py` fallan
por entorno, no por el cambio. Las pruebas Qt se omiten si falta PySide6.
