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
8. **No invoques subagentes sin necesidad:** una consulta, una lectura o un cambio trivial los hace el coordinador
   directamente.
9. **Registro de autoría:** en modificaciones significativas, el cuerpo del commit lleva una sección «Agentes» que
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
- **No declares conformidad** con IEC 60848 ni con UNE-EN 60848.
- No uses otros productos como oráculo (REQ-CR-04).

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
