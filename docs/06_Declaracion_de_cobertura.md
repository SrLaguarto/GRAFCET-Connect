# 06. Declaración de cobertura

Documento generado por `tools/generar_trazabilidad.py` a partir de `grafcet/profile.py`.

**No se declara conformidad con IEC 60848:2013 ni con UNE-EN 60848:2022. Ninguna capacidad está aprobada: las capacidades I son provisionales por U-01 y las que dependen de una cuestión abierta están bloqueadas. No se afirma certificación, aprobación UNE ni seguridad funcional.**

| Eje de versión | Valor |
|---|---|
| format | 0.1 |
| application | 0.1.0-dev |
| profile | grafcet-impl-provisional@0.1.0 |
| standard | IEC 60848:2013 ed. 3.0 |

Base normativa declarada: IEC 60848 edición 3.0 (2013-02-27), adopción UNE-EN 60848:2022. No se sustituye silenciosamente (REQ-NOR-01).

## Capacidades

| Capacidad | Estado | Motivo | Requisitos |
|---|---|---|---|
| `acciones.activacion-condicionada` — Acción al activar/desactivar con condición adicional | pendiente / bloqueada | no implementada en esta iteración | REQ-ACT-02 |
| `acciones.conflicto` — Conflicto de escritura y dependencia cruzada: no compila si es seguro; si no, se detiene | provisional (especificada, sin contraste normativo) | P-IMP-16; decisión del responsable, hoja 08 2.1 C y 2.2 B | REQ-ACT-03 |
| `acciones.continuas` — Disyunción de contribuciones continuas sobre situación efectiva | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-ACT-01 |
| `acciones.lecturas-contexto` — Lo asignado en un instante se ve en ese mismo instante; vale la última asignación | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 2.3 A y 2.4 A | REQ-ACT-05 |
| `acciones.limitadas` — Acción continua limitada [t0, t0+d) | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-TMP-02 |
| `acciones.memorizadas` — Acciones memorizadas al activar, desactivar o por evento | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-ACT-02 |
| `acciones.salidas-continuas-leidas` — Leer salidas continuas en expresiones | pendiente / bloqueada | H-10 | REQ-ACT-01 |
| `escenario.predicado-parada` — Condición de parada por predicado observador | pendiente / bloqueada | P: no implementada en esta iteración | REQ-SIM-02 |
| `eventos.entradas` — Flancos sobre proposiciones de entradas en la primera evolución del contexto | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-EVT-01 |
| `eventos.franqueamiento` — Eventos de franqueamiento como disparadores | pendiente / bloqueada | U-03 | REQ-EVT-03 |
| `eventos.internos` — Flancos sobre actividad, variables internas o condiciones temporales | pendiente / bloqueada | U-03 | REQ-EVT-03 |
| `eventos.recorrido` — Uso de un evento por transiciones validadas durante su propio recorrido | pendiente / bloqueada | U-03 | REQ-EVT-03, REQ-SEM-09 |
| `evolucion.ordinaria` — Validación, receptividad, cambio conjunto, simultaneidad y relación S'=(S\D)∪A | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-02, REQ-SEM-03, REQ-SEM-04 |
| `inicio.acciones-activacion` — Acciones al activar de las etapas iniciales: se ejecutan al arrancar | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.1 A | REQ-ACT-02 |
| `inicio.inestable` — Transición franqueable en la situación inicial: evoluciona en τ=0 | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.2 A | REQ-SEM-01 |
| `inicio.memoria-no-nula` — Variable memorizada con valor inicial distinto de cero (no compila) | pendiente / bloqueada | decisión del responsable, hoja 08 1.5 A: se usa una acción al activar | REQ-ACT-02 |
| `inicio.temporal-entrada-verdadera` — Condición temporal sobre entrada verdadera al iniciar: cuenta desde τ=0 | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.3 A | REQ-TMP-02 |
| `instantanea.recorrido` — Instantánea exacta en mitad de un recorrido | pendiente / bloqueada | P: D-INSTANTANEA-FASE | REQ-SIM-04 |
| `jerarquia.encapsulacion` — Ejecución de encapsulación | pendiente / bloqueada | no implementada en esta iteración; U-08 | REQ-JER-05 |
| `jerarquia.estructura` — Edición, persistencia y validación de forzados, macroetapas y recintos | provisional (especificada, sin contraste normativo) | I/P | REQ-MOD-07, REQ-JER-03 |
| `jerarquia.forzado` — Ejecución de órdenes de forzado | pendiente / bloqueada | no implementada en esta iteración; U-08 (H-18) | REQ-JER-02 |
| `jerarquia.macroetapas` — Ejecución de macroetapas | pendiente / bloqueada | no implementada en esta iteración; U-08 | REQ-JER-04 |
| `lotes` — Lotes simultáneos y lotes ordenados con igual tiempo | provisional (especificada, sin contraste normativo) | P | REQ-EVT-02 |
| `parciales.actividad` — activePartial sobre parcial sin hijos | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-JER-01 |
| `parciales.anidados` — activePartial sobre parcial con parciales hijos | pendiente / bloqueada | H-08 | REQ-JER-01 |
| `permanencia.actividad` — Etapa activada y desactivada a la vez permanece activa | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-05 |
| `permanencia.efectos` — Acciones, eventos y tiempo de una etapa en permanencia activa o reactivada | pendiente / bloqueada | U-04 (H-05) | REQ-SEM-05, REQ-EVT-03 |
| `situacion.inicial.explicita` — Situación inicial = etapas marcadas iniciales | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-01 |
| `situacion.inicial.vacia` — Arranque sin etapas iniciales | pendiente / bloqueada | U-07 | REQ-SEM-01, REQ-MOD-04 |
| `temporal.base-compuesta` — Base temporal distinta de entradas o active(etapa) | pendiente / bloqueada | H-09 | REQ-TMP-02 |
| `temporal.coincidencias` — Vencimiento coincidente con lote, caída en el vencimiento, rebote | pendiente / bloqueada | U-06 | REQ-TMP-03 |
| `temporal.delay` — delay(d1,p,d2) ordinario con d1>0 | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-TMP-02 |
| `temporal.delay-cero` — delay con d1=0 | pendiente / bloqueada | U-06 | REQ-TMP-03 |
| `temporal.duracion-etapa-inicial` — La duración de una etapa inicial cuenta desde τ=0 (oráculos T-12a/T-12c) | provisional (especificada, sin contraste normativo) | I; decisión del responsable, hoja 08 1.4 A | REQ-TMP-02 |
| `temporal.elapsed` — Duración elapsed(etapa) ejecutable | pendiente / bloqueada | U-06 (valor inactivo); no implementada | REQ-TMP-02 |
| `temporal.reentrada-virtual` — Salida y reentrada en el mismo instante: la duración de la etapa no se interrumpe | provisional (especificada, sin contraste normativo) | decisión del responsable de producto, 25-10-2026 (P-IMP-18; cierra H-09) | REQ-TMP-02 |
| `temporal.vencimientos-simultaneos` — Varios vencimientos en el mismo instante (independientes del orden) | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-TMP-02 |
| `transiciones.fuente-evento` — Transición fuente con receptividad de evento (primera evolución) | provisional (especificada, sin contraste normativo) | I (U-01); repetición U-07 | REQ-MOD-04 |
| `transiciones.fuente-nivel` — Transición fuente con receptividad de nivel | pendiente / bloqueada | U-07 | REQ-MOD-04 |
| `transiciones.fuente-repeticion` — Transición fuente por evento en evoluciones posteriores del mismo contexto | pendiente / bloqueada | U-07 (con U-03) | REQ-MOD-04, REQ-EVT-03 |
| `transiciones.sin-lados` — Transición sin precedentes ni siguientes | pendiente / bloqueada | U-07 | REQ-MOD-04 |
| `transiciones.sumidero` — Transición sin siguientes | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-MOD-04 |
| `transitorios` — Situaciones virtuales sin pulsos continuos; memorizadas conservadas | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-06 |

## Materias excluidas por cuestiones críticas abiertas (REQ-NOR-02)

- `eventos.franqueamiento`: U-03
- `eventos.internos`: U-03
- `eventos.recorrido`: U-03
- `jerarquia.encapsulacion`: no implementada en esta iteración; U-08
- `jerarquia.forzado`: no implementada en esta iteración; U-08 (H-18)
- `jerarquia.macroetapas`: no implementada en esta iteración; U-08
- `permanencia.efectos`: U-04 (H-05)
- `situacion.inicial.vacia`: U-07
- `temporal.coincidencias`: U-06
- `temporal.delay-cero`: U-06
- `temporal.elapsed`: U-06 (valor inactivo); no implementada
- `transiciones.fuente-evento`: I (U-01); repetición U-07
- `transiciones.fuente-nivel`: U-07
- `transiciones.fuente-repeticion`: U-07 (con U-03)
- `transiciones.sin-lados`: U-07

## Lecturas seleccionables como hipótesis (P-IMP-15)

Elegir una lectura distinta de la predeterminada no cierra la cuestión ni amplía la cobertura: la ejecución queda marcada con esa hipótesis en su perfil efectivo y en su traza.

- **U-03** (U-03: receptividades con eventos de entrada en evoluciones posteriores del instante); por defecto `detener`:
  - `detener`: Detener con D-SEM-PENDIENTE: la cuestión sigue abierta
  - `situacion-anterior`: El evento solo franquea transiciones validadas en la situación anterior al evento
  - `recorrido`: El evento sigue disponible durante todo el recorrido transitorio que provoca
- **1.1** (U-09: acciones «al activar» de las etapas iniciales); por defecto `A`:
  - `A`: Se ejecutan al arrancar
  - `B`: No se ejecutan: la situación inicial no es una activación
- **1.2** (U-09: situación inicial inestable); por defecto `A`:
  - `A`: Evoluciona en τ=0
  - `B`: Espera al primer cambio de entradas
  - `C`: No compila
- **1.3** (U-09: temporizador sobre una entrada ya verdadera al arrancar); por defecto `A`:
  - `A`: Cuenta desde τ=0
  - `B`: Espera una subida real de la entrada
- **1.5** (U-09: variable memorizada con valor inicial distinto de 0); por defecto `A`:
  - `A`: No compila (se usa una acción al activar)
  - `B`: Empieza con el valor declarado
- **2.1** (U-05: varias asignaciones simultáneas a la misma variable); por defecto `C`:
  - `A`: Todas leen el valor anterior; si coinciden, una sola escritura
  - `B`: Se acumulan, una detrás de otra (orden de identificador)
  - `C`: Conflicto
- **2.2** (U-05: dependencia cruzada entre asignaciones simultáneas); por defecto `B`:
  - `A`: Todas leen el estado anterior (intercambio)
  - `B`: Error: no compila o se detiene
- **2.3** (U-05: receptividad que lee un valor asignado en el mismo instante); por defecto `A`:
  - `A`: Ve el valor nuevo
  - `B`: Ve el valor de antes del instante
- **2.4** (U-05: asignaciones distintas sucesivas en el mismo instante); por defecto `A`:
  - `A`: Vale la última
  - `B`: Conflicto
- **2.5** (U-05: salida continua que lee una memoria cambiada en el instante); por defecto `A`:
  - `A`: Usa el valor final del instante
  - `B`: Usa el valor de antes del instante
- **3.1** (U-04: acciones al activar/desactivar de una etapa en permanencia activa); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecuta ninguna
  - `B`: Se ejecutan las dos
- **3.2** (U-04: temporizador de una etapa en permanencia activa o reactivada); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Sigue contando
  - `B`: Vuelve a empezar
- **3.3** (U-04 (H-05): acciones al activar una etapa que ya estaba activa); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecutan
  - `B`: Se ejecutan
- **4.1** (U-06: la base de un retardo cambia exactamente en su vencimiento); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Primero vence el retardo
  - `B`: Primero cambia la entrada (cancela)
- **4.2** (U-06: rebote durante el retardo de desconexión); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: La condición sigue verdadera sin interrupción
  - `B`: Se mantiene el plazo; después vuelve a contar el retardo de conexión
- **4.3** (U-06: lote y vencimiento independientes en el mismo instante); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Juntos en un solo instante
  - `B`: Primero el vencimiento
  - `C`: Primero el lote
  - `D`: Solo se detiene si el resultado depende del orden
- **4.4** (U-06: retardo cero); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: 0s/p equivale a p
  - `B`: No compila
- **5.2** (U-03: acción por evento en una etapa que se desactiva con ese mismo evento); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Se ejecuta
  - `B`: No se ejecuta
- **5.3** (U-03: acción por evento en una etapa que se activa con ese mismo evento); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecuta
  - `B`: Se ejecuta
- **6.1** (U-07: grafcet sin etapas iniciales); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Arranca sin etapas activas
- **6.2** (U-07: transición fuente con receptividad de nivel); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Imposición continua: mientras sea verdadera, mantiene activas sus etapas siguientes
- **6.3** (U-07: transición fuente con flanco en evoluciones posteriores del instante); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Franquea una sola vez por flanco
- **6.4** (U-07: transición sin etapas antes ni después); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Se permite y no tiene efecto
- **8.1** (H-08: actividad de un parcial con parciales hijos); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Cuenta también las etapas de los hijos
  - `B`: Solo las etapas propias
- **8.2** (H-10: leer una salida continua en una expresión); por defecto `detener`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Prohibido: no compila
  - `B`: Valor de la situación estable anterior
  - `C`: Valor según la situación inestable del momento
