# 05. Trazabilidad requisito ↔ implementación ↔ prueba

Documento **generado** por `tools/generar_trazabilidad.py`; no editar a mano.

Generado el 2026-10-24T21:39:10+02:00 · Python 3.12.10 · Windows-11-10.0.26200-SP0 · 118 pruebas ejecutadas, 0 fallos, 0 errores.

Leyenda: ✔ pasa · ⛔ bloqueo por U verificado (el oráculo semántico sigue abierto) · ◐ parcial · ∅ capacidad no implementada en esta iteración (se verifica que no se ejecuta) · — no ejecutado · ✘ falla. **Un ✔ con oráculo I es provisional (U-01): no prueba conformidad.**

## Resumen

| Categoría del requisito | Nº |
|---|---|
| Implementado (P), verificable ya (`IMPL-P`) | 41 |
| Implementado como provisional (I; U-01) (`IMPL-I`) | 11 |
| Parcial (`PARCIAL`) | 11 |
| Bloqueado por U (bloqueo implementado) (`BLOQ-U`) | 5 |
| Pendiente de iteración (estructura hecha) (`PEND-ITER`) | 3 |
| Pendiente de interfaz (`PEND-UI`) | 5 |
| Pendiente de plataforma (U-10) (`PEND-PLT`) | 1 |
| Revisión documental (`DOC`) | 5 |

| Estado de los 102 casos del documento 11 | Nº |
|---|---|
| BLOQUEO VERIFICADO | 13 |
| NO EJECUTADO | 6 |
| NO IMPLEMENTADO | 7 |
| PARCIAL | 8 |
| PASA | 68 |

Pruebas suplementarias S-xx: 18 casos, 21 pruebas, 21 pasan.

## Requisitos

| Requisito | Clase/prio. | Doc. | Categoría | Implementación | Casos | Nota |
|---|---|---|---|---|---|---|
| REQ-ALC-01 | P/alta | 01 | PARCIAL | editor, persistence, engine | T-21a ◐, T-24d ◐ | Ciclo principal sin servicios de terceros verificado sin interfaz (T-24d); falta la interfaz |
| REQ-ALC-02 | P/crítica | 01 | DOC | tools/comprobar_paquete.py | R-02 (documental), S-PKG ✔ | Parte automatizable de R-02: el paquete conserva exactamente los doce Markdown con sus huellas |
| REQ-ALC-03 | P/alta | 01 | IMPL-P | profile, declaration | R-01 (documental), S-DECL ✔ | Cada capacidad marcada provisional / no soportada con su motivo |
| REQ-NOR-01 | P/crítica | 01 | IMPL-P | profile, persistence, declaration | T-22e ✔, S-DECL ✔ | Base normativa declarada en el manifiesto; ejes de versión separados; no se sustituye silenciosamente |
| REQ-NOR-02 | P/crítica | 01 | IMPL-P | declaration | R-01 (documental), S-DECL ✔ | La declaración excluye toda materia con U crítica y nunca afirma conformidad; R-01 sigue siendo documental |
| REQ-CR-01 | P/crítica | 02 | DOC | tools/paquete.py | R-01 (documental) | Las fuentes y localizadores se conservan en el paquete; la matriz enlaza cada requisito con su documento |
| REQ-CR-02 | P/crítica | 02 | DOC | — | R-02 (documental), S-PKG ✔ | Esta implementación se ha hecho solo con el paquete; ver declaración de procedencia en README |
| REQ-CR-03 | P/crítica | 02 | DOC | — | R-02 (documental) | No se ha detectado contaminación; procedimiento descrito en README |
| REQ-CR-04 | P/alta | 02 | DOC | tests | R-01 (documental) | Ningún oráculo procede de otro producto; los oráculos son los del documento 11 |
| REQ-MOD-01 | P/crítica | 03 | IMPL-P | model, persistence | T-21b ✔, T-22b ✔ | IDs únicos, propietario y referencias existentes; duplicados/huérfanos impiden simular |
| REQ-MOD-02 | I/crítica | 03 | IMPL-I | model, editor | T-21b ✔ | D-ALTERNANCIA; enlaces etapa→etapa como borrador (P-IMP-05) |
| REQ-MOD-03 | P/crítica | 03 | IMPL-P | editor | T-21c ✔ | Solo se conecta por operación explícita; la geometría no crea relaciones |
| REQ-MOD-04 | I/alta | 03 | PARCIAL | model, engine | T-03c ✔, T-10e ◐, T-01d ⛔, S-U07 ✔ | Sumideros y fuentes por evento (1.ª evolución) I; fuentes de nivel, sin lados y repetición: U-07 |
| REQ-MOD-05 | P/alta | 03 | IMPL-P | model, expressions, editor | T-09c ✔ | Texto libre conservado como descriptivo; D-EXP-PENDIENTE localizado |
| REQ-MOD-06 | P/crítica | 03 | IMPL-P | model, editor, engine | T-04c ✔, T-21d ✔ | Renombrar, mover u ordenar no cambia observables ni revisión semántica (H-13) |
| REQ-MOD-07 | I/alta | 03 | IMPL-I | model | T-18c ✔, T-19c ✔ | Propiedad única de expansiones y recintos; recursión rechazada (solo estructura) |
| REQ-SEM-01 | I/crítica | 04 | PARCIAL | engine | T-01a ✔, T-01b ✔, T-01c ◐, T-01d ⛔, S-U09 ✔, S-H07 ✔ | Situación inicial explícita sin jerarquía: I. Inicio inestable, acciones iniciales, memoria no nula y temporal verdadero: U-09. Inicio vacío: U-07 |
| REQ-SEM-02 | I/crítica | 04 | IMPL-I | engine | T-02c ✔, T-02a ✔, T-02b ✔, T-06a ✔, T-06b ✔ | Validación y receptividad; imposición jerárquica pendiente de iteración |
| REQ-SEM-03 | I/crítica | 04 | IMPL-I | engine | T-03a ✔, T-03b ✔, T-03c ✔, T-03d ✔, T-06c ✔ | Cambio conjunto de precedentes y siguientes |
| REQ-SEM-04 | I/crítica | 04 | IMPL-I | engine | T-04a ✔, T-04b ✔, T-04c ✔, T-06a ✔, T-06b ✔, T-13d ✔ | Conjunto simultáneo completo; sin prioridad por orden |
| REQ-SEM-05 | I/crítica | 04 | PARCIAL | engine | T-05a ✔, T-05b ⛔, S-H05 ✔ | Actividad I; efectos (acciones, eventos, tiempo) bloqueados por U-04 (y H-05) |
| REQ-SEM-06 | I/crítica | 04 | IMPL-I | engine | T-07a ✔, T-07b ✔, T-07c ✔ | Etapas virtuales sin pulso continuo; memorizadas conservadas; eventos en el recorrido: U-03 |
| REQ-SEM-07 | P/crítica | 04 | IMPL-P | engine | T-08a ⛔, T-08b ✔, S-08a ✔ | D-LIM-EVOL recuperable, τ sin avanzar, sin falsa estabilidad (S-08a; T-08a bloqueado por U-09, H-03) |
| REQ-SEM-08 | P/crítica | 04 | IMPL-P | engine, trace | T-04c ✔, T-23b ✔, T-24a ◐, S-U06 ✔ | Mismos observables con independencia de recorrido, geometría y control; entre sistemas: U-10 |
| REQ-SEM-09 | U/crítica | 04 | BLOQ-U | engine | T-10d ⛔, T-11b ⛔, T-15c ⛔, S-U05 ✔ | U-03..U-05: detención con D-SEM-PENDIENTE; si todas las lecturas coinciden, se acepta |
| REQ-ACT-01 | I/crítica | 05 | IMPL-I | engine | T-14a ✔, T-14b ✔, T-14c ✔, T-07a ✔, T-12c ✔, S-H10 ✔ | Disyunción sobre situación efectiva; lectura de salidas continuas no soportada (H-10) |
| REQ-ACT-02 | I/crítica | 05 | IMPL-I | engine | T-15a ✔, T-15b ✔, T-01c ◐, T-07b ✔, T-07c ✔, T-18e ∅, S-U03 ✔, S-U09 ✔, S-H07 ✔ | Memorizadas por activación, desactivación y evento, también virtuales |
| REQ-ACT-03 | P/crítica | 05 | IMPL-P | engine | T-16a ✔, T-16b ✔ | D-ESCRITURA-CONFLICTO con autores y valores; sin prioridad oculta |
| REQ-ACT-04 | I/crítica | 05 | IMPL-I | model | T-16c ✔ | D-MODO-SALIDA en validación |
| REQ-ACT-05 | U/crítica | 05 | BLOQ-U | engine | T-15c ⛔, T-16d ⛔, S-U05 ✔ | U-05: lecturas cruzadas, incrementos simultáneos y lecturas tras asignación bloqueadas |
| REQ-EVT-01 | I/crítica | 05 | IMPL-I | engine | T-10a ✔, T-10b ✔, T-10c ✔, T-10e ◐ | Flancos sobre entradas en la 1.ª evolución; sin retención ni consumo exclusivo |
| REQ-EVT-02 | P/crítica | 05 | IMPL-P | scenario | T-10b ✔, T-13a ✔ | Lotes simultáneos frente a lotes ordenados; D-LOTE |
| REQ-EVT-03 | U/crítica | 05 | BLOQ-U | model, engine | T-10d ⛔, T-11a ⛔, T-11b ⛔, T-05b ⛔, S-U03 ✔, S-H05 ✔ | U-03/U-04: eventos internos, de franqueamiento y en recorrido bloqueados |
| REQ-EXP-01 | P/alta | 05 | IMPL-P | expressions, values | T-09a ✔, T-09b ✔, T-09c ✔, S-DEC ✔, S-EXP ✔ | Tipos exactos, unidades, precedencia; sintaxis de literales P-IMP-06 |
| REQ-EXP-02 | P/crítica | 05 | IMPL-P | expressions, engine | T-09d ✔ | Evaluación pura |
| REQ-TMP-01 | P/crítica | 05 | IMPL-P | timeutil, values | T-12d ✔, T-24b ✔, S-DEC ✔ | µs exactos, rango 0..2^63-1, sin redondeo |
| REQ-TMP-02 | I/crítica | 05 | IMPL-I | engine, model | T-12a ✔, T-12b ✔, T-12c ✔, T-12e ✔, T-12f ✔, T-13d ✔, S-U09 ✔, S-12a ✔, S-H09 ✔ | delay ordinario, limitadas, retardadas; duración de etapa inicial según T-12a/T-12c (H-02); bases compuestas no soportadas (H-09) |
| REQ-TMP-03 | U/crítica | 05 | BLOQ-U | engine | T-13b ⛔, T-13c ⛔, T-20a ⛔, S-U06 ✔ | U-06: coincidencias lote/vencimiento, caída en vencimiento, rebote, d1=0, órdenes dependientes |
| REQ-JER-01 | I/crítica | 06 | PARCIAL | engine, model | T-04c ✔, T-20b ✔, S-H08 ✔ | Partición sin orden y XG de parciales sin hijos; anidados: H-08 |
| REQ-JER-02 | I/crítica | 06 | PEND-ITER | model | T-17a ∅, T-17b ∅ | Cuatro formas de forzado editables y validadas; ejecución pendiente (H-18, U-08) |
| REQ-JER-03 | P/crítica | 06 | PARCIAL | model | T-17c ◐, T-17d ✔ | Ciclos D-JERARQUIA-CICLO; conflicto posible estático; detección dinámica pendiente de ejecución |
| REQ-JER-04 | I/crítica | 06 | PEND-ITER | model | T-18a ∅, T-18b ∅, T-18c ✔, T-18e ∅ | Estructura de macro/expansión validada; ejecución pendiente |
| REQ-JER-05 | I/crítica | 06 | PEND-ITER | model | T-19a ∅, T-19b ∅, T-19c ✔ | Estructura de recintos y coherencia inicial validadas; ejecución pendiente |
| REQ-JER-06 | U/crítica | 06 | BLOQ-U | model | T-18d ⛔, T-20a ⛔, T-20c ⛔ | U-08: no ejecutable (y ejecución jerárquica aún no implementada) |
| REQ-JER-07 | P/alta | 06 | PEND-UI | — | T-21g —, T-24a ◐ | Plegado y navegación pertenecen a la vista |
| REQ-EDT-01 | P/alta | 07 | PARCIAL | editor, persistence | T-21a ◐ | Crear, abrir, guardar y duplicar sin interfaz; diálogo de cierre con cambios pendiente de interfaz |
| REQ-EDT-02 | P/alta | 07 | IMPL-P | editor | T-21b ✔, T-21c ✔ | Insertar, conectar, editar; borrador inválido guardable |
| REQ-EDT-03 | P/alta | 07 | PARCIAL | editor | T-04c ✔, T-21c ✔ | Mover, alinear, distribuir y deshacer; zoom y desplazamiento pendientes de interfaz |
| REQ-EDT-04 | P/crítica | 07 | IMPL-P | editor | T-21e ✔ | Copiar/pegar con IDs nuevos y decisión explícita de referencias externas |
| REQ-EDT-05 | P/crítica | 07 | IMPL-P | editor | T-21f ✔ | Transacciones atómicas; fallo fuera del historial; rehacer descartado |
| REQ-EDT-06 | P/crítica | 07 | IMPL-P | editor | T-21d ✔ | Renombrar sin cambiar ID, usos actualizados, colisión diagnosticada, búsqueda con ruta |
| REQ-EDT-07 | P/alta | 07 | IMPL-P | editor | T-09b ✔, T-21d ✔ | Diccionario de variables y usos afectados por un cambio |
| REQ-EDT-08 | P/alta | 07 | PEND-UI | — | T-21g — | Navegación jerárquica |
| REQ-EDT-09 | P/alta | 07 | IMPL-P | diagnostics | T-21b ✔, T-09c ✔ | Código, gravedad, elemento, evidencia y corrección; foco en interfaz pendiente |
| REQ-EDT-10 | P/crítica | 07 | IMPL-P | persistence | T-22d ✔ | Recuperación separada cada 30 s si hay cambios, sin sobrescritura |
| REQ-EDT-11 | P/alta | 07 | PEND-UI | — | T-21h — | Exportación SVG/PDF no implementada en esta iteración |
| REQ-EDT-12 | P/alta | 07 | PEND-UI | — | T-21g —, T-25a ◐ | Diagramas extensos: vista general, zoom y filtros |
| REQ-EDT-13 | P/alta | 07 | PEND-UI | — | T-26a —, T-26b — | Teclado y accesibilidad |
| REQ-EDT-14 | P/crítica | 07 | IMPL-P | editor, engine | T-23d ✔ | Edición semántica = revisión nueva; la ejecución conserva la suya |
| REQ-SIM-01 | P/crítica | 08 | IMPL-P | engine | T-23a ✔, T-23b ✔ | Estados de sesión, pausas en frontera completa, microavance, puntos antes/después |
| REQ-SIM-02 | P/crítica | 08 | IMPL-P | scenario, engine | T-10b ✔, T-23c ✔ | Escenarios y entradas manuales registradas con origen y ordinal |
| REQ-SIM-03 | P/alta | 08 | IMPL-P | engine | T-02a ✔, T-02b ✔, T-02c ✔, T-23a ✔ | Observación de actividad, validación, receptividad y franqueamiento |
| REQ-SIM-04 | P/crítica | 08 | IMPL-P | engine | T-23c ✔, T-22f ✔, T-23f ✔ | Instantánea con Z completo y compatibilidad exacta; dentro de recorrido D-INSTANTANEA-FASE |
| REQ-SIM-05 | P/crítica | 08 | IMPL-P | trace | T-04a ✔, T-22g ✔ | Traza con conjuntos E, causas, cierre y digest |
| REQ-SIM-06 | P/crítica | 08 | IMPL-P | engine | T-09d ✔, T-23b ✔ | Observar y pausar no modifican comportamiento |
| REQ-SIM-07 | P/crítica | 08 | IMPL-P | engine | T-23e ✔ | Intervención E en pausa estable, rama auditable |
| REQ-SIM-08 | P/alta | 08 | IMPL-P | diagnostics, engine | T-08a ⛔, T-08b ✔, T-16a ✔, S-08a ✔ | Evidencia y corrección recomendada en cada diagnóstico |
| REQ-DAT-01 | P/crítica | 09 | IMPL-P | model, persistence, ids | T-22b ✔, T-21e ✔, S-H12 ✔ | Identidades, referencias y propiedad; nombres hexadecimales (H-12) |
| REQ-DAT-02 | P/crítica | 09 | IMPL-P | persistence | T-22a ✔ | Ida y vuelta conserva significado, notas y vista (formato 0.1 provisional, U-11) |
| REQ-DAT-03 | P/crítica | 09 | IMPL-P | persistence | T-22c ✔, T-22e ✔ | Versión mayor/menor, desconocidos y migración con copia e informe |
| REQ-DAT-04 | P/crítica | 09 | IMPL-P | engine | T-22f ✔, T-23c ✔, T-23f ✔ | Instantánea íntegra y compatibilidad exacta; campos U no aplicables declarados |
| REQ-DAT-05 | P/crítica | 09 | IMPL-P | canonical, timeutil | T-24a ◐, T-24b ✔, S-CAN ✔ | Representación canónica y SHA-256 independientes de región |
| REQ-DAT-06 | P/crítica | 09 | IMPL-P | canonical, persistence, expressions | T-25b ✔, T-25c ✔, S-CAN ✔ | Sin código ejecutable, sin rutas fuera de raíz, límites previos |
| REQ-DAT-07 | P/crítica | 09 | IMPL-P | persistence | T-22d ✔ | Guardado atómico con diario; recuperación del último válido |
| REQ-DAT-08 | P/crítica | 09 | IMPL-P | model, trace | T-09c ✔, T-22g ✔ | Divergencia texto-significado y trazas truncadas |
| REQ-ARQ-01 | P/crítica | 10 | IMPL-P | todo el núcleo | T-23b ✔, T-24a ◐ | Todo el contrato se verifica sin interfaz (esta batería) |
| REQ-PLT-01 | P/crítica | 10 | PEND-PLT | trace | T-24a ◐ | Trazas canónicas deterministas en Windows; comparación en macOS/Linux pendiente (U-10) |
| REQ-PLT-02 | P/alta | 10 | PARCIAL | timeutil, persistence | T-24b ✔, T-24c ◐, S-H12 ✔ | Región, Unicode, rutas y mayúsculas verificados en Windows; otros sistemas U-10 |
| REQ-PLT-03 | P/alta | 10 | PARCIAL | todo el núcleo | T-24d ◐, T-24e — | Sin conexión verificado; instalación y actualización pendientes de empaquetado |
| REQ-PLT-04 | P/alta | 10 | PARCIAL | model, persistence, tools/medir_presupuestos.py | T-25a ◐, T-25d — | Límites aplicados; medición indicativa, no ratificada (U-10) |
| REQ-ROB-01 | P/crítica | 10 | IMPL-P | model, engine, persistence | T-08a ⛔, T-08b ✔, T-25a ◐, S-08a ✔ | Límites de datos y de evolución diagnosticados sin alterar significado |
| REQ-ROB-02 | P/crítica | 10 | IMPL-P | persistence, canonical | T-22d ✔, T-25b ✔, T-25c ✔ | Archivos fallidos preservan la última revisión válida y no ejecutan cargas |

## Casos del documento 11

| Caso | Requisitos | Oráculo (11) | Resultado | Pruebas | Observación |
|---|---|---|---|---|---|
| T-01a | REQ-SEM-01 | I | PASA (oráculo I) | `test_T01a_situacion_inicial_explicita` |  |
| T-01b | REQ-SEM-01 | I | PASA (oráculo I) | `test_T01b_orden_de_archivo_irrelevante` |  |
| T-01c | REQ-SEM-01, REQ-ACT-02 | P/I parcial | PARCIAL | `test_T01c_restaurar_conserva_memoria_reiniciar_la_pone_a_cero` | restaurar/reiniciar verificados; activaciones iniciales U-09 |
| T-01d | REQ-SEM-01, REQ-MOD-04 | B | BLOQUEO VERIFICADO | `test_T01d_sin_iniciales_bloqueo_U07` | U-07 |
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
| T-05b | REQ-SEM-05, REQ-EVT-03 | B | BLOQUEO VERIFICADO | `test_T05b_efectos_de_permanencia_bloqueo_U04` | U-04 |
| T-06a | REQ-SEM-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T06a_sincronizacion_incompleta` |  |
| T-06b | REQ-SEM-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T06b_recorrido_hasta_sincronizar` |  |
| T-06c | REQ-SEM-03 | I | PASA (oráculo I) | `test_T06c_paralelismo_y_sincronizacion` |  |
| T-07a | REQ-SEM-06, REQ-ACT-01 | I | PASA (oráculo I) | `test_T07a_etapa_virtual_sin_pulso` |  |
| T-07b | REQ-SEM-06, REQ-ACT-02 | I | PASA (oráculo I) | `test_T07b_memorizada_al_activar_etapa_virtual` |  |
| T-07c | REQ-SEM-06, REQ-ACT-02 | I | PASA (oráculo I) | `test_T07c_memorizada_al_desactivar_etapa_virtual` |  |
| T-08a | REQ-SEM-07, REQ-ROB-01 | P | BLOQUEO VERIFICADO | `test_T08a_inicio_inestable_bloqueado_por_U09` | el modelo es inestable al iniciar: U-09 (H-03); la parte P está en S-08a |
| T-08b | REQ-SEM-07 | P | PASA (oráculo P) | `test_T08b_espera_estable_no_es_divergencia` |  |
| T-09a | REQ-EXP-01 | P | PASA (oráculo P) | `test_T09a_precedencia` |  |
| T-09b | REQ-EXP-01, REQ-EDT-07 | P | PASA (oráculo P) | `test_T09b_unidades_y_tipos` |  |
| T-09c | REQ-MOD-05, REQ-DAT-08 | P | PASA (oráculo P) | `test_T09c_texto_pendiente_y_divergencia_se_guardan` |  |
| T-09d | REQ-EXP-02, REQ-SIM-06 | P | PASA (oráculo P) | `test_T09d_observar_no_modifica_estado` |  |
| T-10a | REQ-EVT-01 | I | PASA (oráculo I) | `test_T10a_sin_flanco_al_arrancar` |  |
| T-10b | REQ-EVT-01, REQ-EVT-02 | I/P | PASA (oráculo I/P) | `test_T10b_lote_simultaneo_frente_a_lotes_ordenados` |  |
| T-10c | REQ-EVT-01 | I | PASA (oráculo I) | `test_T10c_flanco_no_se_retiene` |  |
| T-10d | REQ-EVT-03, REQ-SEM-09 | B | BLOQUEO VERIFICADO | `test_T10d_alcance_causal_del_evento_bloqueo_U03` | U-03 |
| T-10e | REQ-EVT-01, REQ-MOD-04 | I/B parcial | PARCIAL | `test_T10e_fuentes_por_evento_primera_evolucion_y_repeticion_U07` | primera evolución E={t,u} verificada; repetición U-07 |
| T-11a | REQ-EVT-03 | B | BLOQUEO VERIFICADO | `test_T11a_permanencia_y_franqueamiento_separados_bloqueo_U04` | U-04 |
| T-11b | REQ-EVT-03, REQ-SEM-09 | B | BLOQUEO VERIFICADO | `test_T11b_evento_de_franqueamiento_bloqueo_U03` | U-03 |
| T-12a | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12a_retardo_exacto_sin_cuantizacion` | duración de etapa inicial según el oráculo (H-02); lectura de «B a 2000001» (H-11) |
| T-12b | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12b_pulso_breve_no_activa` |  |
| T-12c | REQ-TMP-02, REQ-ACT-01 | I | PASA (oráculo I) | `test_T12c_accion_limitada` | duración de etapa inicial según el oráculo (H-02) |
| T-12d | REQ-TMP-01 | P | PASA (oráculo P) | `test_T12d_tiempo_exacto_rechazos` |  |
| T-12e | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12e_retardo_de_conexion_y_desconexion` |  |
| T-12f | REQ-TMP-02 | I | PASA (oráculo I) | `test_T12f_reentrada_inicia_intervalo_nuevo` |  |
| T-13a | REQ-EVT-02 | P | PASA (oráculo P) | `test_T13a_lote_con_dos_escrituras` |  |
| T-13b | REQ-TMP-03 | B | BLOQUEO VERIFICADO | `test_T13b_caida_exacta_en_el_vencimiento_bloqueo` | U-06; con p verdadera desde el inicio, U-09 |
| T-13c | REQ-TMP-03 | B | BLOQUEO VERIFICADO | `test_T13c_rebote_durante_desconexion_bloqueo_U06` | U-06 |
| T-13d | REQ-TMP-02, REQ-SEM-04 | I | PASA (oráculo I) | `test_T13d_vencimientos_simultaneos_misma_frontera` |  |
| T-14a | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14a_disyuncion_de_contribuciones` |  |
| T-14b | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14b_continua_sin_memoria` |  |
| T-14c | REQ-ACT-01 | I | PASA (oráculo I) | `test_T14c_condicion_continua_con_evento` | segunda parte = T-07a |
| T-15a | REQ-ACT-02 | I | PASA (oráculo I) | `test_T15a_memorizada_conserva_valor` |  |
| T-15b | REQ-ACT-02 | I | PASA (oráculo I) | `test_T15b_accion_por_evento_cuenta_eventos_reales` |  |
| T-15c | REQ-ACT-05, REQ-SEM-09 | B | BLOQUEO VERIFICADO | `test_T15c_lecturas_cruzadas_bloqueo_U05` | U-05 |
| T-16a | REQ-ACT-03 | P | PASA (oráculo P) | `test_T16a_conflicto_de_escritura` |  |
| T-16b | REQ-ACT-03 | I | PASA (oráculo I) | `test_T16b_escrituras_iguales` |  |
| T-16c | REQ-ACT-04 | I | PASA (oráculo I) | `test_T16c_modos_mezclados` |  |
| T-16d | REQ-ACT-05 | B | BLOQUEO VERIFICADO | `test_T16d_dos_incrementos_bloqueo_U05` | U-05 |
| T-17a | REQ-JER-02 | I | NO IMPLEMENTADO (bloqueo verificado) | `test_T17a_forzado_no_ejecutable_en_esta_iteracion` | ejecución de forzado no implementada (H-18) |
| T-17b | REQ-JER-02 | I/B parcial | NO IMPLEMENTADO (bloqueo verificado) | `test_T17b_forzado_actual_no_ejecutable` | ejecución de forzado no implementada; efectos U-08 |
| T-17c | REQ-JER-03 | P | PARCIAL | `test_T17c_conflicto_posible_de_forzado` | conflicto posible detectado estáticamente; detección dinámica pendiente |
| T-17d | REQ-JER-03 | P | PASA (oráculo P) | `test_T17d_ciclo_de_forzado` |  |
| T-18a | REQ-JER-04 | I | NO IMPLEMENTADO (bloqueo verificado) | `test_T18a_macroetapa_no_ejecutable_en_esta_iteracion` | ejecución de macroetapas no implementada |
| T-18b | REQ-JER-04 | I | NO IMPLEMENTADO (bloqueo verificado) | `test_T18b_recorrido_de_expansion_no_ejecutable` | ejecución de macroetapas no implementada |
| T-18c | REQ-JER-04, REQ-MOD-07 | P/I | PASA (oráculo P/I) | `test_T18c_propiedad_unica_y_recursion` | estructura: propiedad, anidamiento y recursión |
| T-18d | REQ-JER-06 | B | BLOQUEO VERIFICADO | `test_T18d_rama_residual_bloqueada` | U-08 (y ejecución no implementada) |
| T-18e | REQ-JER-04, REQ-ACT-02 | I/B parcial | NO IMPLEMENTADO (bloqueo verificado) | `test_T18e_reentrada_de_macroetapa_no_ejecutable` | ejecución de macroetapas no implementada; U-08 |
| T-19a | REQ-JER-05 | I | NO IMPLEMENTADO (bloqueo verificado) | `test_T19a_encapsulacion_no_ejecutable_en_esta_iteracion` | ejecución de encapsulación no implementada |
| T-19b | REQ-JER-05 | I | NO IMPLEMENTADO (bloqueo verificado) | `test_T19b_encapsulacion_anidada_no_ejecutable` | ejecución de encapsulación no implementada |
| T-19c | REQ-JER-05, REQ-MOD-07 | I/P | PASA (oráculo I/P) | `test_T19c_propietario_unico_y_coherencia_inicial` |  |
| T-20a | REQ-JER-06, REQ-TMP-03 | B | BLOQUEO VERIFICADO | `test_T20a_coincidencia_jerarquica_bloqueada` | U-06/U-08 (y ejecución no implementada) |
| T-20b | REQ-JER-01 | I/P | PASA (oráculo I/P) | `test_T20b_particion_sin_orden_y_actividad_derivada` |  |
| T-20c | REQ-JER-06 | B | BLOQUEO VERIFICADO | `test_T20c_forzado_contra_recinto_bloqueado` | U-08 (y ejecución no implementada) |
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
| S-CAN | REQ-DAT-05, REQ-DAT-06 | pasa | `test_SCAN_formato_canonico` | reglas de representación canónica y lectura estricta (09). |
| S-DEC | REQ-EXP-01, REQ-TMP-01 | pasa | `test_SDEC_decimales_y_enteros_exactos` | sin redondeo silencioso ni desbordamiento. |
| S-DECL | REQ-ALC-03, REQ-NOR-01, REQ-NOR-02 | pasa | `test_SDECL_declaracion_sin_conformidad` | la declaración excluye U críticas y no afirma conformidad. |
| S-EXP | REQ-EXP-01 | pasa | `test_SEXP_comparacion_encadenada_y_tipos` | comparaciones encadenadas rechazadas; sin conversión booleano↔número. |
| S-H05 | REQ-EVT-03, REQ-SEM-05 | pasa | `test_SH05_activar_etapa_ya_activa_bloqueo_U04` | hallazgo H-05 (activación de etapa ya activa fuera de D). |
| S-H07 | REQ-ACT-02, REQ-SEM-01 | pasa | `test_SH07_memoria_inicial_no_nula_bloqueo_U09` | hallazgo H-07. |
| S-H08 | REQ-JER-01 | pasa | `test_SH08_actividad_de_parcial_con_hijos` | hallazgo H-08. |
| S-H09 | REQ-TMP-02 | pasa | `test_SH09_reentrada_virtual_con_dependencia_temporal` | hallazgo H-09. |
| S-H10 | REQ-ACT-01 | pasa | `test_SH10_leer_salida_continua` | hallazgo H-10. |
| S-H12 | REQ-DAT-01, REQ-PLT-02 | pasa | `test_SH12_id_de_documento_y_nombre_de_fichero` | hallazgo H-12. |
| S-PKG | REQ-ALC-02, REQ-CR-02 | pasa | `test_SPKG_paquete_de_transferencia_intacto` | parte automatizable de R-02 (doce Markdown, huellas de la versión implementada). |
| S-U03 | REQ-ACT-02, REQ-EVT-03 | pasa | `test_SU03_accion_por_evento_en_etapa_que_sale` | acción sobre evento y etapa desactivada por ese evento (U-03/U-05). |
| S-U03 | REQ-EVT-03 | pasa | `test_SU03_flanco_sobre_variable_interna` | eventos internos estáticamente bloqueados (U-03). |
| S-U05 | REQ-ACT-05, REQ-SEM-09 | pasa | `test_SU05_receptividad_lee_valor_asignado` | asignación n:=1 seguida de receptividad n=1 en etapa virtual (U-05). |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_delay_cero` | delay con d1=0 bloqueado (U-06). |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_lote_y_vencimiento_coincidentes` | coincidencia de lote y vencimiento en el mismo τ (H-17, U-06). |
| S-U06 | REQ-SEM-08, REQ-TMP-03 | pasa | `test_SU06_vencimientos_que_dependen_del_orden` | vencimientos simultáneos con efecto mutuo (U-06). |
| S-U07 | REQ-MOD-04 | pasa | `test_SU07_fuente_de_nivel_y_transicion_sin_lados` | U-07 en validación; el borrador se conserva. |
| S-U09 | REQ-ACT-02, REQ-SEM-01, REQ-TMP-02 | pasa | `test_SU09_inicio_inestable_acciones_iniciales_y_temporal_verdadero` | bloqueos de inicialización (U-09). |

## Revisión bidireccional del paquete

Referencias que el paquete declara en un solo sentido. No son errores: el documento 11 no exige simetría fila a fila. Se listan para que el revisor decida si deben completarse.

- **requisito→caso sin retorno** (20): REQ-SEM-04→T-04c, REQ-SEM-08→T-24a, REQ-EXP-01→T-09c, REQ-JER-01→T-04c, REQ-JER-07→T-24a, REQ-EDT-03→T-04c, REQ-EDT-09→T-09c, REQ-EDT-12→T-25a, REQ-SIM-02→T-10b, REQ-SIM-03→T-02a, REQ-SIM-03→T-02b, REQ-SIM-03→T-02c, REQ-SIM-05→T-04a, REQ-SIM-08→T-08a, REQ-SIM-08→T-08b, REQ-SIM-08→T-16a, REQ-DAT-04→T-23c, REQ-DAT-05→T-24b, REQ-ARQ-01→T-24a, REQ-ROB-01→T-08b
- **caso→requisito sin retorno** (23): T-01c→REQ-SEM-01, T-01c→REQ-ACT-02, T-01d→REQ-SEM-01, T-01d→REQ-MOD-04, T-03d→REQ-SEM-03, T-05b→REQ-EVT-03, T-06a→REQ-SEM-02, T-06a→REQ-SEM-04, T-06b→REQ-SEM-02, T-06b→REQ-SEM-04, T-06c→REQ-SEM-03, T-07a→REQ-ACT-01, T-07b→REQ-ACT-02, T-07c→REQ-ACT-02, T-12c→REQ-ACT-01, T-12e→REQ-TMP-02, T-12f→REQ-TMP-02, T-13d→REQ-TMP-02, T-13d→REQ-SEM-04, T-18e→REQ-JER-04, T-18e→REQ-ACT-02, T-23f→REQ-SIM-04, T-23f→REQ-DAT-04
- **caso inexistente** (0): ninguna
- **requisito inexistente** (0): ninguna
