# 05. Trazabilidad requisito ↔ implementación ↔ prueba

Documento **generado** por `tools/generar_trazabilidad.py`; no editar a mano.

Generado el 2026-10-28T19:15:36+00:00 · Python 3.13.17 · Linux-6.18.44-fc-v180-x86_64-with-glibc2.39 · 251 pruebas ejecutadas, 0 fallos, 0 errores.

Leyenda: ✔ pasa · ◆ pasa según una decisión del responsable sobre una U (no es el oráculo del documento 11, que pedía detener; contraste U-01 pendiente) · ⛔ bloqueo por U verificado (el oráculo semántico sigue abierto) · ◐ parcial · ∅ capacidad no implementada en esta iteración (se verifica que no se ejecuta) · — no ejecutado · ✘ falla. **Un ✔ con oráculo I es provisional (U-01): no prueba conformidad.**

## Resumen

| Categoría del requisito | Nº |
|---|---|
| Implementado (P), verificable ya (`IMPL-P`) | 42 |
| Implementado como provisional (I; U-01) (`IMPL-I`) | 15 |
| Parcial (`PARCIAL`) | 9 |
| Implementado según decisión del responsable (U cerrada; contraste U-01 pendiente) (`IMPL-DEC`) | 5 |
| Bloqueado por U (bloqueo implementado) (`BLOQ-U`) | 0 |
| Pendiente de iteración (estructura hecha) (`PEND-ITER`) | 0 |
| Pendiente de interfaz (`PEND-UI`) | 5 |
| Pendiente de plataforma (U-10) (`PEND-PLT`) | 1 |
| Revisión documental (`DOC`) | 5 |

| Estado de los 102 casos del documento 11 | Nº |
|---|---|
| BLOQUEO VERIFICADO | 1 |
| NO EJECUTADO | 6 |
| PARCIAL | 7 |
| PASA | 76 |
| PASA SEGÚN DECISIÓN | 12 |

Pruebas suplementarias S-xx: 151 casos, 154 pruebas, 154 pasan.

## Requisitos

| Requisito | Clase/prio. | Doc. | Categoría | Implementación | Casos | Nota |
|---|---|---|---|---|---|---|
| REQ-ALC-01 | P/alta | 01 | PARCIAL | editor, persistence, engine | T-21a ◐, T-24d ◐ | Ciclo principal sin servicios de terceros verificado sin interfaz (T-24d); falta la interfaz |
| REQ-ALC-02 | P/crítica | 01 | DOC | tools/comprobar_paquete.py | R-02 (documental), S-PKG ✔ | Parte automatizable de R-02: el paquete conserva exactamente los doce Markdown con sus huellas |
| REQ-ALC-03 | P/alta | 01 | IMPL-P | profile, declaration | R-01 (documental), S-DECL ✔ | Cada capacidad marcada provisional / no soportada con su motivo |
| REQ-NOR-01 | P/crítica | 01 | IMPL-P | profile, persistence, declaration | T-22e ✔, S-DECL ✔ | Base normativa declarada en el manifiesto; ejes de versión separados; no se sustituye silenciosamente |
| REQ-NOR-02 | P/crítica | 01 | IMPL-P | declaration | R-01 (documental), S-CMP01 ✔, S-CMP04 ✔, S-CMP05 ✔, S-OPT03a ✔, S-DECL ✔ | La declaración excluye toda materia con U crítica y nunca afirma conformidad; R-01 sigue siendo documental |
| REQ-CR-01 | P/crítica | 02 | DOC | tools/paquete.py | R-01 (documental) | Las fuentes y localizadores se conservan en el paquete; la matriz enlaza cada requisito con su documento |
| REQ-CR-02 | P/crítica | 02 | DOC | — | R-02 (documental), S-PKG ✔ | Esta implementación se ha hecho solo con el paquete; ver declaración de procedencia en README |
| REQ-CR-03 | P/crítica | 02 | DOC | — | R-02 (documental) | No se ha detectado contaminación; procedimiento descrito en README |
| REQ-CR-04 | P/alta | 02 | DOC | tests | R-01 (documental) | Ningún oráculo procede de otro producto; los oráculos son los del documento 11 |
| REQ-MOD-01 | P/crítica | 03 | IMPL-P | model, persistence | T-21b ✔, T-22b ✔ | IDs únicos, propietario y referencias existentes; duplicados/huérfanos impiden simular |
| REQ-MOD-02 | I/crítica | 03 | IMPL-I | model, editor | T-21b ✔ | D-ALTERNANCIA; enlaces etapa→etapa como borrador (P-IMP-05) |
| REQ-MOD-03 | P/crítica | 03 | IMPL-P | editor | T-21c ✔, S-EDI07 ✔, S-EDI17 ✔, S-EDI19 ✔, S-EDI20 ✔, S-EDI21 ✔, S-EDI23 ✔, S-EDI24 ✔, S-EDI26 ✔ | Solo se conecta por operación explícita; la geometría no crea relaciones |
| REQ-MOD-04 | I/alta | 03 | IMPL-DEC | model, engine | T-03c ✔, T-10e ◆, T-01d ◆, S-U07 ✔, S-OPT03e ✔ | Sumideros I. U-07 cerrada por el responsable (comparador, 27-10-2026, P-IMP-22): fuente por evento una vez por flanco (6.3 A); sin etapas iniciales, fuente de nivel y transición sin lados no compilan (6.1 A, 6.2 A, 6.4 A) |
| REQ-MOD-05 | P/alta | 03 | IMPL-P | model, expressions, editor | T-09c ✔ | Texto libre conservado como descriptivo; D-EXP-PENDIENTE localizado |
| REQ-MOD-06 | P/crítica | 03 | IMPL-P | model, editor, engine | T-04c ✔, T-21d ✔ | Renombrar, mover u ordenar no cambia observables ni revisión semántica (H-13) |
| REQ-MOD-07 | I/alta | 03 | IMPL-I | model, hierarchy | T-18c ✔, T-19c ✔, S-H08 ✔ | Propiedad única de expansiones y recintos; recursión rechazada; la estructura se ejecuta (P-IMP-23) |
| REQ-SEM-01 | I/crítica | 04 | PARCIAL | engine | T-01a ✔, T-01b ✔, T-01c ✔, T-01d ◆, S-CMP02 ✔, S-U09 ✔, S-H07 ✔ | Situación inicial explícita y su cierre causal en τ=0: acciones al activar las iniciales, evolución inicial y temporizadores desde τ=0 (hoja 08, 1.1–1.4, P-IMP-19). Inicio vacío: no compila (6.1 A, P-IMP-22). Abierto: iniciales dentro de jerarquías (U-08) |
| REQ-SEM-02 | I/crítica | 04 | IMPL-I | engine | T-02c ✔, T-02a ✔, T-02b ✔, T-06a ✔, T-06b ✔ | Validación y receptividad; imposición jerárquica pendiente de iteración |
| REQ-SEM-03 | I/crítica | 04 | IMPL-I | engine | T-03a ✔, T-03b ✔, T-03c ✔, T-03d ✔, T-06c ✔ | Cambio conjunto de precedentes y siguientes |
| REQ-SEM-04 | I/crítica | 04 | IMPL-I | engine | T-04a ✔, T-04b ✔, T-04c ✔, T-06a ✔, T-06b ✔, T-13d ✔ | Conjunto simultáneo completo; sin prioridad por orden |
| REQ-SEM-05 | I/crítica | 04 | IMPL-DEC | engine | T-05a ✔, T-05b ◆, S-H05 ✔ | Actividad I. Efectos decididos por el responsable (comparador, 27-10-2026, P-IMP-22): en permanencia o reactivación no se ejecutan acciones al activar ni al desactivar y la duración sigue (3.1 A, 3.2 A, 3.3 A; cierra H-05) |
| REQ-SEM-06 | I/crítica | 04 | IMPL-I | engine | T-07a ✔, T-07b ✔, T-07c ✔, S-EJ01 ✔, S-H09 ✔ | Etapas inestables sin pulso continuo; memorizadas conservadas; eventos en el recorrido según la lectura 5.1 (P-IMP-22) |
| REQ-SEM-07 | P/crítica | 04 | IMPL-P | engine | T-08a ✔, T-08b ✔, S-08a ✔, S-H09b ✔, S-OPT03c ✔ | D-LIM-EVOL recuperable, τ sin avanzar, sin falsa estabilidad (T-08a con su oráculo original desde la respuesta 1.2 A; S-08a) |
| REQ-SEM-08 | P/crítica | 04 | IMPL-P | engine, trace | T-04c ✔, T-23b ✔, T-24a ◐, S-U06 ✔ | Mismos observables con independencia de recorrido, geometría y control; entre sistemas: U-10 |
| REQ-SEM-09 | U/crítica | 04 | IMPL-DEC | engine | T-10d ◆, T-11b ⛔, T-15c ◆, S-CMP01 ✔, S-CMP02 ✔, S-CMP03 ✔, S-CMP05 ✔, S-APP08 ✔, S-U05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔ | U-05 (P-IMP-20) y U-03, U-04, U-06, U-07 (comparador, 27-10-2026, P-IMP-22) cerradas por el responsable; cada lectura sigue siendo seleccionable, «detener» incluida en el banco (P-IMP-15, P-IMP-21; el simulador de escritorio no la ofrece, P-IMP-30). Siguen deteniéndose los eventos internos y de franqueamiento (U-03), 0s/p/d2 y los vencimientos que dependen del orden (U-06) |
| REQ-ACT-01 | I/crítica | 05 | IMPL-I | engine | T-14a ✔, T-14b ✔, T-14c ✔, T-07a ✔, T-12c ✔, S-EDI100 ✔, S-EDI40 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI58 ✔, S-EDI62 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI75 ✔, S-EDI82 ✔, S-EDI83 ✔, S-EDI84 ✔, S-EDI86 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI91 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI39 ✔, S-EDI98 ✔, S-H10 ✔ | Disyunción sobre situación efectiva; una salida continua leída en una expresión vale según la situación del momento (comparador, 8.2 C; cierra H-10) |
| REQ-ACT-02 | I/crítica | 05 | IMPL-I | engine | T-15a ✔, T-15b ✔, T-01c ✔, T-07b ✔, T-07c ✔, T-18e ◐, S-CMP02 ✔, S-EJ02 ✔, S-U03 ✔, S-U05b ✔, S-U09 ✔, S-H07 ✔ | Memorizadas por activación, desactivación y evento, también virtuales |
| REQ-ACT-03 | P/crítica | 05 | IMPL-P | model, engine | T-16a ✔, T-16b ✔, S-ESC01 ✔, S-ESC02 ✔ | D-ESCRITURA-CONFLICTO con autores y valores, sin prioridad oculta; un conflicto seguro impide compilar (P-IMP-16) y el resto se detiene en ejecución |
| REQ-ACT-04 | I/crítica | 05 | IMPL-I | model | T-16c ✔ | D-MODO-SALIDA en validación |
| REQ-ACT-05 | U/crítica | 05 | IMPL-DEC | engine, model | T-15c ◆, T-16d ◆, S-EJ01 ✔, S-U05 ✔, S-U05b ✔, S-ESC02 ✔ | Hoja 08, 2.1 C, 2.2 B, 2.3 A, 2.4 A y 2.5 A (P-IMP-20): conflicto si dos escriben a la vez, dependencia cruzada no compila, lo asignado se ve en el mismo instante y vale la última asignación |
| REQ-EVT-01 | I/crítica | 05 | IMPL-I | engine | T-10a ✔, T-10b ✔, T-10c ✔, T-10e ◆, S-EJ02 ✔ | Flancos sobre entradas en la 1.ª evolución; sin retención ni consumo exclusivo |
| REQ-EVT-02 | P/crítica | 05 | IMPL-P | scenario | T-10b ✔, T-13a ✔ | Lotes simultáneos frente a lotes ordenados; D-LOTE |
| REQ-EVT-03 | U/crítica | 05 | PARCIAL | model, engine | T-10d ◆, T-11a ◆, T-11b ⛔, T-05b ◆, S-CMP02 ✔, S-EJ01 ✔, S-EJ02 ✔, S-U03 ✔, S-H05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔, S-OPT03e ✔ | Evento en el recorrido: lectura «situación anterior» por defecto; acciones por evento solo si la etapa estaba activa y no sale con él (comparador, 27-10-2026, 5.1–5.3, P-IMP-22; H-23). Eventos internos y de franqueamiento: U-03, bloqueados |
| REQ-EXP-01 | P/alta | 05 | IMPL-P | expressions, values | T-09a ✔, T-09b ✔, T-09c ✔, S-DEC ✔, S-EXP ✔ | Tipos exactos, unidades, precedencia; sintaxis de literales P-IMP-06 |
| REQ-EXP-02 | P/crítica | 05 | IMPL-P | expressions, engine | T-09d ✔ | Evaluación pura |
| REQ-TMP-01 | P/crítica | 05 | IMPL-P | timeutil, values | T-12d ✔, T-24b ✔, S-EDI41 ✔, S-EDI46 ✔, S-DEC ✔ | µs exactos, rango 0..2^63-1, sin redondeo |
| REQ-TMP-02 | I/crítica | 05 | IMPL-I | engine, model | T-12a ✔, T-12b ✔, T-12c ✔, T-12e ✔, T-12f ✔, T-13d ✔, S-EDI75 ✔, S-U09 ✔, S-12a ✔, S-H09 ✔, S-H09b ✔ | delay ordinario, limitadas, retardadas; duración de etapa inicial según T-12a/T-12c (H-02); salida y reentrada en el mismo instante sin interrumpir la duración (P-IMP-18); bases compuestas no soportadas (H-09) |
| REQ-TMP-03 | U/crítica | 05 | PARCIAL | engine, model | T-13b ◆, T-13c ◆, T-20a ◆, S-CMP02 ✔, S-U06 ✔ | Decidido (comparador, 27-10-2026, P-IMP-22): caída en el vencimiento → primero el vencimiento (4.1 A); rebote → sigue verdadera (4.2 A); lote y vencimiento independientes → juntos (4.3 A; cierra H-17); los tiempos de 0 s se quitan: 0s/p es p y 0s/p/7s es p/7s (chat, 4.4 revisada, P-IMP-28). Sigue en U-06: vencimientos simultáneos que dependen del orden |
| REQ-JER-01 | I/crítica | 06 | IMPL-I | engine, model | T-04c ✔, T-20b ✔, S-H08 ✔ | Partición sin orden y XG derivada de sus etapas. Un parcial dentro de otro solo como recinto o expansión; sin encapsulante no compila (chat 27-10-2026, 8.1 C; cierra H-08) |
| REQ-JER-02 | I/crítica | 06 | IMPL-I | hierarchy, engine | T-17a ✔, T-17b ◐ | Forzado explícito, actual (captura), vacío e inicial; el destino no evoluciona mientras está vigente; la retirada libera desde la situación resultante (documento 06, P-IMP-23). Momento, temporizadores, recintos y acciones: U-08 (7.2–7.4, 7.8) |
| REQ-JER-03 | P/crítica | 06 | IMPL-P | model, hierarchy | T-17c ✔, T-17d ✔ | Ciclos D-JERARQUIA-CICLO; conflicto posible avisado al validar y detenido al ejecutar (D-FORZADO-CONFLICTO) sin prioridad por ID |
| REQ-JER-04 | I/crítica | 06 | IMPL-I | model, hierarchy, engine | T-18a ✔, T-18b ✔, T-18c ✔, T-18e ◐ | Relación expandida: llegar activa la entrada, salir exige la salida; XM por la expansión; reentrada sin borrar memorias (P-IMP-23). Ramas residuales: U-08 (7.5). Iniciales en la expansión: se admiten (7.7 A, P-IMP-24) |
| REQ-JER-05 | I/crítica | 06 | IMPL-I | model, hierarchy | T-19a ✔, T-19b ✔, T-19c ✔ | Al arrancar, iniciales; al reentrar, enlaces de activación; al salir, se desactivan todos los descendientes (P-IMP-23). Encapsulante en permanencia: el contenido se mantiene (comparador, 3.4 A) |
| REQ-JER-06 | U/crítica | 06 | IMPL-DEC | hierarchy | T-18d ◆, T-20a ◆, T-20c ◆ | Cerradas por el responsable: 7.2 B, 7.3 A, 7.4 C, 7.5 A, 7.6 B, 7.7 A y 7.8 A (P-IMP-24 a P-IMP-26). Vaciar por forzado un recinto con su encapsulante activa no se preguntó y se detiene (U-08) |
| REQ-JER-07 | P/alta | 06 | PEND-UI | — | T-21g —, T-24a ◐ | Plegado y navegación pertenecen a la vista |
| REQ-EDT-01 | P/alta | 07 | PARCIAL | editor, persistence | T-21a ◐, S-EDI03 ✔, S-EDI04 ✔, S-EDI05 ✔, S-EDI08 ✔, S-EDI28 ✔, S-EDI32 ✔, S-APP06 ✔ | Crear, abrir, guardar y duplicar sin interfaz; el simulador de escritorio abre proyectos y modelos, crea un grafcet nuevo, lo guarda y lo reabre (P-IMP-29, P-IMP-32), y pregunta antes de descartar cambios; sin duplicar desde la interfaz |
| REQ-EDT-02 | P/alta | 07 | IMPL-P | editor | T-21b ✔, T-21c ✔, S-EDI42 ✔, S-EDI50 ✔, S-EDI51 ✔, S-EDI54 ✔, S-EDI56 ✔, S-EDI57 ✔, S-EDI64 ✔, S-EDI97 ✔, S-EDI03 ✔, S-EDI100 ✔, S-EDI101 ✔, S-EDI10 ✔, S-EDI11 ✔, S-EDI12 ✔, S-EDI13 ✔, S-EDI14 ✔, S-EDI15 ✔, S-EDI17 ✔, S-EDI18 ✔, S-EDI19 ✔, S-EDI21 ✔, S-EDI24 ✔, S-EDI25 ✔, S-EDI28 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI31 ✔, S-EDI33 ✔, S-EDI34 ✔, S-EDI35 ✔, S-EDI36 ✔, S-EDI38 ✔, S-EDI41 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI52 ✔, S-EDI53 ✔, S-EDI55 ✔, S-EDI58 ✔, S-EDI59 ✔, S-EDI60 ✔, S-EDI61 ✔, S-EDI62 ✔, S-EDI63 ✔, S-EDI65 ✔, S-EDI66 ✔, S-EDI67 ✔, S-EDI68 ✔, S-EDI69 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI82 ✔, S-EDI87 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI99 ✔, S-EDI16 ✔, S-EDI45 ✔, S-EDI46 ✔, S-EDI47 ✔, S-EDI01 ✔ | Insertar, conectar, editar; borrador inválido guardable; en la interfaz de escritorio: etapas, transiciones, enlaces y receptividades de un secuencial (P-IMP-32); selección, salto y repetición con el ratón (P-IMP-33), flechas y recorridos manuales persistentes (P-IMP-35), tramos verticales mínimos y transición que se agarra sin sacar rama (P-IMP-36), una flecha por lazo, imán y arrastre desde la paleta (P-IMP-37), receptividades con un programador por bloques y acciones desde la etapa (P-IMP-38); panel de acciones y jerarquías, pendientes |
| REQ-EDT-03 | P/alta | 07 | PARCIAL | editor | T-04c ✔, T-21c ✔, S-EDI10 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI37 ✔, S-EDI01 ✔ | Mover, alinear, distribuir y deshacer; zoom en la vista del simulador (P-IMP-29); en la interfaz de escritorio, mover con rejilla de 20 y deshacer o rehacer (P-IMP-32); alinear y distribuir, pendientes en la interfaz |
| REQ-EDT-04 | P/crítica | 07 | IMPL-P | editor | T-21e ✔ | Copiar/pegar con IDs nuevos y decisión explícita de referencias externas |
| REQ-EDT-05 | P/crítica | 07 | IMPL-P | editor | T-21f ✔, S-EDI05 ✔ | Transacciones atómicas; fallo fuera del historial; rehacer descartado |
| REQ-EDT-06 | P/crítica | 07 | IMPL-P | editor | T-21d ✔, S-EDI08 ✔, S-EDI43 ✔ | Renombrar sin cambiar ID, usos actualizados, colisión diagnosticada, búsqueda con ruta |
| REQ-EDT-07 | P/alta | 07 | IMPL-P | editor | T-09b ✔, T-21d ✔, S-EDI54 ✔, S-EDI40 ✔, S-EDI43 ✔, S-EDI49 ✔, S-EDI66 ✔, S-EDI79 ✔, S-EDI80 ✔, S-EDI85 ✔, S-EDI94 ✔, S-EDI96 ✔, S-EDI39 ✔, S-APP14 ✔, S-APP16 ✔ | Diccionario de variables y usos afectados por un cambio; en la interfaz de escritorio, panel de variables (nombre, papel, tipo, valor inicial, unidad, usos) y acciones de etapa con su diálogo (P-IMP-38) |
| REQ-EDT-08 | P/alta | 07 | PEND-UI | — | T-21g — | Navegación jerárquica |
| REQ-EDT-09 | P/alta | 07 | IMPL-P | diagnostics | T-21b ✔, T-09c ✔, S-EDI06 ✔, S-EDI14 ✔, S-EDI73 ✔, S-EDI76 ✔, S-EDI77 ✔, S-EDI78 ✔, S-EDI80 ✔, S-EDI81 ✔, S-EDI96 ✔, S-EDI02 ✔, S-ESC01 ✔ | Código, gravedad, elemento, evidencia y corrección; panel de diagnósticos del editor de escritorio con clic que selecciona y centra el elemento (P-IMP-32); foco de teclado pendiente |
| REQ-EDT-10 | P/crítica | 07 | IMPL-P | persistence | T-22d ✔, S-EDI09 ✔ | Recuperación separada cada 30 s si hay cambios, sin sobrescritura; conectada al editor de escritorio, que la ofrece al arrancar (P-IMP-32) |
| REQ-EDT-11 | P/alta | 07 | PEND-UI | — | T-21h — | Exportación SVG/PDF no implementada en esta iteración (el simulador guarda el dibujo como PNG) |
| REQ-EDT-12 | P/alta | 07 | PEND-UI | — | T-21g —, T-25a ◐ | Diagramas extensos: vista general, zoom y filtros |
| REQ-EDT-13 | P/alta | 07 | PEND-UI | — | T-26a —, T-26b — | Teclado y accesibilidad |
| REQ-EDT-14 | P/crítica | 07 | IMPL-P | editor, engine | T-23d ✔, S-EDI03 ✔, S-EDI73 ✔ | Edición semántica = revisión nueva; la ejecución conserva la suya |
| REQ-SIM-01 | P/crítica | 08 | IMPL-P | engine | T-23a ✔, T-23b ✔ | Estados de sesión, pausas en frontera completa, microavance, puntos antes/después |
| REQ-SIM-02 | P/crítica | 08 | IMPL-P | scenario, engine | T-10b ✔, T-23c ✔, S-APP04 ✔ | Escenarios y entradas manuales registradas con origen y ordinal |
| REQ-SIM-03 | P/alta | 08 | IMPL-P | engine | T-02a ✔, T-02b ✔, T-02c ✔, T-23a ✔, S-EDI22 ✔, S-EDI27 ✔, S-EDI32 ✔, S-EDI40 ✔, S-EDI78 ✔, S-APP14 ✔, S-APP15 ✔, S-APP05 ✔, S-APP09 ✔, S-APP10 ✔, S-APP11 ✔, S-APP12 ✔, S-APP13 ✔, S-APP16 ✔ | Observación de actividad, validación, receptividad y franqueamiento |
| REQ-SIM-04 | P/crítica | 08 | IMPL-P | engine | T-23c ✔, T-22f ✔, T-23f ✔, S-OPT03d ✔ | Instantánea con Z completo y compatibilidad exacta; dentro de recorrido D-INSTANTANEA-FASE |
| REQ-SIM-05 | P/crítica | 08 | IMPL-P | trace | T-04a ✔, T-22g ✔, S-OPT03b ✔ | Traza con conjuntos E, causas, cierre y digest |
| REQ-SIM-06 | P/crítica | 08 | IMPL-P | engine | T-09d ✔, T-23b ✔ | Observar y pausar no modifican comportamiento |
| REQ-SIM-07 | P/crítica | 08 | IMPL-P | engine | T-23e ✔ | Intervención E en pausa estable, rama auditable |
| REQ-SIM-08 | P/alta | 08 | IMPL-P | diagnostics, engine | T-08a ✔, T-08b ✔, T-16a ✔, S-08a ✔ | Evidencia y corrección recomendada en cada diagnóstico |
| REQ-DAT-01 | P/crítica | 09 | IMPL-P | model, persistence, ids | T-22b ✔, T-21e ✔, S-EDI73 ✔, S-EDI77 ✔, S-EDI82 ✔, S-EDI91 ✔, S-EDI98 ✔, S-H12 ✔ | Identidades, referencias y propiedad; nombres hexadecimales (H-12) |
| REQ-DAT-02 | P/crítica | 09 | IMPL-P | persistence | T-22a ✔, S-CMP04 ✔, S-EDI04 ✔, S-APP01 ✔, S-APP06 ✔ | Ida y vuelta conserva significado, notas y vista (formato 0.1 provisional, U-11) |
| REQ-DAT-03 | P/crítica | 09 | IMPL-P | persistence | T-22c ✔, T-22e ✔, S-APP02 ✔ | Versión mayor/menor, desconocidos y migración con copia e informe |
| REQ-DAT-04 | P/crítica | 09 | IMPL-P | engine | T-22f ✔, T-23c ✔, T-23f ✔, S-OPT03d ✔ | Instantánea íntegra y compatibilidad exacta; campos U no aplicables declarados |
| REQ-DAT-05 | P/crítica | 09 | IMPL-P | canonical, timeutil | T-24a ◐, T-24b ✔, S-CAN ✔ | Representación canónica y SHA-256 independientes de región |
| REQ-DAT-06 | P/crítica | 09 | IMPL-P | canonical, persistence, expressions | T-25b ✔, T-25c ✔, S-CAN ✔ | Sin código ejecutable, sin rutas fuera de raíz, límites previos |
| REQ-DAT-07 | P/crítica | 09 | IMPL-P | persistence | T-22d ✔ | Guardado atómico con diario; recuperación del último válido |
| REQ-DAT-08 | P/crítica | 09 | IMPL-P | model, trace | T-09c ✔, T-22g ✔ | Divergencia texto-significado y trazas truncadas |
| REQ-ARQ-01 | P/crítica | 10 | IMPL-P | todo el núcleo | T-23b ✔, T-24a ◐ | Todo el contrato se verifica sin interfaz (esta batería) |
| REQ-PLT-01 | P/crítica | 10 | PEND-PLT | trace | T-24a ◐ | Trazas canónicas deterministas en Windows; comparación en macOS/Linux pendiente (U-10) |
| REQ-PLT-02 | P/alta | 10 | PARCIAL | timeutil, persistence | T-24b ✔, T-24c ◐, S-H12 ✔ | Región, Unicode, rutas y mayúsculas verificados en Windows; otros sistemas U-10 |
| REQ-PLT-03 | P/alta | 10 | PARCIAL | todo el núcleo | T-24d ◐, T-24e — | Sin conexión verificado; versión portable para Windows sin instalador (P-IMP-29); instalación y actualización pendientes (U-10) |
| REQ-PLT-04 | P/alta | 10 | PARCIAL | model, persistence, tools/medir_presupuestos.py | T-25a ◐, T-25d — | Límites aplicados; medición indicativa, no ratificada (U-10) |
| REQ-ROB-01 | P/crítica | 10 | IMPL-P | model, engine, persistence | T-08a ✔, T-08b ✔, T-25a ◐, S-08a ✔ | Límites de datos y de evolución diagnosticados sin alterar significado |
| REQ-ROB-02 | P/crítica | 10 | IMPL-P | persistence, canonical | T-22d ✔, T-25b ✔, T-25c ✔, S-APP02 ✔ | Archivos fallidos preservan la última revisión válida y no ejecutan cargas |

## Casos del documento 11

| Caso | Requisitos | Oráculo (11) | Resultado | Pruebas | Observación |
|---|---|---|---|---|---|
| T-01a | REQ-SEM-01 | I | PASA (oráculo I) | `test_T01a_situacion_inicial_explicita` |  |
| T-01b | REQ-SEM-01 | I | PASA (oráculo I) | `test_T01b_orden_de_archivo_irrelevante` |  |
| T-01c | REQ-SEM-01, REQ-ACT-02 | P/I parcial | PASA (oráculo P/I parcial) | `test_T01c_restaurar_conserva_memoria_reiniciar_la_pone_a_cero` | restaurar y reiniciar; las acciones al activar las iniciales ya se ejecutan (1.1 A) |
| T-01d | REQ-SEM-01, REQ-MOD-04 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T01d_sin_iniciales_no_compila` | comparador, 27-10-2026, 6.1 A: sin etapas iniciales no compila; no se inventa etapa inicial. Con «detener», U-07 |
| T-02a | REQ-SEM-02 | I | PASA (oráculo I) | `test_T02a_receptividad_sin_validacion` |  |
| T-02b | REQ-SEM-02 | I | PASA (oráculo I) | `test_T02b_validacion_sin_receptividad` |  |
| T-02c | REQ-SEM-02 | I | PASA (oráculo I) | `test_T02c_franqueamiento_inmediato` |  |
| T-03a | REQ-SEM-03 | I | PASA (oráculo I) | `test_T03a_divergencia_en_y_activa_el_conjunto` |  |
| T-03b | REQ-SEM-03 | I | PASA (oráculo I) | `test_T03b_sincronizacion_desactiva_conjuntamente` |  |
| T-03c | REQ-SEM-03, REQ-MOD-04 | I | PASA (oráculo I) | `test_T03c_transicion_sumidero` |  |
| T-03d | REQ-SEM-03 | I | PASA (oráculo I) | `test_T03d_rama_no_recorrida_no_contribuye` |  |
| T-04a | REQ-SEM-04 | I | PASA (oráculo I) | `test_T04a_transiciones_independientes_simultaneas` |  |
| T-04b | REQ-SEM-04 | I | PASA (oráculo I) | `test_T04b_sin_exclusion_automatica` |  |
| T-04c | REQ-SEM-08, REQ-MOD-06 | P | PASA (oráculo P) | `test_T04c_presentacion_orden_y_parciales_no_cambian_observables` |  |
| T-05a | REQ-SEM-05 | I | PASA (oráculo I) | `test_T05a_permanencia_activa` |  |
| T-05b | REQ-SEM-05, REQ-EVT-03 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T05b_efectos_de_permanencia_decididos` | comparador, 27-10-2026, 3.1 A: la permanencia no ejecuta acciones (no se asumen dos cambios de actividad); p sigue a 1 y u vuelve a franquear en la evolución siguiente. Con «detener», U-04 |
| T-06a | REQ-SEM-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T06a_sincronizacion_incompleta` |  |
| T-06b | REQ-SEM-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T06b_recorrido_hasta_sincronizar` |  |
| T-06c | REQ-SEM-03 | I | PASA (oráculo I) | `test_T06c_paralelismo_y_sincronizacion` |  |
| T-07a | REQ-SEM-06, REQ-ACT-01 | I | PASA (oráculo I) | `test_T07a_etapa_virtual_sin_pulso` |  |
| T-07b | REQ-SEM-06, REQ-ACT-02 | I | PASA (oráculo I) | `test_T07b_memorizada_al_activar_etapa_virtual` |  |
| T-07c | REQ-SEM-06, REQ-ACT-02 | I | PASA (oráculo I) | `test_T07c_memorizada_al_desactivar_etapa_virtual` |  |
| T-08a | REQ-SEM-07, REQ-ROB-01 | P | PASA (oráculo P) | `test_T08a_ciclo_instantaneo_al_arrancar` | oráculo original ejecutable desde la respuesta 1.2 A de la hoja 08 (cierra H-03) |
| T-08b | REQ-SEM-07 | P | PASA (oráculo P) | `test_T08b_espera_estable_no_es_divergencia` |  |
| T-09a | REQ-EXP-01 | P | PASA (oráculo P) | `test_T09a_precedencia` |  |
| T-09b | REQ-EXP-01, REQ-EDT-07 | P | PASA (oráculo P) | `test_T09b_unidades_y_tipos` |  |
| T-09c | REQ-MOD-05, REQ-DAT-08 | P | PASA (oráculo P) | `test_T09c_texto_pendiente_y_divergencia_se_guardan` |  |
| T-09d | REQ-EXP-02, REQ-SIM-06 | P | PASA (oráculo P) | `test_T09d_observar_no_modifica_estado` |  |
| T-10a | REQ-EVT-01 | I | PASA (oráculo I) | `test_T10a_sin_flanco_al_arrancar` |  |
| T-10b | REQ-EVT-01, REQ-EVT-02 | I/P | PASA (oráculo I/P) | `test_T10b_lote_simultaneo_frente_a_lotes_ordenados` |  |
| T-10c | REQ-EVT-01 | I | PASA (oráculo I) | `test_T10c_flanco_no_se_retiene` |  |
| T-10d | REQ-EVT-03, REQ-SEM-09 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T10d_alcance_causal_del_evento_situacion_anterior` | comparador, 27-10-2026, 5.1: lectura «situación anterior», de las alternativas del caso (B o C) queda en B. Con «detener», U-03 |
| T-10e | REQ-EVT-01, REQ-MOD-04 | I/B parcial | PASA SEGÚN DECISIÓN (en el documento 11: I/B parcial, depende de U) | `test_T10e_fuentes_por_evento_una_vez_por_flanco` | parte I: E={t,u} con el mismo evento; repetición decidida (comparador, 27-10-2026, 6.3 A): una vez por flanco. Con «detener», U-07 |
| T-11a | REQ-EVT-03 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T11a_permanencia_y_franqueamiento_separados` | E={t,u} en la primera evolución; la permanencia de B no ejecuta acciones (comparador, 27-10-2026, 3.1 A). Con «detener», U-04 |
| T-11b | REQ-EVT-03, REQ-SEM-09 | B | BLOQUEO VERIFICADO | `test_T11b_evento_de_franqueamiento_bloqueo_U03` | U-03 |
| T-12a | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12a_retardo_exacto_sin_cuantizacion` | duración de etapa inicial según el oráculo (H-02); lectura de «B a 2000001» (H-11) |
| T-12b | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12b_pulso_breve_no_activa` |  |
| T-12c | REQ-TMP-02, REQ-ACT-01 | I | PASA (oráculo I) | `test_T12c_accion_limitada` | duración de etapa inicial según el oráculo (H-02) |
| T-12d | REQ-TMP-01 | P | PASA (oráculo P) | `test_T12d_tiempo_exacto_rechazos` |  |
| T-12e | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12e_retardo_de_conexion_y_desconexion` |  |
| T-12f | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12f_reentrada_inicia_intervalo_nuevo` |  |
| T-13a | REQ-EVT-02 | P | PASA (oráculo P) | `test_T13a_lote_con_dos_escrituras` |  |
| T-13b | REQ-TMP-03 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T13b_caida_exacta_en_el_vencimiento_franquea` | comparador, 27-10-2026, 4.1 A: primero el vencimiento, franquea (también con p verdadera desde el arranque, 1.3 A). Con «detener», U-06 |
| T-13c | REQ-TMP-03 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T13c_rebote_durante_desconexion_sigue_verdadera` | comparador, 27-10-2026, 4.2 A: la nueva subida anula la desconexión; verdadera a 5 s sin nuevo plazo. Con «detener», U-06 |
| T-13d | REQ-TMP-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T13d_vencimientos_simultaneos_misma_frontera` |  |
| T-14a | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14a_disyuncion_de_contribuciones` |  |
| T-14b | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14b_continua_sin_memoria` |  |
| T-14c | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14c_condicion_continua_con_evento` | segunda parte = T-07a |
| T-15a | REQ-ACT-02 | I | PASA (oráculo I) | `test_T15a_memorizada_conserva_valor` |  |
| T-15b | REQ-ACT-02 | I | PASA (oráculo I) | `test_T15b_accion_por_evento_cuenta_eventos_reales` |  |
| T-15c | REQ-ACT-05, REQ-SEM-09 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T15c_lecturas_cruzadas_dependencia_cruzada` | decisión 2.2 B de la hoja 08: dependencia cruzada, no compila; en ejecución se detiene. El error no está entre las lecturas (5,2), (5,5) y (2,2) que lista el caso |
| T-16a | REQ-ACT-03 | P | PASA (oráculo P) | `test_T16a_conflicto_de_escritura` |  |
| T-16b | REQ-ACT-03 | I | PASA (oráculo I) | `test_T16b_escrituras_iguales` |  |
| T-16c | REQ-ACT-04 | I | PASA (oráculo I) | `test_T16c_modos_mezclados` |  |
| T-16d | REQ-ACT-05 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T16d_dos_incrementos_conflicto` | decisión 2.1 C de la hoja 08: de las alternativas del caso (n=1, n=2 o conflicto), conflicto |
| T-17a | REQ-JER-02 | I | PASA (oráculo I) | `test_T17a_forzado_explicito_vacio_e_inicial` | forzado explícito, vacío e inicial (P-IMP-23) |
| T-17b | REQ-JER-02 | I/B parcial | PARCIAL | `test_T17b_forzado_actual_captura_y_retirada` | captura, mantenimiento y retirada verificados (I); los efectos coincidentes quedan decididos (7.2 B, 7.8 A) pero el caso no los ejercita |
| T-17c | REQ-JER-03 | P | PASA (oráculo P) | `test_T17c_conflicto_de_forzado` | conflicto avisado al validar y detenido al ejecutar, sin prioridad |
| T-17d | REQ-JER-03 | P | PASA (oráculo P) | `test_T17d_ciclo_de_forzado` |  |
| T-18a | REQ-JER-04 | I | PASA (oráculo I) | `test_T18a_macroetapa_entrada_y_salida` | entrada, salida y XM (P-IMP-23) |
| T-18b | REQ-JER-04 | I | PASA (oráculo I) | `test_T18b_recorrido_de_expansion_y_reentrada` | recorrido virtual de la expansión y reentrada (P-IMP-23) |
| T-18c | REQ-JER-04, REQ-MOD-07 | P/I | PASA (oráculo P/I) | `test_T18c_propiedad_unica_y_recursion` | estructura: propiedad, anidamiento y recursión |
| T-18d | REQ-JER-06 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T18d_rama_residual` | comparador 27-10-2026, 7.5 A: se desactivan todas las etapas de la expansión. Con «detener», U-08 |
| T-18e | REQ-JER-04, REQ-ACT-02 | I/B parcial | PARCIAL | `test_T18e_reentrada_de_macroetapa_y_memoria` | parte I verificada: E en cada llegada, n=1 y n=2 sin reinicio de memoria (P-IMP-23); el caso pide confirmar U-08 antes de cerrar |
| T-19a | REQ-JER-05 | I | PASA (oráculo I) | `test_T19a_inicio_salida_y_reentrada_por_enlace_de_activacion` | inicio por iniciales, salida y reentrada por enlace de activación (P-IMP-23) |
| T-19b | REQ-JER-05 | I | PASA (oráculo I) | `test_T19b_encapsulacion_anidada` | activación anidada y desactivación de descendientes (P-IMP-23) |
| T-19c | REQ-JER-05, REQ-MOD-07 | I/P | PASA (oráculo I/P) | `test_T19c_propietario_unico_y_coherencia_inicial` |  |
| T-20a | REQ-JER-06, REQ-TMP-03 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T20a_desactivacion_y_vencimiento_interior` | chat 27-10-2026, 7.6 B: primero actúa lo interior y después se desactiva H. Con «detener», U-08 |
| T-20b | REQ-JER-01 | I/P | PASA (oráculo I/P) | `test_T20b_particion_sin_orden_y_actividad_derivada` |  |
| T-20c | REQ-JER-06 | B | PASA SEGÚN DECISIÓN (en el documento 11: B, depende de U) | `test_T20c_forzado_contra_recinto` | comparador 27-10-2026, 7.4 C: el forzado se ignora con la encapsulante inactiva. Vaciar un recinto activo no se preguntó y sigue detenido (U-08) |
| T-21a | REQ-ALC-01, REQ-EDT-01 | P | PARCIAL | `test_T21a_crear_guardar_reabrir_duplicar` | sin interfaz: el diálogo de cierre con cambios queda pendiente |
| T-21b | REQ-MOD-01, REQ-MOD-02, REQ-EDT-02, REQ-EDT-09 | P/I | PASA (oráculo P/I) | `test_T21b_diagnosticos_separados_borrador_guardable` |  |
| T-21c | REQ-MOD-03, REQ-EDT-02, REQ-EDT-03 | P | PASA (oráculo P) | `test_T21c_cruzar_mover_alinear_no_conecta` |  |
| T-21d | REQ-MOD-06, REQ-EDT-06, REQ-EDT-07 | P | PASA (oráculo P) | `test_T21d_renombrar_conserva_ids_y_traza` |  |
| T-21e | REQ-EDT-04, REQ-DAT-01 | P | PASA (oráculo P) | `test_T21e_copiar_pegar_con_referencia_externa` |  |
| T-21f | REQ-EDT-05 | P | PASA (oráculo P) | `test_T21f_borrar_encapsulante_y_deshacer_atomico` |  |
| T-21g | REQ-EDT-08, REQ-EDT-12, REQ-JER-07 | P | NO EJECUTADO | — | requiere interfaz gráfica |
| T-21h | REQ-EDT-11 | P | NO EJECUTADO | — | exportación SVG/PDF no implementada en esta iteración |
| T-22a | REQ-DAT-02 | P | PASA (oráculo P) | `test_T22a_ida_y_vuelta_conserva_significado_notas_y_vista` |  |
| T-22b | REQ-DAT-01, REQ-MOD-01 | P | PASA (oráculo P) | `test_T22b_referencia_rota_propietario_contradictorio_clave_duplicada` |  |
| T-22c | REQ-DAT-03 | P | PASA (oráculo P) | `test_T22c_versiones_y_desconocidos` |  |
| T-22d | REQ-DAT-07, REQ-EDT-10, REQ-ROB-02 | P | PASA (oráculo P) | `test_T22d_guardado_interrumpido`, `test_T22d_recuperacion_separada` |  |
| T-22e | REQ-NOR-01, REQ-DAT-03 | P | PASA (oráculo P) | `test_T22e_migracion_y_ejes_de_version` |  |
| T-22f | REQ-DAT-04, REQ-SIM-04 | P | PASA (oráculo P) | `test_T22f_restaurar_exige_compatibilidad_exacta` |  |
| T-22g | REQ-DAT-08, REQ-SIM-05 | P | PASA (oráculo P) | `test_T22g_traza_truncada_o_alterada` |  |
| T-23a | REQ-SIM-01, REQ-SIM-03 | P | PASA (oráculo P) | `test_T23a_pausa_antes_del_conjunto` |  |
| T-23b | REQ-SIM-01, REQ-SIM-06, REQ-ARQ-01, REQ-SEM-08 | P | PASA (oráculo P) | `test_T23b_continuo_microavances_y_puntos_de_parada` |  |
| T-23c | REQ-SIM-02, REQ-SIM-04 | P | PASA (oráculo P) | `test_T23c_instantanea_continuar_y_restaurar` |  |
| T-23d | REQ-EDT-14 | P | PASA (oráculo P) | `test_T23d_edicion_durante_ejecucion_crea_revision` |  |
| T-23e | REQ-SIM-07 | P | PASA (oráculo P) | `test_T23e_intervencion_de_depuracion` |  |
| T-23f | REQ-SIM-04, REQ-DAT-04 | P | PASA (oráculo P) | `test_T23f_instantanea_dentro_de_un_recorrido` |  |
| T-24a | REQ-PLT-01, REQ-DAT-05 | P | PARCIAL | `test_T24a_trazas_canonicas_deterministas` | determinismo verificado en Windows; comparación entre sistemas pendiente de U-10 |
| T-24b | REQ-PLT-02, REQ-TMP-01 | P | PASA (oráculo P) | `test_T24b_configuracion_regional` |  |
| T-24c | REQ-PLT-02 | P | PARCIAL | `test_T24c_rutas_unicode_e_ids_que_difieren_en_mayusculas` | verificado en Windows (NTFS, insensible a mayúsculas); otros sistemas U-10 |
| T-24d | REQ-PLT-03, REQ-ALC-01 | P | PARCIAL | `test_T24d_sin_conexion` | núcleo sin acceso de red; la exportación no existe aún |
| T-24e | REQ-PLT-03 | P | NO EJECUTADO | — | instalación, actualización y reversión: empaquetado pendiente de U-10 |
| T-25a | REQ-PLT-04, REQ-ROB-01 | P | PARCIAL | `test_T25a_limites` | límites y rechazo controlado verificados; medición de tiempos pendiente de U-10 |
| T-25b | REQ-DAT-06, REQ-ROB-02 | P | PASA (oráculo P) | `test_T25b_script_operador_desconocido_y_ruta_externa` |  |
| T-25c | REQ-DAT-06, REQ-ROB-02 | P | PASA (oráculo P) | `test_T25c_profundidad_y_documento_corrupto` |  |
| T-25d | REQ-PLT-04 | P | NO EJECUTADO | — | requiere equipo de referencia (U-10); medición indicativa en tools/medir_presupuestos.py |
| T-26a | REQ-EDT-13 | P | NO EJECUTADO | — | requiere interfaz gráfica |
| T-26b | REQ-EDT-13 | P | NO EJECUTADO | — | requiere interfaz gráfica |

## Pruebas suplementarias (diseñadas por la implementación)

No sustituyen oráculos del paquete; cubren hallazgos, bloqueos U y reglas P internas.

| Caso | Requisitos | Resultado | Prueba | Descripción |
|---|---|---|---|---|
| S-08a | REQ-ROB-01, REQ-SEM-07, REQ-SIM-08 | pasa | `test_S08a_limite_de_evolucion_recuperable` | variante de T-08a disparada por un lote (H-03). |
| S-12a | REQ-TMP-02 | pasa | `test_S12a_retardo_tras_activacion_no_inicial` | variante de T-12a independiente de H-02 (activación por transición a 1 s). |
| S-APP01 | REQ-DAT-02 | pasa | `test_SAPP01_abrir_lo_guardado` | un ejemplo guardado como proyecto se abre igual (modelo y posiciones) y simula |
| S-APP02 | REQ-DAT-03, REQ-ROB-02 | pasa | `test_SAPP02_abrir_rechaza_lo_que_no_es_modelo` | un documento de otra familia no se abre; uno con campos semánticos desconocidos |
| S-APP03 |  | pasa | `test_SAPP03_colocacion_automatica` | cada etapa, macroetapa y transición tiene posición, dos etapas no |
| S-APP04 | REQ-SIM-02 | pasa | `test_SAPP04_entradas_numericas` | una entrada numérica escrita a mano admite coma decimal y respeta tipo, escala y rango. |
| S-APP05 | REQ-SIM-03 | pasa | `test_SAPP05_ejemplos_en_la_ventana` | cada ejemplo se carga y se dibuja; un clic en una entrada hace evolucionar el grafcet como en el banco. |
| S-APP06 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SAPP06_guardar_y_abrir_en_la_ventana` | «Guardar como proyecto» y «Abrir modelo» conservan el modelo y su dibujo. |
| S-APP07 |  | pasa | `test_SAPP07_lecturas_reinician` | Cambiar una lectura reinicia la simulación y se señala como distinta de la decidida. |
| S-APP08 | REQ-SEM-09 | pasa | `test_SAPP08_ajustes_y_lecturas` | «Ajustes» (entre Simulación y Ayuda) tiene las lecturas; el diálogo no ofrece «detener» y el |
| S-APP09 | REQ-SIM-03 | pasa | `test_SAPP09_tiempo_real_pausa_y_paso` | al cargar, el tiempo real está activo; pausa, paso y reinicio funcionan. |
| S-APP10 | REQ-SIM-03 | pasa | `test_SAPP10_temporizador_en_dibujo_y_tabla` | «temporizada», con E1 activa y 1 s transcurrido, muestra «1 s / 3 s» junto a la receptividad y en |
| S-APP11 | REQ-SIM-03 | pasa | `test_SAPP11_paneles_plegables` | el panel derecho y el inferior se pliegan del todo con su flecha y desde «Ver»; el estado se guarda. |
| S-APP12 | REQ-SIM-03 | pasa | `test_SAPP12_zoom_se_conserva` | «+», «−» y la rueda con Ctrl cambian el zoom; un refresco lo conserva; «Ajustar» vuelve a encajar. |
| S-APP13 | REQ-SIM-03 | pasa | `test_SAPP13_tiempos_truncados_a_dos_decimales` | lo que lleva un temporizador y τ se muestran truncados a la baja a 2 decimales; el preset, tal cual. |
| S-APP14 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP14_nombres_en_vez_de_id` | un modelo hecho con el editor (ID internos) se dibuja y se traza con los nombres: |
| S-APP15 | REQ-SIM-03 | pasa | `test_SAPP15_ejemplos_no_cambian` | en los ejemplos el ID es el nombre: mostrar nombres no cambia nada del dibujo ni de la traza. |
| S-APP16 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP16_ventana_con_nombres` | un modelo del editor, guardado y abierto en la ventana, muestra nombres en el dibujo, |
| S-CAN | REQ-DAT-05, REQ-DAT-06 | pasa | `test_SCAN_formato_canonico` | reglas de representación canónica y lectura estricta (09). |
| S-CMP01 | REQ-NOR-02, REQ-SEM-09 | pasa | `test_SCMP01_catalogo_coherente` | cada lectura del comparador existe en el perfil, tiene su texto y se comprueba. |
| S-CMP02 | REQ-ACT-02, REQ-EVT-03, REQ-SEM-01, REQ-SEM-09, REQ-TMP-03 | pasa | `test_SCMP02_cada_lectura_hace_lo_que_anuncia` | cada alternativa evoluciona como dice su panel. |
| S-CMP03 | REQ-SEM-09 | pasa | `test_SCMP03_las_lecturas_se_distinguen` | en cada ejemplo, las lecturas no acaban todas igual (si no, el ejemplo no sirve para elegir). |
| S-CMP04 | REQ-DAT-02, REQ-NOR-02 | pasa | `test_SCMP04_registro_de_decisiones` | la respuesta se guarda con su origen; los bloques 1 y 2 vienen de la hoja 08. |
| S-CMP05 | REQ-NOR-02, REQ-SEM-09 | pasa | `test_SCMP05_lecturas_por_defecto_son_las_respuestas_incorporadas` | las respuestas incorporadas (hoja 08 y comparador) son las lecturas por defecto; lo abierto se detiene. |
| S-DEC | REQ-EXP-01, REQ-TMP-01 | pasa | `test_SDEC_decimales_y_enteros_exactos` | sin redondeo silencioso ni desbordamiento. |
| S-DECL | REQ-ALC-03, REQ-NOR-01, REQ-NOR-02 | pasa | `test_SDECL_declaracion_sin_conformidad` | la declaración excluye U críticas y no afirma conformidad. |
| S-EDI01 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI01_parcial_raiz_etiquetas_y_agrupar` | el grafcet nuevo tiene el parcial raíz «g»; las etiquetas nuevas son 0, 1… (solo el |
| S-EDI02 | REQ-EDT-09 | pasa | `test_SEDI02_comprobar_receptividad_sin_cambiar_el_modelo` | un texto mal escrito se diagnostica sin tocar el modelo; las variables que faltan se listan. |
| S-EDI03 | REQ-EDT-01, REQ-EDT-02, REQ-EDT-14 | pasa | `test_SEDI03_crear_enlazar_y_simular` | E0 (inicial) → t1 «marcha» → E1 → t2 «paro» → E0 se crea con el ratón, |
| S-EDI04 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SEDI04_guardar_abrir_y_simular` | el grafcet creado se guarda como proyecto, se abre y simula igual; en Editar se |
| S-EDI05 | REQ-EDT-01, REQ-EDT-05 | pasa | `test_SEDI05_deshacer_rehacer_mover_y_borrar` | un arrastre es una sola operación de deshacer; borrar avisa de lo que arrastra y se |
| S-EDI06 | REQ-EDT-09 | pasa | `test_SEDI06_receptividad_mal_escrita_y_diagnosticos` | una receptividad que no se interpreta se conserva como texto, se diagnostica con su corrección, |
| S-EDI07 | REQ-MOD-03 | pasa | `test_SEDI07_enlaces_en_borrador_y_añadir_debajo` | dos elementos del mismo tipo quedan como borrador con su diagnóstico; «añadir debajo» crea |
| S-EDI08 | REQ-EDT-01, REQ-EDT-06 | pasa | `test_SEDI08_etiquetas_y_cambios_sin_guardar` | renombrar una etapa conserva su identidad y actualiza el dibujo; con cambios sin |
| S-EDI09 | REQ-EDT-10 | pasa | `test_SEDI09_recuperacion_automatica` | con cambios sin guardar se copia la edición cada 30 s y se ofrece recuperarla; guardar la borra. |
| S-EDI10 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI10_el_ratón_real_y_el_dibujo` | los clics del ratón sobre el dibujo llegan al editor; la selección y las marcas se |
| S-EDI100 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI100_limitada_con_condicion_a_medias_pasa_a_borrador` | la condición a medias (con huecos) de una limitada de un fichero antiguo la deja como |
| S-EDI101 | REQ-EDT-02 | pasa | `test_SEDI101_renombrar_con_la_seleccion_cambiada_no_hace_nada` | un editingFinished que llega tarde (la selección cambió, o el elemento ya no existe, por ejemplo tras |
| S-EDI11 | REQ-EDT-02 | pasa | `test_SEDI11_puntos_de_union` | etapas y transiciones tienen puntos de unión arriba y abajo; al acercarse se marcan y del punto |
| S-EDI12 | REQ-EDT-02 | pasa | `test_SEDI12_paleta_arrastrar_y_sin_pedir_receptividad` | los elementos de la paleta, a la izquierda, se arrastran al dibujo; una transicion se coloca sin |
| S-EDI13 | REQ-EDT-02 | pasa | `test_SEDI13_propiedades_de_la_etapa` | al seleccionar una etapa, el panel de la izquierda muestra su etiqueta y su tipo, editables. |
| S-EDI14 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI14_propiedades_de_la_transicion` | la receptividad se arma con botones, variables, comparaciones y temporizadores; lo que |
| S-EDI15 | REQ-EDT-02 | pasa | `test_SEDI15_transiciones_mas_altas_de_acertar` | el area de una transicion es mas alta que su trazo: se acierta sin punteria. |
| S-EDI16 | REQ-EDT-02 | pasa | `test_SEDI16_notacion_del_usuario` | ↑a, ↓a y X1 se traducen a la sintaxis del núcleo y vuelven; los espacios se ignoran al escribir y |
| S-EDI17 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI17_barra_de_simultaneidad` | la simultaneidad es una barra de doble trazo que se arrastra desde la paleta, se |
| S-EDI18 | REQ-EDT-02 | pasa | `test_SEDI18_enlaces_seleccionables_flecha_y_quitar` | un enlace se selecciona con un clic en su trazo; si va de abajo arriba se dibuja con flecha; se |
| S-EDI19 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI19_alternativas_con_el_raton` | la alternativa (O) no es un elemento: se construye con el raton. Una segunda transicion |
| S-EDI20 | REQ-MOD-03 | pasa | `test_SEDI20_sentido_del_enlace_segun_el_trazo` | de arriba abajo, el enlace no lleva flecha; de abajo arriba, si (sale solo del trazo). |
| S-EDI21 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI21_abrir_ramas_con_el_raton_de_verdad` | con eventos de raton reales sobre el dibujo (pulsar, mover, soltar): arrastrar de un punto |
| S-EDI22 | REQ-SIM-03 | pasa | `test_SEDI22_ejemplo_alternativas` | el ejemplo «alternativas» se simula, se dibuja con la flecha de union y se puede editar. |
| S-EDI23 | REQ-MOD-03 | pasa | `test_SEDI23_el_punto_de_arriba_recibe_y_el_enlace_entra_por_arriba` | lo que se arrastra desde el punto de arriba de una transicion es lo que le llega (viene de la etapa |
| S-EDI24 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI24_entrada_de_transicion_a_enlace_de_salida` | arrastrar la entrada a un enlace de salida crea otra alternativa, no una simultaneidad. |
| S-EDI25 | REQ-EDT-02 | pasa | `test_SEDI25_arrastrar_desde_linea_de_seleccion` | clic selecciona un enlace; arrastre desde él abre otra rama en una transacción. |
| S-EDI26 | REQ-MOD-03 | pasa | `test_SEDI26_geometria_comun_retorno_y_movimiento` | uniones comunes, retorno fuera de la etapa, flecha automática y recorridos iguales en Qt/web. |
| S-EDI27 | REQ-SIM-03 | pasa | `test_SEDI27_ejemplos_seleccion_salto_repeticion` | las ramas construidas ejecutan selección, salto y repetición sin cambiar el motor. |
| S-EDI28 | REQ-EDT-01, REQ-EDT-02 | pasa | `test_SEDI28_salto_inverso_guardar_y_reabrir` | arrastrar la entrada de una etapa a una salida crea el salto; persiste y se deshace entero. |
| S-EDI29 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI29_flecha_arrastrar_y_ocultar_sin_cambiar_modelo` | mover y ocultar la flecha son presentación; un arrastre, un deshacer. La flecha sigue |
| S-EDI30 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI30_recolocar_retorno_y_mover_etapa` | tiradores para carril y alturas; extremos conectados al mover etapas. El recorrido no |
| S-EDI31 | REQ-EDT-02 | pasa | `test_SEDI31_flecha_union_horizontal_independiente` | la flecha de unión no sale por defecto (el enlace baja); se muestra, se mueve y se oculta; la |
| S-EDI32 | REQ-EDT-01, REQ-SIM-03 | pasa | `test_SEDI32_dibujo_manual_persistencia_y_simulacion` | los ajustes sobreviven a guardar, abrir, simular y guardar otra copia. |
| S-EDI33 | REQ-EDT-02 | pasa | `test_SEDI33_una_flecha_por_lazo_y_ninguna_al_bajar` | por defecto solo lleva flecha un enlace que sube, y una por lazo, en el enlace más largo (figura del |
| S-EDI34 | REQ-EDT-02 | pasa | `test_SEDI34_agarrar_una_transicion_la_mueve` | el trazo de una transición se agarra para moverla; sus puntos de unión quedan al final de su |
| S-EDI35 | REQ-EDT-02 | pasa | `test_SEDI35_tramo_vertical_minimo_en_etapas_y_transiciones` | un enlace siempre sale de la etapa y llega a la transición (y al revés) con un tramo vertical |
| S-EDI36 | REQ-EDT-02 | pasa | `test_SEDI36_sin_escalones_en_el_tramo_horizontal` | un carril guardado cuando el enlace daba un rodeo no deja un escalón cuando ya no hace falta; con |
| S-EDI37 | REQ-EDT-03 | pasa | `test_SEDI37_iman_alinea_con_el_elemento_enlazado` | al mover una etapa o una transición a dos pasos de rejilla o menos de la vertical de un elemento |
| S-EDI38 | REQ-EDT-02 | pasa | `test_SEDI38_panel_izquierdo_plegable_y_figura_de_la_paleta` | el panel izquierdo (paleta y propiedades) se pliega como los otros, desde su flecha o desde Ver, y |
| S-EDI39 | REQ-ACT-01, REQ-EDT-07 | pasa | `test_SEDI39_acciones_y_variables_en_el_nucleo` | una acción se cambia de arriba abajo conservando su ID y su lugar, se ordena y se quita |
| S-EDI40 | REQ-ACT-01, REQ-EDT-07, REQ-SIM-03 | pasa | `test_SEDI40_contador_por_flanco_con_el_editor` | el ejemplo «contador-flanco» del responsable, hecho con el editor |
| S-EDI41 | REQ-EDT-02, REQ-TMP-01 | pasa | `test_SEDI41_retardo_3s_X1_con_el_asistente` | con la etapa X1 en bloques y el bloque «temporizar» encima, la receptividad es 3s/X1, |
| S-EDI42 | REQ-EDT-02 | pasa | `test_SEDI42_ida_y_vuelta_texto_arbol_texto` | el texto se vuelve árbol de bloques y el árbol vuelve al mismo texto, con paréntesis solo donde la |
| S-EDI43 | REQ-EDT-06, REQ-EDT-07 | pasa | `test_SEDI43_panel_de_variables` | el diccionario muestra nombre, papel y tipo (sin inicial, unidad ni usos); renombrar |
| S-EDI44 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI44_acciones_desde_el_dibujo` | botón derecho en una etapa: «Añadir acción…»; la acción se dibuja a su derecha; un |
| S-EDI45 | REQ-EDT-02 | pasa | `test_SEDI45_constantes_1_y_0` | en la notación del usuario se ve 1 y 0 y se guarda true y false, solo como operando booleano |
| S-EDI46 | REQ-EDT-02, REQ-TMP-01 | pasa | `test_SEDI46_retardo_con_parentesis_anidados` | la condición de un retardo puede llevar paréntesis anidados (3s/(a AND (b OR c)), |
| S-EDI47 | REQ-EDT-02 | pasa | `test_SEDI47_aviso_de_x1_ambiguo` | si existen la etapa E1 y la etapa 1, X1 se sigue resolviendo a E1, pero se señala que podría ser |
| S-EDI48 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI48_dialogo_de_acciones_vista_previa_y_avisos` | el diálogo de acciones ya no lleva programador (la condición y el evento se programan en |
| S-EDI49 | REQ-EDT-07 | pasa | `test_SEDI49_memorias_en_la_interfaz` | las variables internas se llaman «memorias» en la interfaz; el papel guardado sigue siendo |
| S-EDI50 | REQ-EDT-02 | pasa | `test_SEDI50_soltar_envolver_sustituir_y_quitar` | un bloque suelto en un hueco lo encaja; uno que envuelve sobre un hueco ocupado deja el bloque que |
| S-EDI51 | REQ-EDT-02 | pasa | `test_SEDI51_desplegables_y_campos` | el desplegable de una variable ofrece las booleanas de su papel, el de una etapa todas las etapas y |
| S-EDI52 | REQ-EDT-02 | pasa | `test_SEDI52_texto_y_bloques_sincronizados` | lo escrito en el campo de texto aparece en bloques; un texto que no se puede analizar no cambia los |
| S-EDI53 | REQ-EDT-02 | pasa | `test_SEDI53_deshacer_cambios_de_bloques` | en el panel de la transición cada cambio de bloques es una operación del editor y se deshace con su |
| S-EDI54 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI54_paleta_por_categorias` | la paleta tiene siete categorías con su color; las memorias son las variables de papel |
| S-EDI55 | REQ-EDT-02 | pasa | `test_SEDI55_ventana_ampliada_sincronizada` | «⤢ Ampliar» abre el programador en una ventana propia, no modal, con el mismo texto; los cambios de |
| S-EDI56 | REQ-EDT-02 | pasa | `test_SEDI56_cabe_a_200_px_y_crece_en_alto` | el área y la paleta caben a 200 px sin barra horizontal; el área crece en alto al estrecharse y |
| S-EDI57 | REQ-EDT-02 | pasa | `test_SEDI57_raton_clic_en_piezas_y_arrastres_recibidos` | un clic en un desplegable abre su menú y en un campo, su editor (Intro aplica, Esc descarta); |
| S-EDI58 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI58_receptividad_1_y_accion_entera` | una receptividad «1» se guarda como true y se valida sin D-TIPO; el valor de una acción |
| S-EDI59 | REQ-EDT-02 | pasa | `test_SEDI59_pestana_bloques_en_el_panel_inferior` | el programador de la receptividad es la pestaña «Bloques» del panel inferior, solo al editar; |
| S-EDI60 | REQ-EDT-02 | pasa | `test_SEDI60_bloques_y_texto_sincronizados_en_la_pestana` | un cambio de bloques escribe el texto del panel izquierdo y es una operación del editor (Ctrl+Z); |
| S-EDI61 | REQ-EDT-02 | pasa | `test_SEDI61_boton_bloques_abajo_si_el_panel_esta_plegado` | con el panel inferior plegado no se despliega solo; el panel de la transición ofrece «Bloques |
| S-EDI62 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI62_ficha_accion_en_la_paleta` | la carpeta «Acciones» ofrece la ficha «Continua» con su figura (el lado izquierdo, bajo |
| S-EDI63 | REQ-EDT-02 | pasa | `test_SEDI63_y_y_o_con_colores_distintos` | «y» y «o» siguen en Operadores pero se dibujan con colores distintos entre sí y del resto de |
| S-EDI64 | REQ-EDT-02 | pasa | `test_SEDI64_disposicion_en_columnas` | categorías como carpetas en una columna (las siete, con su color), a su derecha la columna de |
| S-EDI65 | REQ-EDT-02 | pasa | `test_SEDI65_arrastre_de_las_paletas` | la paleta «Elementos» se arrastra (el arrastre se activa después de fijar el modo de iconos y el |
| S-EDI66 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI66_variables_nuevas_al_dia_en_el_programador` | al crear, renombrar, quitar o cambiar de papel una variable (panel Variables, diálogo de |
| S-EDI67 | REQ-EDT-02 | pasa | `test_SEDI67_carpetas_en_su_orden_y_temporizadores` | las carpetas del programador van en este orden: Operadores, Entradas, Salidas, Etapas (X), |
| S-EDI68 | REQ-EDT-02 | pasa | `test_SEDI68_receptividad_en_la_pestana_con_texto_de_solo_lectura` | toda la receptividad está en la pestaña Bloques (texto de la fórmula, «Escrito», «Se dibuja» y |
| S-EDI69 | REQ-EDT-02 | pasa | `test_SEDI69_lazo_de_seleccion` | arrastrar desde un hueco dibuja un rectángulo y selecciona lo que queda dentro (etapas, |
| S-EDI70 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI70_soltar_la_ficha_accion_crea_una_accion_suelta` | la ficha «Continua», soltada en cualquier sitio, crea una acción continua suelta sin |
| S-EDI71 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI71_enlazar_una_accion_a_una_etapa_separarla_y_deshacer` | arrastrar del punto de unión de una acción suelta a una etapa la une: con variable pasa a |
| S-EDI72 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI72_tipo_de_accion_por_el_boton_derecho` | el botón derecho en una acción (suelta o unida) ofrece un submenú «Tipo de acción» con |
| S-EDI73 | REQ-DAT-01, REQ-EDT-09, REQ-EDT-14 | pasa | `test_SEDI73_guardar_abrir_con_borradores_avisos_y_deshacer` | los borradores de acción se guardan en la presentación |
| S-EDI74 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI74_dialogo_editar_de_una_accion_suelta_o_sin_completar` | «Editar…» de una acción suelta abre el diálogo de acciones (con el límite de tiempo de |
| S-EDI75 | REQ-ACT-01, REQ-TMP-02 | pasa | `test_SEDI75_accion_limitada_se_dibuja_como_condicion_not_d_sobre_x` | una acción limitada en el tiempo se dibuja como en la norma, con su límite como una |
| S-EDI76 | REQ-EDT-09 | pasa | `test_SEDI76_mensajes_informativos_y_barra_de_estado` | un aviso informativo de la edición no sale en rojo (el rojo es de los errores); el mensaje temporal |
| S-EDI77 | REQ-DAT-01, REQ-EDT-09 | pasa | `test_SEDI77_borradores_danados_al_abrir` | un `draftActions` corrupto no rompe la apertura: se descartan los dañados (no son |
| S-EDI78 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SEDI78_anchos_de_los_paneles_laterales` | al editar, el panel izquierdo mide de lo que piden las dos columnas de la paleta (su |
| S-EDI79 | REQ-EDT-07 | pasa | `test_SEDI79_tabla_de_variables_nombre_papel_tipo` | la tabla tiene solo Nombre, Papel y Tipo; se ofrecen Booleana, Entera y Decimal con 2 decimales; |
| S-EDI80 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI80_variable_nueva_sin_nombre` | «Nueva variable» añade una fila en blanco que solo existe en la interfaz; al escribir un |
| S-EDI81 | REQ-EDT-09 | pasa | `test_SEDI81_parpadeo_naranja_en_los_errores` | un rechazo, un intento de simular con errores, un clic en Diagnósticos (también en el aviso de un |
| S-EDI82 | REQ-ACT-01, REQ-DAT-01, REQ-EDT-02 | pasa | `test_SEDI82_colocacion_de_las_acciones_de_una_etapa` | por defecto, cajas pegadas en fila; el botón derecho en la etapa ofrece |
| S-EDI83 | REQ-ACT-01 | pasa | `test_SEDI83_condicion_y_banderita_encima_sin_solaparse` | en las tres colocaciones, la condición (trazo vertical a la izquierda de la caja y su texto), la |
| S-EDI84 | REQ-ACT-01 | pasa | `test_SEDI84_banco_dibuja_las_colocaciones_como_el_editor` | tools/dibujo.js (banco y comparador) lee `actionLayout` de la vista y dibuja las tres colocaciones |
| S-EDI85 | REQ-EDT-07 | pasa | `test_SEDI85_papel_y_tipo_como_texto_con_desplegable_al_editar` | Papel y Tipo se ven como texto; al editar la celda aparece un desplegable con las opciones y al elegir se |
| S-EDI86 | REQ-ACT-01 | pasa | `test_SEDI86_limitada_dibuja_x_de_la_etiqueta_no_del_id` | la condición de una acción limitada (`NOT 3s/X…`) usa la etiqueta de la etapa (X0), no su ID interno, |
| S-EDI87 | REQ-EDT-02 | pasa | `test_SEDI87_los_elementos_solo_se_colocan_arrastrando` | no hay modo herramienta para colocar: un clic en una ficha solo muestra su ayuda, un clic en el |
| S-EDI88 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI88_carpeta_de_acciones_con_sus_cinco_fichas` | la paleta tiene dos carpetas, «Elementos» (etapa, transición, simultaneidad) y |
| S-EDI89 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI89_punto_derecho_de_la_etapa_y_union_con_acciones_sueltas` | la etapa tiene un punto de unión en el centro de su lado derecho (visible al pasar el |
| S-EDI90 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI90_pegar_una_accion_al_lado_de_otra_con_iman` | soltar (o mover) una acción suelta de modo que toque el lado derecho de otra acción de la |
| S-EDI91 | REQ-ACT-01, REQ-DAT-01 | pasa | `test_SEDI91_grupos_sueltos_se_mueven_y_se_unen_juntos` | varias acciones sueltas pegadas forman un grupo suelto (`grupo` y `orden` en la |
| S-EDI92 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI92_el_enlace_de_las_acciones_se_selecciona_y_se_elimina` | el trazo que une la etapa con sus acciones se selecciona con un clic (se resalta); Supr |
| S-EDI93 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI93_condicion_y_evento_de_una_accion_en_la_pestana_bloques` | al seleccionar una acción condicionada (o por evento, o una continua limitada de un |
| S-EDI94 | REQ-ACT-01, REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI94_evento_acciones_sueltas_limitada_y_crear_las_que_faltan` | la pestaña Bloques programa también el evento de una acción, la condición de |
| S-EDI95 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI95_el_dialogo_editar_conserva_condicion_evento_y_limite` | el diálogo Editar no lleva programador y conserva la condición y el evento de la acción; |
| S-EDI96 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI96_nombres_de_variable_reservados` | en la interfaz se rechaza, con mensaje y parpadeo, un nombre de variable que no se puede |
| S-EDI97 | REQ-EDT-02 | pasa | `test_SEDI97_y_y_o_de_varias_entradas` | los bloques «y» y «o» llevan un «+» al final que añade otro hueco (y un «×» en los huecos vacíos de |
| S-EDI98 | REQ-ACT-01, REQ-DAT-01 | pasa | `test_SEDI98_acciones_sueltas_en_grupo_en_el_nucleo` | el editor guarda en `presentation.draftActions` los grupos de acciones sueltas (`grupo`, |
| S-EDI99 | REQ-EDT-02 | pasa | `test_SEDI99_y_y_o_con_muchos_operandos` | un «y» o un «o» de 10, 11 o 26 operandos (las claves de los huecos no chocan con la clase del nodo): |
| S-EJ01 | REQ-ACT-05, REQ-EVT-03, REQ-SEM-06 | pasa | `test_SEJ01_contador_en_etapa_inestable` | ejemplo del responsable; la etapa inestable 2 suma en CT y vuelve a 1 mientras CT < 3. |
| S-EJ02 | REQ-ACT-02, REQ-EVT-01, REQ-EVT-03 | pasa | `test_SEJ02_contador_por_flanco_en_una_etapa` | ejemplo del responsable; una cuenta por cada subida de I02 con 1 activa, ninguna en 0. |
| S-ESC01 | REQ-ACT-03, REQ-EDT-09 | pasa | `test_SESC01_conflictos_seguros_no_compilan` | activación/activación, desactivación/desactivación, activación/desactivación y misma etapa. |
| S-ESC02 | REQ-ACT-03, REQ-ACT-05 | pasa | `test_SESC02_no_son_conflictos_seguros` | la misma constante, etapas en secuencia y eventos distintos no impiden compilar. |
| S-EXP | REQ-EXP-01 | pasa | `test_SEXP_comparacion_encadenada_y_tipos` | comparaciones encadenadas rechazadas; sin conversión booleano↔número. |
| S-H05 | REQ-EVT-03, REQ-SEM-05 | pasa | `test_SH05_activar_etapa_ya_activa_no_ejecuta_sus_acciones` | hallazgo H-05, cerrado por el comparador (3.3 A). Con «detener», U-04. |
| S-H07 | REQ-ACT-02, REQ-SEM-01 | pasa | `test_SH07_memoria_inicial_no_nula_no_compila` | hoja 08, 1.5 A (cierra H-07); otro valor inicial se pone al activar la etapa inicial. |
| S-H08 | REQ-JER-01, REQ-MOD-07 | pasa | `test_SH08_parcial_dentro_de_otro` | hallazgo H-08, cerrado por el responsable (8.1 C): sin encapsulante no compila; como recinto, sí. |
| S-H09 | REQ-SEM-06, REQ-TMP-02 | pasa | `test_SH09_reentrada_en_el_mismo_instante_conserva_la_duracion` | P-IMP-18 (cierra H-09); la salida y reentrada sin tiempo no reinicia el retardo. |
| S-H09b | REQ-SEM-07, REQ-TMP-02 | pasa | `test_SH09b_etapa_que_sale_por_su_temporizador_y_reentra_no_se_estabiliza` | consecuencia de P-IMP-18; ciclo instantáneo sin fin, cortado con D-LIM-EVOL (doc. 04). |
| S-H10 | REQ-ACT-01 | pasa | `test_SH10_leer_salida_continua` | hallazgo H-10, cerrado por el comparador (8.2 C): se lee según la situación del momento, también la inestable. |
| S-H12 | REQ-DAT-01, REQ-PLT-02 | pasa | `test_SH12_id_de_documento_y_nombre_de_fichero` | hallazgo H-12. |
| S-OPT03a | REQ-EVT-03, REQ-NOR-02, REQ-SEM-09 | pasa | `test_SOPT03a_por_defecto_situacion_anterior` | por defecto, la respuesta 5.1 («situación anterior»); «detener» sigue disponible. |
| S-OPT03b | REQ-EVT-03, REQ-SEM-09, REQ-SIM-05 | pasa | `test_SOPT03b_lectura_situacion_anterior` | el evento solo franquea lo validado antes de él → B, con hipótesis en la traza. |
| S-OPT03c | REQ-EVT-03, REQ-SEM-07, REQ-SEM-09 | pasa | `test_SOPT03c_lectura_recorrido` | el evento sigue disponible en el recorrido → C; con reinicio, ciclo sin fin. |
| S-OPT03d | REQ-DAT-04, REQ-SIM-04 | pasa | `test_SOPT03d_instantanea_exige_la_misma_lectura` | no se mezclan instantáneas de lecturas distintas. |
| S-OPT03e | REQ-EVT-03, REQ-MOD-04 | pasa | `test_SOPT03e_limites_de_la_opcion` | valores no admitidos se rechazan; la repetición de fuentes la decide 6.3, no U-03. |
| S-PKG | REQ-ALC-02, REQ-CR-02 | pasa | `test_SPKG_paquete_de_transferencia_intacto` | parte automatizable de R-02 (doce Markdown, huellas de la versión implementada). |
| S-U03 | REQ-ACT-02, REQ-EVT-03 | pasa | `test_SU03_accion_por_evento_en_etapa_que_sale` | acción por evento en una etapa que sale con ese evento: no se ejecuta (comparador, 5.2 B). |
| S-U03 | REQ-EVT-03 | pasa | `test_SU03_flanco_sobre_variable_interna` | eventos internos estáticamente bloqueados (U-03). |
| S-U05 | REQ-ACT-05, REQ-SEM-09 | pasa | `test_SU05_receptividad_lee_valor_asignado` | hoja 08, 2.3 A; la receptividad ve el valor recién asignado y sigue en el mismo instante. |
| S-U05b | REQ-ACT-02, REQ-ACT-05 | pasa | `test_SU05b_asignaciones_sucesivas_vale_la_ultima` | hoja 08, 2.4 A; dos asignaciones distintas sucesivas en un instante, vale la última. |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_delay_cero` | los tiempos de 0 s se quitan (chat, 4.4 revisada): 0s/p es p y 0s/p/2s es p/2s, retardo a la desconexión puro. |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_lote_y_vencimiento_coincidentes` | lote y vencimiento independientes en el mismo τ se procesan juntos (comparador 4.3 A; cierra H-17). |
| S-U06 | REQ-SEM-08, REQ-TMP-03 | pasa | `test_SU06_vencimientos_que_dependen_del_orden` | vencimientos simultáneos con efecto mutuo (U-06). |
| S-U07 | REQ-MOD-04 | pasa | `test_SU07_fuente_de_nivel_y_transicion_sin_lados` | fuente de nivel y transición sin lados no compilan (comparador 6.2 A y 6.4 A); con «detener», U-07. |
| S-U09 | REQ-ACT-02, REQ-SEM-01, REQ-TMP-02 | pasa | `test_SU09_inicializacion_decidida` | hoja 08, 1.1 A, 1.2 A y 1.3 A (U-09 cerrada por el responsable). |

## Revisión bidireccional del paquete

Referencias que el paquete declara en un solo sentido. No son errores: el documento 11 no exige simetría fila a fila. Se listan para que el revisor decida si deben completarse.

- **requisito→caso sin retorno** (20): REQ-SEM-04→T-04c, REQ-SEM-08→T-24a, REQ-EXP-01→T-09c, REQ-JER-01→T-04c, REQ-JER-07→T-24a, REQ-EDT-03→T-04c, REQ-EDT-09→T-09c, REQ-EDT-12→T-25a, REQ-SIM-02→T-10b, REQ-SIM-03→T-02a, REQ-SIM-03→T-02b, REQ-SIM-03→T-02c, REQ-SIM-05→T-04a, REQ-SIM-08→T-08a, REQ-SIM-08→T-08b, REQ-SIM-08→T-16a, REQ-DAT-04→T-23c, REQ-DAT-05→T-24b, REQ-ARQ-01→T-24a, REQ-ROB-01→T-08b
- **caso→requisito sin retorno** (23): T-01c→REQ-SEM-01, T-01c→REQ-ACT-02, T-01d→REQ-SEM-01, T-01d→REQ-MOD-04, T-03d→REQ-SEM-03, T-05b→REQ-EVT-03, T-06a→REQ-SEM-02, T-06a→REQ-SEM-04, T-06b→REQ-SEM-02, T-06b→REQ-SEM-04, T-06c→REQ-SEM-03, T-07a→REQ-ACT-01, T-07b→REQ-ACT-02, T-07c→REQ-ACT-02, T-12c→REQ-ACT-01, T-12e→REQ-TMP-02, T-12f→REQ-TMP-02, T-13d→REQ-TMP-02, T-13d→REQ-SEM-04, T-18e→REQ-JER-04, T-18e→REQ-ACT-02, T-23f→REQ-SIM-04, T-23f→REQ-DAT-04
- **caso inexistente** (0): ninguna
- **requisito inexistente** (0): ninguna
