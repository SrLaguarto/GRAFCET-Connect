# Núcleo GRAFCET — implementación parcial del paquete 0.1

Implementación de la **segunda IA** a partir de los doce documentos de `../Definición del proyecto/`, que no se modifican. Cubre los requisitos que no dependen de las cuestiones U pendientes. Lo que sí depende de una U no se aproxima: se detiene con un diagnóstico que nombra la cuestión.

> **No se declara conformidad** con IEC 60848:2013 ni con UNE-EN 60848:2022. Las capacidades I son provisionales (U-01); las que dependen de una U abierta están bloqueadas. Ver `docs/06_Declaracion_de_cobertura.md`.

## Uso

Requiere Python ≥ 3.12, sin dependencias externas.

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
| `spec/clasificacion.py` | Clasificación de requisitos y tratamiento de casos | U-12 (propuesta) |
| `tools/banco_de_pruebas.py`, `comparador.html`, `decisiones.py`, `dibujo.js` | Banco de pruebas y comparador de decisiones (no es la interfaz del producto) | SEM-09, NOR-02 |
| `tests/` | Casos T-01…T-26 del documento 11 y suplementarios S-xx | — |

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
- Interfaz gráfica (Qt 6/PySide6 propuesta), exportación SVG/PDF y accesibilidad: requieren instalar la dependencia y ratificar U-10.
- Empaquetado, matriz de sistemas y medición en el equipo de referencia (U-10).
- Ratificación del formato 0.1 (U-11) y cierre de las U normativas, que permitiría desbloquear capacidades.
