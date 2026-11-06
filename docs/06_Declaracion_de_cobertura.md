# 06. Declaración de cobertura

Documento generado por `tools/generar_trazabilidad.py` a partir de `grafcet/profile.py`.

**No se declara conformidad con IEC 60848:2013 ni con UNE-EN 60848:2022. Ninguna capacidad está aprobada: las capacidades I son provisionales por U-01 y las que dependen de una cuestión abierta están bloqueadas. No se afirma certificación, aprobación UNE ni seguridad funcional.**

| Eje de versión | Valor |
|---|---|
| format | 0.1 |
| application | 1.0.2 |
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
| `acciones.salidas-continuas-leidas` — Leer salidas continuas en expresiones: valor según la situación del momento, también la inestable | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 8.2 C (cierra H-10) | REQ-ACT-01 |
| `escenario.predicado-parada` — Condición de parada por predicado observador | pendiente / bloqueada | P: no implementada en esta iteración | REQ-SIM-02 |
| `eventos.entradas` — Flancos sobre proposiciones de entradas en la primera evolución del contexto | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-EVT-01 |
| `eventos.franqueamiento` — Eventos de franqueamiento como disparadores | pendiente / bloqueada | U-03 | REQ-EVT-03 |
| `eventos.internos` — Flancos sobre actividad, variables internas o condiciones temporales | pendiente / bloqueada | U-03 | REQ-EVT-03 |
| `eventos.recorrido` — Un evento solo franquea las transiciones validadas antes de él; una acción por evento solo se ejecuta si su etapa estaba activa antes y no sale con él | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 5.1 «situación anterior» (seleccionable, P-IMP-15), 5.2 B y 5.3 A | REQ-EVT-03, REQ-SEM-09 |
| `evolucion.ordinaria` — Validación, receptividad, cambio conjunto, simultaneidad y relación S'=(S\D)∪A | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-02, REQ-SEM-03, REQ-SEM-04 |
| `inicio.acciones-activacion` — Acciones al activar de las etapas iniciales: se ejecutan al arrancar | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.1 A | REQ-ACT-02 |
| `inicio.inestable` — Transición franqueable en la situación inicial: evoluciona en τ=0 | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.2 A | REQ-SEM-01 |
| `inicio.memoria-no-nula` — Variable memorizada con valor inicial distinto de cero (no compila) | pendiente / bloqueada | decisión del responsable, hoja 08 1.5 A: se usa una acción al activar | REQ-ACT-02 |
| `inicio.temporal-entrada-verdadera` — Condición temporal sobre entrada verdadera al iniciar: cuenta desde τ=0 | provisional (especificada, sin contraste normativo) | decisión del responsable, hoja 08 1.3 A | REQ-TMP-02 |
| `instantanea.recorrido` — Instantánea exacta en mitad de un recorrido | pendiente / bloqueada | P: D-INSTANTANEA-FASE | REQ-SIM-04 |
| `jerarquia.encapsulacion` — Encapsulación: al entrar, etapas con enlace de activación (al arrancar, las iniciales); al salir, se desactiva todo el contenido | provisional (especificada, sin contraste normativo) | I (U-01), documento 06 y LOC §7.4; P-IMP-23 | REQ-JER-05 |
| `jerarquia.encapsulacion-coincidencia` — Transición interior que franquea cuando se desactiva su encapsulante: primero actúa y después se desactiva | provisional (especificada, sin contraste normativo) | decisión del responsable, chat 27-10-2026, 7.6 B (coherente con 4.1 A y 4.3 A) | REQ-JER-06 |
| `jerarquia.encapsulacion-permanencia` — Encapsulante en permanencia activa: su contenido se mantiene | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 3.4 A | REQ-JER-05, REQ-SEM-05 |
| `jerarquia.estructura` — Edición, persistencia y validación de forzados, macroetapas y recintos | provisional (especificada, sin contraste normativo) | I/P | REQ-MOD-07, REQ-JER-03 |
| `jerarquia.forzado` — Forzado: explícito, actual, vacío e inicial; el destino no evoluciona mientras está vigente | provisional (especificada, sin contraste normativo) | I (U-01), documento 06 y LOC tabla 9; P-IMP-23 | REQ-JER-02, REQ-JER-03 |
| `jerarquia.forzado-acciones` — Acciones al activar o desactivar de las etapas que cambia un forzado: se ejecutan | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 7.8 A (cierra H-24) | REQ-JER-06, REQ-ACT-02 |
| `jerarquia.forzado-momento` — Orden que entra en vigor cuando su destino franquea: el destino evoluciona y el forzado se aplica en la evolución siguiente | provisional (especificada, sin contraste normativo) | decisión del responsable, chat 27-10-2026, 7.2 B (coherente con 4.3 A y 7.6 B; cierra H-18) | REQ-JER-06 |
| `jerarquia.forzado-recinto` — Forzar un recinto con la encapsulante inactiva: el forzado se ignora mientras siga inactiva. Vaciar por forzado un recinto con la encapsulante activa no se preguntó y se detiene (U-08) | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 7.4 C | REQ-JER-06 |
| `jerarquia.forzado-tiempo` — Temporizadores de un parcial forzado: siguen contando | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 7.3 A | REQ-JER-06 |
| `jerarquia.macro-inicial` — Etapas iniciales dentro de una expansión: se admiten y están activas al arrancar | provisional (especificada, sin contraste normativo) | decisión del responsable, chat 27-10-2026, 7.7 A | REQ-JER-04 |
| `jerarquia.macro-ramas` — Salir de una macroetapa con otras ramas activas: se desactivan todas las etapas de la expansión | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 7.5 A | REQ-JER-06 |
| `jerarquia.macroetapas` — Macroetapas: llegar activa la entrada; salir exige la salida; XM por la expansión | provisional (especificada, sin contraste normativo) | I (U-01), documento 06 y LOC tabla 11; P-IMP-23 | REQ-JER-04 |
| `lotes` — Lotes simultáneos y lotes ordenados con igual tiempo | provisional (especificada, sin contraste normativo) | P | REQ-EVT-02 |
| `parciales.actividad` — activePartial sobre parcial sin hijos | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-JER-01 |
| `parciales.anidados` — Parcial dentro de otro: solo como recinto de una encapsulante o expansión de una macroetapa del parcial dueño; sin encapsulante no compila | provisional (especificada, sin contraste normativo) | decisión del responsable, chat 27-10-2026, 8.1 C (cierra H-08) | REQ-JER-01, REQ-MOD-07 |
| `permanencia.actividad` — Etapa activada y desactivada a la vez permanece activa | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-05 |
| `permanencia.efectos` — Etapa en permanencia activa o reactivada: no ejecuta acciones al activar ni al desactivar y su duración sigue | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 3.1 A, 3.2 A y 3.3 A (cierra H-05) | REQ-SEM-05, REQ-EVT-03 |
| `situacion.inicial.explicita` — Situación inicial = etapas marcadas iniciales | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-01 |
| `situacion.inicial.vacia` — Arranque sin etapas iniciales (no compila) | pendiente / bloqueada | decisión del responsable, comparador 27-10-2026, 6.1 A | REQ-SEM-01, REQ-MOD-04 |
| `temporal.base-compuesta` — Base temporal distinta de entradas o active(etapa) | pendiente / bloqueada | H-09 | REQ-TMP-02 |
| `temporal.coincidencias` — Lote y vencimiento en el mismo instante: primero el vencimiento si el lote cambia su base, si no juntos; un rebote durante la desconexión la mantiene verdadera | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 4.1 A, 4.2 A y 4.3 A (cierra H-17) | REQ-TMP-03 |
| `temporal.delay` — delay(d1,p,d2) ordinario con d1>0 | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-TMP-02 |
| `temporal.delay-cero` — Tiempos de 0 s en un retardo: se quitan al compilar (0s/p es p; 0s/p/7s es p/7s; 8s/p/0s es 8s/p) | provisional (especificada, sin contraste normativo) | decisión del responsable, chat 27-10-2026, 4.4 revisada (A) | REQ-TMP-03 |
| `temporal.duracion-etapa-inicial` — La duración de una etapa inicial cuenta desde τ=0 (oráculos T-12a/T-12c) | provisional (especificada, sin contraste normativo) | I; decisión del responsable, hoja 08 1.4 A | REQ-TMP-02 |
| `temporal.elapsed` — Duración elapsed(etapa) ejecutable | pendiente / bloqueada | no implementada en esta iteración; el valor con la etapa inactiva ya está decidido: 0 (decisión del responsable, comparador 27-10-2026, 4.5 A) | REQ-TMP-02 |
| `temporal.reentrada-virtual` — Salida y reentrada en el mismo instante: la duración de la etapa no se interrumpe | provisional (especificada, sin contraste normativo) | decisión del responsable de producto, 25-10-2026 (P-IMP-18; cierra H-09) | REQ-TMP-02 |
| `temporal.vencimientos-simultaneos` — Varios vencimientos en el mismo instante (independientes del orden) | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-TMP-02 |
| `transiciones.fuente-evento` — Transición fuente con receptividad de evento (primera evolución) | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-MOD-04 |
| `transiciones.fuente-nivel` — Transición fuente con receptividad de nivel (no compila) | pendiente / bloqueada | decisión del responsable, comparador 27-10-2026, 6.2 A | REQ-MOD-04 |
| `transiciones.fuente-repeticion` — Transición fuente por evento: franquea una sola vez por flanco | provisional (especificada, sin contraste normativo) | decisión del responsable, comparador 27-10-2026, 6.3 A | REQ-MOD-04, REQ-EVT-03 |
| `transiciones.sin-lados` — Transición sin precedentes ni siguientes (no compila) | pendiente / bloqueada | decisión del responsable, comparador 27-10-2026, 6.4 A | REQ-MOD-04 |
| `transiciones.sumidero` — Transición sin siguientes | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-MOD-04 |
| `transitorios` — Situaciones virtuales sin pulsos continuos; memorizadas conservadas | provisional (especificada, sin contraste normativo) | I (U-01) | REQ-SEM-06 |

## Materias excluidas por cuestiones críticas abiertas (REQ-NOR-02)

- `eventos.franqueamiento`: U-03
- `eventos.internos`: U-03

## Lecturas seleccionables como hipótesis (P-IMP-15)

Elegir una lectura distinta de la predeterminada no cierra la cuestión ni amplía la cobertura: la ejecución queda marcada con esa hipótesis en su perfil efectivo y en su traza.

- **U-03** (U-03: receptividades con eventos de entrada en evoluciones posteriores del instante); por defecto `situacion-anterior`:
  - `detener`: Detener con D-SEM-PENDIENTE: no se elige
  - `situacion-anterior`: De uno en uno («situación anterior»): el flanco solo franquea las transiciones validadas antes de él
  - `recorrido`: Por ciclo («recorrido»): el flanco vale en todo el recorrido del instante y puede atravesar varias etapas inestables seguidas
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
- **3.1** (U-04: acciones al activar/desactivar de una etapa en permanencia activa); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecuta ninguna
  - `B`: Se ejecutan las dos
- **3.2** (U-04: temporizador de una etapa en permanencia activa o reactivada); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Sigue contando
  - `B`: Vuelve a empezar
- **3.3** (U-04 (H-05): acciones al activar una etapa que ya estaba activa); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecutan
  - `B`: Se ejecutan
- **4.1** (U-06: la base de un retardo cambia exactamente en su vencimiento); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Primero vence el retardo
  - `B`: Primero cambia la entrada (cancela)
- **4.2** (U-06: rebote durante el retardo de desconexión); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: La condición sigue verdadera sin interrupción
  - `B`: Se mantiene el plazo; después vuelve a contar el retardo de conexión
- **4.3** (U-06: lote y vencimiento independientes en el mismo instante); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Juntos en un solo instante
  - `B`: Primero el vencimiento
  - `C`: Primero el lote
  - `D`: Solo se detiene si el resultado depende del orden
- **4.4** (U-06: retardo cero); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: El 0 s se quita: 0s/p es p y 0s/p/7s es p/7s
  - `B`: 0s/p no compila
- **5.2** (U-03: acción por evento en una etapa que se desactiva con ese mismo evento); por defecto `B`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Se ejecuta
  - `B`: No se ejecuta
- **5.3** (U-03: acción por evento en una etapa que se activa con ese mismo evento); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No se ejecuta
  - `B`: Se ejecuta
- **6.1** (U-07: grafcet sin etapas iniciales); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Arranca sin etapas activas
- **6.2** (U-07: transición fuente con receptividad de nivel); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Imposición continua: mientras sea verdadera, mantiene activas sus etapas siguientes
- **6.3** (U-07: transición fuente con flanco en evoluciones posteriores del instante); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Franquea una sola vez por flanco
- **6.4** (U-07: transición sin etapas antes ni después); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: No compila
  - `B`: Se permite y no tiene efecto
- **3.4** (U-04/U-08: encapsulante activada y desactivada a la vez); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Su contenido se mantiene
  - `B`: Su contenido se reinicia con las etapas de activación
- **7.2** (U-08 (H-18): orden que entra en vigor cuando su destino podría evolucionar); por defecto `B`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: El forzado se aplica en esa misma evolución y gana
  - `B`: El destino evoluciona y el forzado se aplica en la evolución siguiente
- **7.3** (U-08: temporizadores de un parcial forzado); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Siguen contando
  - `B`: Se congelan mientras dura el forzado
- **7.4** (U-08: forzar un recinto cuya encapsulante está inactiva); por defecto `C`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Error de diseño: se detiene con error
  - `B`: Se fuerza igualmente
  - `C`: El forzado se ignora mientras la encapsulante esté inactiva
- **7.5** (U-08: salir de una macroetapa con ramas internas aún activas); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Se desactivan todas las etapas de la expansión
  - `B`: Las ramas siguen activas
  - `C`: Error de diseño: se detiene con error
- **7.6** (U-08: desactivar la encapsulante cuando franquea algo en su interior); por defecto `B`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Gana la desactivación: lo interior no tiene efecto
  - `B`: Primero actúa lo interior y después se desactiva
- **7.7** (U-08: etapas iniciales dentro de una expansión); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Se permiten: están activas al arrancar
  - `B`: No se permiten: no compila
- **7.8** (U-08 (H-24): acciones de etapas activadas o desactivadas por un forzado); por defecto `A`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Se ejecutan
  - `B`: No se ejecutan
- **8.1** (H-08: parcial dentro de otro (ownerRef del documento 09)); por defecto `C`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Cuenta también las etapas de los hijos
  - `B`: Solo las etapas propias
  - `C`: Sin encapsulante no se admite: no compila
- **8.2** (H-10: leer una salida continua en una expresión); por defecto `C`:
  - `detener`: Detener: la cuestión sigue abierta
  - `A`: Prohibido: no compila
  - `B`: Valor de la situación estable anterior
  - `C`: Valor según la situación inestable del momento
