# 05. Trazabilidad requisito ↔ implementación ↔ prueba

Documento **generado** por `tools/generar_trazabilidad.py`; no editar a mano.

Generado el 2026-10-30T21:25:04+01:00 · Python 3.12.10 · Windows-11-10.0.26200-SP0 · 529 pruebas ejecutadas, 0 fallos, 0 errores.

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

Pruebas suplementarias S-xx: 428 casos, 432 pruebas, 432 pasan.

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
| REQ-MOD-03 | P/crítica | 03 | IMPL-P | editor | T-21c ✔, S-EDI258 ✔, S-EDI259 ✔, S-EDI228 ✔, S-EDI229 ✔, S-EDI230 ✔, S-EDI231 ✔, S-EDI232 ✔, S-EDI233 ✔, S-EDI225 ✔, S-EDI07 ✔, S-EDI17 ✔, S-EDI194 ✔, S-EDI19 ✔, S-EDI20 ✔, S-EDI21 ✔, S-EDI23 ✔, S-EDI24 ✔, S-EDI26 ✔, S-EDI193 ✔ | Solo se conecta por operación explícita; la geometría no crea relaciones |
| REQ-MOD-04 | I/alta | 03 | IMPL-DEC | model, engine | T-03c ✔, T-10e ◆, T-01d ◆, S-U07 ✔, S-OPT03e ✔ | Sumideros I. U-07 cerrada por el responsable (comparador, 27-10-2026, P-IMP-22): fuente por evento una vez por flanco (6.3 A); sin etapas iniciales, fuente de nivel y transición sin lados no compilan (6.1 A, 6.2 A, 6.4 A) |
| REQ-MOD-05 | P/alta | 03 | IMPL-P | model, expressions, editor | T-09c ✔ | Texto libre conservado como descriptivo; D-EXP-PENDIENTE localizado |
| REQ-MOD-06 | P/crítica | 03 | IMPL-P | model, editor, engine | T-04c ✔, T-21d ✔, S-EDI151 ✔ | Renombrar, mover u ordenar no cambia observables ni revisión semántica (H-13) |
| REQ-MOD-07 | I/alta | 03 | IMPL-I | model, hierarchy | T-18c ✔, T-19c ✔, S-EDI229 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI173 ✔, S-EDI174 ✔, S-EDI179 ✔, S-EDI189 ✔, S-EDI139 ✔, S-EDI144 ✔, S-EDI145 ✔, S-EDI149 ✔, S-EDI154 ✔, S-EDI155 ✔, S-EDI158 ✔, S-EDI193 ✔, S-H08 ✔ | Propiedad única de expansiones y recintos; recursión rechazada; la estructura se ejecuta (P-IMP-23) |
| REQ-SEM-01 | I/crítica | 04 | PARCIAL | engine | T-01a ✔, T-01b ✔, T-01c ✔, T-01d ◆, S-CMP02 ✔, S-U09 ✔, S-H07 ✔ | Situación inicial explícita y su cierre causal en τ=0: acciones al activar las iniciales, evolución inicial y temporizadores desde τ=0 (hoja 08, 1.1–1.4, P-IMP-19). Inicio vacío: no compila (6.1 A, P-IMP-22). Abierto: iniciales dentro de jerarquías (U-08) |
| REQ-SEM-02 | I/crítica | 04 | IMPL-I | engine | T-02c ✔, T-02a ✔, T-02b ✔, T-06a ✔, T-06b ✔, S-EDI230 ✔ | Validación y receptividad; imposición jerárquica pendiente de iteración |
| REQ-SEM-03 | I/crítica | 04 | IMPL-I | engine | T-03a ✔, T-03b ✔, T-03c ✔, T-03d ✔, T-06c ✔ | Cambio conjunto de precedentes y siguientes |
| REQ-SEM-04 | I/crítica | 04 | IMPL-I | engine | T-04a ✔, T-04b ✔, T-04c ✔, T-06a ✔, T-06b ✔, T-13d ✔ | Conjunto simultáneo completo; sin prioridad por orden |
| REQ-SEM-05 | I/crítica | 04 | IMPL-DEC | engine | T-05a ✔, T-05b ◆, S-H05 ✔ | Actividad I. Efectos decididos por el responsable (comparador, 27-10-2026, P-IMP-22): en permanencia o reactivación no se ejecutan acciones al activar ni al desactivar y la duración sigue (3.1 A, 3.2 A, 3.3 A; cierra H-05) |
| REQ-SEM-06 | I/crítica | 04 | IMPL-I | engine | T-07a ✔, T-07b ✔, T-07c ✔, S-EJ01 ✔, S-H09 ✔ | Etapas inestables sin pulso continuo; memorizadas conservadas; eventos en el recorrido según la lectura 5.1 (P-IMP-22) |
| REQ-SEM-07 | P/crítica | 04 | IMPL-P | engine | T-08a ✔, T-08b ✔, S-FIO29 ✔, S-FIO62 ✔, S-APP19 ✔, S-08a ✔, S-H09b ✔, S-OPT03c ✔ | D-LIM-EVOL recuperable, τ sin avanzar, sin falsa estabilidad (T-08a con su oráculo original desde la respuesta 1.2 A; S-08a) |
| REQ-SEM-08 | P/crítica | 04 | IMPL-P | engine, trace | T-04c ✔, T-23b ✔, T-24a ◐, S-U06 ✔ | Mismos observables con independencia de recorrido, geometría y control; entre sistemas: U-10 |
| REQ-SEM-09 | U/crítica | 04 | IMPL-DEC | engine | T-10d ◆, T-11b ⛔, T-15c ◆, S-CMP01 ✔, S-CMP02 ✔, S-CMP03 ✔, S-CMP05 ✔, S-APP08 ✔, S-U05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔ | U-05 (P-IMP-20) y U-03, U-04, U-06, U-07 (comparador, 27-10-2026, P-IMP-22) cerradas por el responsable; cada lectura sigue siendo seleccionable, «detener» incluida en el banco (P-IMP-15, P-IMP-21; el simulador de escritorio no la ofrece, P-IMP-30). Siguen deteniéndose los eventos internos y de franqueamiento (U-03), 0s/p/d2 y los vencimientos que dependen del orden (U-06) |
| REQ-ACT-01 | I/crítica | 05 | IMPL-I | engine | T-14a ✔, T-14b ✔, T-14c ✔, T-07a ✔, T-12c ✔, S-EDI317 ✔, S-EDI249 ✔, S-EDI224 ✔, S-EDI256 ✔, S-EDI304 ✔, S-EDI305 ✔, S-EDI240 ✔, S-EDI100 ✔, S-EDI102 ✔, S-EDI104 ✔, S-EDI105 ✔, S-EDI106 ✔, S-EDI114 ✔, S-EDI117 ✔, S-EDI123 ✔, S-EDI124 ✔, S-EDI126 ✔, S-EDI127 ✔, S-EDI128 ✔, S-EDI129 ✔, S-EDI130 ✔, S-EDI131 ✔, S-EDI132 ✔, S-EDI133 ✔, S-EDI134 ✔, S-EDI135 ✔, S-EDI136 ✔, S-EDI137 ✔, S-EDI189 ✔, S-EDI40 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI58 ✔, S-EDI62 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI75 ✔, S-EDI82 ✔, S-EDI83 ✔, S-EDI84 ✔, S-EDI86 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI91 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI39 ✔, S-EDI98 ✔, S-H10 ✔ | Disyunción sobre situación efectiva; una salida continua leída en una expresión vale según la situación del momento (comparador, 8.2 C; cierra H-10) |
| REQ-ACT-02 | I/crítica | 05 | IMPL-I | engine | T-15a ✔, T-15b ✔, T-01c ✔, T-07b ✔, T-07c ✔, T-18e ◐, S-CMP02 ✔, S-EJ02 ✔, S-U03 ✔, S-U05b ✔, S-U09 ✔, S-H07 ✔ | Memorizadas por activación, desactivación y evento, también virtuales |
| REQ-ACT-03 | P/crítica | 05 | IMPL-P | model, engine | T-16a ✔, T-16b ✔, S-ESC01 ✔, S-ESC02 ✔ | D-ESCRITURA-CONFLICTO con autores y valores, sin prioridad oculta; un conflicto seguro impide compilar (P-IMP-16) y el resto se detiene en ejecución |
| REQ-ACT-04 | I/crítica | 05 | IMPL-I | model | T-16c ✔ | D-MODO-SALIDA en validación |
| REQ-ACT-05 | U/crítica | 05 | IMPL-DEC | engine, model | T-15c ◆, T-16d ◆, S-EJ01 ✔, S-U05 ✔, S-U05b ✔, S-ESC02 ✔ | Hoja 08, 2.1 C, 2.2 B, 2.3 A, 2.4 A y 2.5 A (P-IMP-20): conflicto si dos escriben a la vez, dependencia cruzada no compila, lo asignado se ve en el mismo instante y vale la última asignación |
| REQ-EVT-01 | I/crítica | 05 | IMPL-I | engine | T-10a ✔, T-10b ✔, T-10c ✔, T-10e ◆, S-EJ02 ✔ | Flancos sobre entradas en la 1.ª evolución; sin retención ni consumo exclusivo |
| REQ-EVT-02 | P/crítica | 05 | IMPL-P | scenario | T-10b ✔, T-13a ✔ | Lotes simultáneos frente a lotes ordenados; D-LOTE |
| REQ-EVT-03 | U/crítica | 05 | PARCIAL | model, engine | T-10d ◆, T-11a ◆, T-11b ⛔, T-05b ◆, S-CMP02 ✔, S-EJ01 ✔, S-EJ02 ✔, S-U03 ✔, S-H05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔, S-OPT03e ✔ | Evento en el recorrido: lectura «situación anterior» por defecto; acciones por evento solo si la etapa estaba activa y no sale con él (comparador, 27-10-2026, 5.1–5.3, P-IMP-22; H-23). Eventos internos y de franqueamiento: U-03, bloqueados |
| REQ-EXP-01 | P/alta | 05 | IMPL-P | expressions, values | T-09a ✔, T-09b ✔, T-09c ✔, S-FIO12 ✔, S-FIO13 ✔, S-DEC ✔, S-EXP ✔ | Tipos exactos, unidades, precedencia; sintaxis de literales P-IMP-06 |
| REQ-EXP-02 | P/crítica | 05 | IMPL-P | expressions, engine | T-09d ✔ | Evaluación pura |
| REQ-TMP-01 | P/crítica | 05 | IMPL-P | timeutil, values | T-12d ✔, T-24b ✔, S-EDI207 ✔, S-EDI210 ✔, S-EDI204 ✔, S-EDI205 ✔, S-EDI206 ✔, S-EDI41 ✔, S-EDI46 ✔, S-DEC ✔ | µs exactos, rango 0..2^63-1, sin redondeo |
| REQ-TMP-02 | I/crítica | 05 | IMPL-I | engine, model | T-12a ✔, T-12b ✔, T-12c ✔, T-12e ✔, T-12f ✔, T-13d ✔, S-EDI75 ✔, S-FIO15 ✔, S-U09 ✔, S-12a ✔, S-H09 ✔, S-H09b ✔ | delay ordinario, limitadas, retardadas; duración de etapa inicial según T-12a/T-12c (H-02); salida y reentrada en el mismo instante sin interrumpir la duración (P-IMP-18); bases compuestas no soportadas (H-09) |
| REQ-TMP-03 | U/crítica | 05 | PARCIAL | engine, model | T-13b ◆, T-13c ◆, T-20a ◆, S-CMP02 ✔, S-U06 ✔ | Decidido (comparador, 27-10-2026, P-IMP-22): caída en el vencimiento → primero el vencimiento (4.1 A); rebote → sigue verdadera (4.2 A); lote y vencimiento independientes → juntos (4.3 A; cierra H-17); los tiempos de 0 s se quitan: 0s/p es p y 0s/p/7s es p/7s (chat, 4.4 revisada, P-IMP-28). Sigue en U-06: vencimientos simultáneos que dependen del orden |
| REQ-JER-01 | I/crítica | 06 | IMPL-I | engine, model | T-04c ✔, T-20b ✔, S-H08 ✔ | Partición sin orden y XG derivada de sus etapas. Un parcial dentro de otro solo como recinto o expansión; sin encapsulante no compila (chat 27-10-2026, 8.1 C; cierra H-08) |
| REQ-JER-02 | I/crítica | 06 | IMPL-I | hierarchy, engine | T-17a ✔, T-17b ◐, S-EDI253 ✔, S-EDI254 ✔, S-EDI255 ✔, S-EDI280 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI284 ✔, S-EDI285 ✔, S-EDI303 ✔, S-EDI305 ✔, S-EDI306 ✔, S-EDI307 ✔, S-EDI308 ✔, S-EDI309 ✔, S-EDI328 ✔, S-EDI242 ✔, S-EDI183 ✔, S-EDI184 ✔, S-EDI190 ✔, S-EDI191 ✔, S-EDI192 ✔, S-EDI196 ✔, S-EDI142 ✔, S-EDI143 ✔, S-EDI146 ✔, S-EDI147 ✔, S-EDI300 ✔, S-EDI301 ✔, S-EDI302 ✔ | Forzado explícito, actual (captura), vacío e inicial; el destino no evoluciona mientras está vigente; la retirada libera desde la situación resultante (documento 06, P-IMP-23). Momento, temporizadores, recintos y acciones: U-08 (7.2–7.4, 7.8) |
| REQ-JER-03 | P/crítica | 06 | IMPL-P | model, hierarchy | T-17c ✔, T-17d ✔, S-EDI254 ✔, S-EDI284 ✔, S-EDI306 ✔, S-EDI328 ✔, S-EDI183 ✔, S-EDI146 ✔ | Ciclos D-JERARQUIA-CICLO; conflicto posible avisado al validar y detenido al ejecutar (D-FORZADO-CONFLICTO) sin prioridad por ID |
| REQ-JER-04 | I/crítica | 06 | IMPL-I | model, hierarchy, engine | T-18a ✔, T-18b ✔, T-18c ✔, T-18e ◐, S-EDI286 ✔, S-EDI287 ✔, S-EDI296 ✔, S-EDI320 ✔, S-EDI325 ✔, S-EDI313 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI227 ✔, S-EDI170 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI173 ✔, S-EDI178 ✔, S-EDI180 ✔, S-EDI181 ✔, S-EDI182 ✔, S-EDI187 ✔, S-EDI194 ✔, S-EDI139 ✔, S-EDI140 ✔, S-EDI145 ✔, S-EDI193 ✔, S-APP20 ✔ | Relación expandida: llegar activa la entrada, salir exige la salida; XM por la expansión; reentrada sin borrar memorias (P-IMP-23). Ramas residuales: U-08 (7.5). Iniciales en la expansión: se admiten (7.7 A, P-IMP-24) |
| REQ-JER-05 | I/crítica | 06 | IMPL-I | model, hierarchy | T-19a ✔, T-19b ✔, T-19c ✔, S-EDI286 ✔, S-EDI287 ✔, S-EDI296 ✔, S-EDI318 ✔, S-EDI319 ✔, S-EDI320 ✔, S-EDI325 ✔, S-EDI314 ✔, S-EDI274 ✔, S-EDI275 ✔, S-EDI312 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI170 ✔, S-EDI174 ✔, S-EDI175 ✔, S-EDI176 ✔, S-EDI188 ✔, S-EDI196 ✔, S-EDI141 ✔, S-EDI144 ✔, S-EDI145 ✔, S-EDI150 ✔, S-EDI155 ✔ | Al arrancar, iniciales; al reentrar, enlaces de activación; al salir, se desactivan todos los descendientes (P-IMP-23). Encapsulante en permanencia: el contenido se mantiene (comparador, 3.4 A) |
| REQ-JER-06 | U/crítica | 06 | IMPL-DEC | hierarchy | T-18d ◆, T-20a ◆, T-20c ◆, S-EDI148 ✔ | Cerradas por el responsable: 7.2 B, 7.3 A, 7.4 C, 7.5 A, 7.6 B, 7.7 A y 7.8 A (P-IMP-24 a P-IMP-26). Vaciar por forzado un recinto con su encapsulante activa no se preguntó y se detiene (U-08) |
| REQ-JER-07 | P/alta | 06 | PEND-UI | — | T-21g —, T-24a ◐, S-EDI316 ✔, S-EDI289 ✔, S-EDI291 ✔, S-EDI292 ✔, S-EDI293 ✔, S-EDI294 ✔, S-EDI177 ✔, S-EDI181 ✔, S-EDI185 ✔, S-EDI186 ✔, S-EDI152 ✔, S-EDI154 ✔, S-EDI157 ✔ | Plegado y navegación pertenecen a la vista |
| REQ-EDT-01 | P/alta | 07 | PARCIAL | editor, persistence | T-21a ◐, S-EDI283 ✔, S-EDI308 ✔, S-EDI03 ✔, S-EDI04 ✔, S-EDI05 ✔, S-EDI08 ✔, S-EDI28 ✔, S-EDI32 ✔, S-EDI300 ✔, S-APP06 ✔, S-APP18 ✔ | Crear, abrir, guardar y duplicar sin interfaz; el simulador de escritorio abre proyectos y modelos, crea un grafcet nuevo, lo guarda y lo reabre (P-IMP-29, P-IMP-32), y pregunta antes de descartar cambios; sin duplicar desde la interfaz |
| REQ-EDT-02 | P/alta | 07 | IMPL-P | editor | T-21b ✔, T-21c ✔, S-EDI286 ✔, S-EDI287 ✔, S-EDI288 ✔, S-EDI296 ✔, S-EDI318 ✔, S-EDI319 ✔, S-EDI325 ✔, S-EDI313 ✔, S-EDI314 ✔, S-EDI315 ✔, S-EDI316 ✔, S-EDI317 ✔, S-EDI200 ✔, S-EDI201 ✔, S-EDI202 ✔, S-EDI203 ✔, S-EDI274 ✔, S-EDI275 ✔, S-EDI276 ✔, S-EDI213 ✔, S-EDI215 ✔, S-EDI216 ✔, S-EDI271 ✔, S-EDI321 ✔, S-EDI322 ✔, S-EDI323 ✔, S-EDI324 ✔, S-EDI310 ✔, S-EDI311 ✔, S-EDI312 ✔, S-EDI326 ✔, S-EDI258 ✔, S-EDI259 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI294 ✔, S-EDI247 ✔, S-EDI248 ✔, S-EDI249 ✔, S-EDI250 ✔, S-EDI251 ✔, S-EDI253 ✔, S-EDI254 ✔, S-EDI255 ✔, S-EDI256 ✔, S-EDI257 ✔, S-EDI267 ✔, S-EDI272 ✔, S-EDI280 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI283 ✔, S-EDI285 ✔, S-EDI243 ✔, S-EDI244 ✔, S-EDI245 ✔, S-EDI246 ✔, S-EDI303 ✔, S-EDI304 ✔, S-EDI305 ✔, S-EDI307 ✔, S-EDI309 ✔, S-EDI42 ✔, S-EDI50 ✔, S-EDI51 ✔, S-EDI54 ✔, S-EDI56 ✔, S-EDI57 ✔, S-EDI64 ✔, S-EDI97 ✔, S-EDI03 ✔, S-EDI100 ✔, S-EDI101 ✔, S-EDI105 ✔, S-EDI106 ✔, S-EDI10 ✔, S-EDI111 ✔, S-EDI112 ✔, S-EDI115 ✔, S-EDI116 ✔, S-EDI119 ✔, S-EDI11 ✔, S-EDI120 ✔, S-EDI121 ✔, S-EDI122 ✔, S-EDI123 ✔, S-EDI124 ✔, S-EDI126 ✔, S-EDI127 ✔, S-EDI128 ✔, S-EDI129 ✔, S-EDI12 ✔, S-EDI130 ✔, S-EDI131 ✔, S-EDI132 ✔, S-EDI133 ✔, S-EDI134 ✔, S-EDI135 ✔, S-EDI136 ✔, S-EDI137 ✔, S-EDI138 ✔, S-EDI13 ✔, S-EDI14 ✔, S-EDI15 ✔, S-EDI170 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI174 ✔, S-EDI17 ✔, S-EDI180 ✔, S-EDI182 ✔, S-EDI183 ✔, S-EDI187 ✔, S-EDI18 ✔, S-EDI190 ✔, S-EDI194 ✔, S-EDI195 ✔, S-EDI19 ✔, S-EDI21 ✔, S-EDI24 ✔, S-EDI25 ✔, S-EDI28 ✔, S-EDI297 ✔, S-EDI298 ✔, S-EDI299 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI31 ✔, S-EDI33 ✔, S-EDI34 ✔, S-EDI35 ✔, S-EDI36 ✔, S-EDI38 ✔, S-EDI41 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI52 ✔, S-EDI53 ✔, S-EDI55 ✔, S-EDI58 ✔, S-EDI59 ✔, S-EDI60 ✔, S-EDI61 ✔, S-EDI62 ✔, S-EDI63 ✔, S-EDI65 ✔, S-EDI66 ✔, S-EDI67 ✔, S-EDI68 ✔, S-EDI69 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI82 ✔, S-EDI87 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI99 ✔, S-EDI16 ✔, S-EDI45 ✔, S-EDI46 ✔, S-EDI47 ✔, S-EDI01 ✔, S-EDI140 ✔, S-EDI141 ✔, S-EDI142 ✔ | Insertar, conectar, editar; borrador inválido guardable; en la interfaz de escritorio: etapas, transiciones, enlaces y receptividades de un secuencial (P-IMP-32); selección, salto y repetición con el ratón (P-IMP-33), flechas y recorridos manuales persistentes (P-IMP-35), tramos verticales mínimos y transición que se agarra sin sacar rama (P-IMP-36), una flecha por lazo, imán y arrastre desde la paleta (P-IMP-37), receptividades con un programador por bloques y acciones desde la etapa (P-IMP-38); panel de acciones y jerarquías, pendientes |
| REQ-EDT-03 | P/alta | 07 | PARCIAL | editor | T-04c ✔, T-21c ✔, S-EDI247 ✔, S-EDI248 ✔, S-EDI251 ✔, S-EDI222 ✔, S-EDI223 ✔, S-EDI224 ✔, S-EDI225 ✔, S-EDI226 ✔, S-EDI227 ✔, S-EDI234 ✔, S-EDI235 ✔, S-EDI220 ✔, S-EDI221 ✔, S-EDI10 ✔, S-EDI188 ✔, S-EDI195 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI37 ✔, S-EDI01 ✔, S-EDI152 ✔ | Mover, alinear, distribuir y deshacer; zoom en la vista del simulador (P-IMP-29); en la interfaz de escritorio, mover con rejilla de 20 y deshacer o rehacer (P-IMP-32); alinear y distribuir, pendientes en la interfaz |
| REQ-EDT-04 | P/crítica | 07 | IMPL-P | editor | T-21e ✔, S-EDI158 ✔ | Copiar/pegar con IDs nuevos y decisión explícita de referencias externas |
| REQ-EDT-05 | P/crítica | 07 | IMPL-P | editor | T-21f ✔, S-EDI322 ✔, S-EDI233 ✔, S-EDI250 ✔, S-EDI254 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI284 ✔, S-EDI243 ✔, S-EDI245 ✔, S-EDI220 ✔, S-EDI303 ✔, S-EDI304 ✔, S-EDI306 ✔, S-EDI307 ✔, S-EDI309 ✔, S-EDI328 ✔, S-EDI240 ✔, S-EDI241 ✔, S-EDI242 ✔, S-EDI05 ✔, S-EDI102 ✔, S-EDI171 ✔, S-EDI174 ✔, S-EDI178 ✔, S-EDI179 ✔, S-EDI183 ✔, S-EDI184 ✔, S-EDI188 ✔, S-EDI191 ✔, S-EDI196 ✔, S-EDI197 ✔, S-EDI139 ✔, S-EDI145 ✔, S-EDI147 ✔, S-EDI149 ✔, S-EDI150 ✔, S-EDI153 ✔, S-EDI300 ✔, S-EDI301 ✔ | Transacciones atómicas; fallo fuera del historial; rehacer descartado |
| REQ-EDT-06 | P/crítica | 07 | IMPL-P | editor | T-21d ✔, S-EDI08 ✔, S-EDI43 ✔, S-EDI151 ✔, S-EDI156 ✔ | Renombrar sin cambiar ID, usos actualizados, colisión diagnosticada, búsqueda con ruta |
| REQ-EDT-07 | P/alta | 07 | IMPL-P | editor | T-09b ✔, T-21d ✔, S-EDI54 ✔, S-EDI103 ✔, S-EDI104 ✔, S-EDI111 ✔, S-EDI114 ✔, S-EDI117 ✔, S-EDI118 ✔, S-EDI260 ✔, S-EDI261 ✔, S-EDI262 ✔, S-EDI263 ✔, S-EDI264 ✔, S-EDI268 ✔, S-EDI40 ✔, S-EDI43 ✔, S-EDI49 ✔, S-EDI66 ✔, S-EDI79 ✔, S-EDI80 ✔, S-EDI85 ✔, S-EDI94 ✔, S-EDI96 ✔, S-EDI39 ✔, S-FIO37 ✔, S-FIO38 ✔, S-FIO42 ✔, S-FIO67 ✔, S-APP14 ✔, S-APP16 ✔ | Diccionario de variables y usos afectados por un cambio; en la interfaz de escritorio, panel de variables (nombre, papel, tipo, valor inicial, unidad, usos) y acciones de etapa con su diálogo (P-IMP-38) |
| REQ-EDT-08 | P/alta | 07 | PEND-UI | — | T-21g —, S-EDI316 ✔, S-EDI289 ✔, S-EDI291 ✔, S-EDI292 ✔, S-EDI293 ✔, S-EDI294 ✔, S-EDI177 ✔, S-EDI185 ✔, S-EDI186 ✔, S-EDI152 ✔ | Navegación jerárquica |
| REQ-EDT-09 | P/alta | 07 | IMPL-P | diagnostics | T-21b ✔, T-09c ✔, S-EDI310 ✔, S-EDI311 ✔, S-EDI326 ✔, S-EDI327 ✔, S-EDI232 ✔, S-EDI255 ✔, S-EDI257 ✔, S-EDI267 ✔, S-EDI272 ✔, S-EDI06 ✔, S-EDI103 ✔, S-EDI112 ✔, S-EDI118 ✔, S-EDI119 ✔, S-EDI121 ✔, S-EDI122 ✔, S-EDI136 ✔, S-EDI14 ✔, S-EDI174 ✔, S-EDI175 ✔, S-EDI178 ✔, S-EDI183 ✔, S-EDI185 ✔, S-EDI192 ✔, S-EDI261 ✔, S-EDI73 ✔, S-EDI76 ✔, S-EDI77 ✔, S-EDI78 ✔, S-EDI80 ✔, S-EDI81 ✔, S-EDI96 ✔, S-EDI02 ✔, S-EDI157 ✔, S-ESC01 ✔ | Código, gravedad, elemento, evidencia y corrección; panel de diagnósticos del editor de escritorio con clic que selecciona y centra el elemento (P-IMP-32); foco de teclado pendiente |
| REQ-EDT-10 | P/crítica | 07 | IMPL-P | persistence | T-22d ✔, S-EDI09 ✔, S-EDI197 ✔ | Recuperación separada cada 30 s si hay cambios, sin sobrescritura; conectada al editor de escritorio, que la ofrece al arrancar (P-IMP-32) |
| REQ-EDT-11 | P/alta | 07 | PEND-UI | — | T-21h — | Exportación SVG/PDF no implementada en esta iteración (el simulador guarda el dibujo como PNG) |
| REQ-EDT-12 | P/alta | 07 | PEND-UI | — | T-21g —, T-25a ◐ | Diagramas extensos: vista general, zoom y filtros |
| REQ-EDT-13 | P/alta | 07 | PEND-UI | — | T-26a —, T-26b — | Teclado y accesibilidad |
| REQ-EDT-14 | P/crítica | 07 | IMPL-P | editor, engine | T-23d ✔, S-EDI228 ✔, S-EDI252 ✔, S-EDI222 ✔, S-EDI223 ✔, S-EDI226 ✔, S-EDI234 ✔, S-EDI235 ✔, S-EDI246 ✔, S-EDI220 ✔, S-EDI221 ✔, S-EDI03 ✔, S-EDI107 ✔, S-EDI108 ✔, S-EDI109 ✔, S-EDI73 ✔ | Edición semántica = revisión nueva; la ejecución conserva la suya |
| REQ-SIM-01 | P/crítica | 08 | IMPL-P | engine | T-23a ✔, T-23b ✔ | Estados de sesión, pausas en frontera completa, microavance, puntos antes/después |
| REQ-SIM-02 | P/crítica | 08 | IMPL-P | scenario, engine | T-10b ✔, T-23c ✔, S-FIO01 ✔, S-FIO06 ✔, S-FIO11 ✔, S-FIO09 ✔, S-FIO30 ✔, S-FIO51 ✔, S-FIO52 ✔, S-FIO59 ✔, S-FIO61 ✔, S-FIO64 ✔, S-FIO69 ✔, S-FIO16 ✔, S-FIO18 ✔, S-FIO27 ✔, S-FIO29 ✔, S-FIO31 ✔, S-FIO40 ✔, S-FIO47 ✔, S-FIO49 ✔, S-FIO50 ✔, S-FIO53 ✔, S-FIO60 ✔, S-FIO63 ✔, S-APP04 ✔ | Escenarios y entradas manuales registradas con origen y ordinal |
| REQ-SIM-03 | P/alta | 08 | IMPL-P | engine | T-02a ✔, T-02b ✔, T-02c ✔, T-23a ✔, S-EDI288 ✔, S-EDI207 ✔, S-EDI208 ✔, S-EDI209 ✔, S-EDI210 ✔, S-EDI211 ✔, S-EDI212 ✔, S-EDI315 ✔, S-EDI204 ✔, S-EDI213 ✔, S-EDI214 ✔, S-EDI215 ✔, S-EDI217 ✔, S-EDI218 ✔, S-EDI219 ✔, S-EDI269 ✔, S-EDI271 ✔, S-EDI289 ✔, S-EDI321 ✔, S-EDI323 ✔, S-EDI324 ✔, S-EDI327 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI290 ✔, S-EDI252 ✔, S-EDI284 ✔, S-EDI306 ✔, S-EDI109 ✔, S-EDI113 ✔, S-EDI182 ✔, S-EDI190 ✔, S-EDI191 ✔, S-EDI22 ✔, S-EDI265 ✔, S-EDI266 ✔, S-EDI270 ✔, S-EDI27 ✔, S-EDI297 ✔, S-EDI298 ✔, S-EDI299 ✔, S-EDI32 ✔, S-EDI40 ✔, S-EDI78 ✔, S-FIO36 ✔, S-FIO51 ✔, S-FIO64 ✔, S-FIO65 ✔, S-FIO68 ✔, S-FIO08 ✔, S-FIO16 ✔, S-FIO17 ✔, S-FIO19 ✔, S-FIO20 ✔, S-FIO22 ✔, S-FIO24 ✔, S-FIO25 ✔, S-FIO27 ✔, S-FIO28 ✔, S-FIO30 ✔, S-FIO31 ✔, S-FIO32 ✔, S-FIO33 ✔, S-FIO34 ✔, S-FIO35 ✔, S-FIO37 ✔, S-FIO38 ✔, S-FIO39 ✔, S-FIO40 ✔, S-FIO41 ✔, S-FIO42 ✔, S-FIO43 ✔, S-FIO44 ✔, S-FIO45 ✔, S-FIO46 ✔, S-FIO47 ✔, S-FIO48 ✔, S-FIO49 ✔, S-FIO53 ✔, S-FIO54 ✔, S-FIO55 ✔, S-FIO57 ✔, S-FIO60 ✔, S-FIO63 ✔, S-FIO66 ✔, S-FIO67 ✔, S-APP14 ✔, S-APP15 ✔, S-APP05 ✔, S-APP09 ✔, S-APP10 ✔, S-APP11 ✔, S-APP12 ✔, S-APP13 ✔, S-APP16 ✔, S-APP17 ✔, S-APP18 ✔, S-APP19 ✔, S-APP20 ✔ | Observación de actividad, validación, receptividad y franqueamiento |
| REQ-SIM-04 | P/crítica | 08 | IMPL-P | engine | T-23c ✔, T-22f ✔, T-23f ✔, S-FIO21 ✔, S-FIO30 ✔, S-FIO58 ✔, S-FIO59 ✔, S-FIO69 ✔, S-APP17 ✔, S-OPT03d ✔ | Instantánea con Z completo y compatibilidad exacta; dentro de recorrido D-INSTANTANEA-FASE |
| REQ-SIM-05 | P/crítica | 08 | IMPL-P | trace | T-04a ✔, T-22g ✔, S-OPT03b ✔ | Traza con conjuntos E, causas, cierre y digest |
| REQ-SIM-06 | P/crítica | 08 | IMPL-P | engine | T-09d ✔, T-23b ✔ | Observar y pausar no modifican comportamiento |
| REQ-SIM-07 | P/crítica | 08 | IMPL-P | engine | T-23e ✔ | Intervención E en pausa estable, rama auditable |
| REQ-SIM-08 | P/alta | 08 | IMPL-P | diagnostics, engine | T-08a ✔, T-08b ✔, T-16a ✔, S-08a ✔ | Evidencia y corrección recomendada en cada diagnóstico |
| REQ-DAT-01 | P/crítica | 09 | IMPL-P | model, persistence, ids | T-22b ✔, T-21e ✔, S-EDI251 ✔, S-EDI283 ✔, S-EDI308 ✔, S-EDI107 ✔, S-EDI118 ✔, S-EDI124 ✔, S-EDI179 ✔, S-EDI73 ✔, S-EDI77 ✔, S-EDI82 ✔, S-EDI91 ✔, S-EDI98 ✔, S-EDI302 ✔, S-H12 ✔ | Identidades, referencias y propiedad; nombres hexadecimales (H-12) |
| REQ-DAT-02 | P/crítica | 09 | IMPL-P | persistence | T-22a ✔, S-CMP04 ✔, S-EDI04 ✔, S-EDI154 ✔, S-EDI302 ✔, S-FIO04 ✔, S-FIO23 ✔, S-FIO26 ✔, S-FIO56 ✔, S-FIO24 ✔, S-FIO41 ✔, S-FIO46 ✔, S-FIO57 ✔, S-APP01 ✔, S-APP06 ✔ | Ida y vuelta conserva significado, notas y vista (formato 0.1 provisional, U-11) |
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
| REQ-ROB-01 | P/crítica | 10 | IMPL-P | model, engine, persistence | T-08a ✔, T-08b ✔, T-25a ◐, S-FIO02 ✔, S-FIO03 ✔, S-FIO14 ✔, S-FIO07 ✔, S-FIO10 ✔, S-FIO36 ✔, S-FIO52 ✔, S-FIO61 ✔, S-FIO65 ✔, S-FIO68 ✔, S-FIO69 ✔, S-FIO05 ✔, S-FIO56 ✔, S-FIO50 ✔, S-FIO53 ✔, S-FIO54 ✔, S-FIO55 ✔, S-FIO57 ✔, S-FIO62 ✔, S-08a ✔ | Límites de datos y de evolución diagnosticados sin alterar significado |
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
| S-APP05 | REQ-SIM-03 | pasa | `test_SAPP05_ejemplos_en_la_ventana` | cada ejemplo se carga y se dibuja; abrirlo deja Pausa sin estado y, con Play, un clic en una entrada hace |
| S-APP06 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SAPP06_guardar_y_abrir_en_la_ventana` | «Guardar como proyecto» y «Abrir modelo» conservan el modelo y su dibujo. |
| S-APP07 |  | pasa | `test_SAPP07_lecturas_reinician` | Cambiar una lectura reinicia la simulación (queda en Pausa, sin estado, hasta Play) y se señala como distinta de la |
| S-APP08 | REQ-SEM-09 | pasa | `test_SAPP08_ajustes_y_lecturas` | «Ajustes» (entre Simulación y Ayuda) tiene las lecturas; el diálogo no ofrece «detener» y el |
| S-APP09 | REQ-SIM-03 | pasa | `test_SAPP09_play_pausa_y_un_solo_control` | un solo control de ejecución. Play simula en tiempo real (traza abajo, sin paleta) y Pausa detiene y |
| S-APP10 | REQ-SIM-03 | pasa | `test_SAPP10_temporizador_en_dibujo_y_tabla` | «temporizada», con E1 activa y 1 s transcurrido, muestra «1 s» (solo lo transcurrido) encima de la |
| S-APP11 | REQ-SIM-03 | pasa | `test_SAPP11_paneles_plegables` | el panel derecho y el inferior se pliegan del todo con su flecha y desde «Ver»; el estado se guarda. |
| S-APP12 | REQ-SIM-03 | pasa | `test_SAPP12_zoom_se_conserva` | «+», «−» y la rueda con Ctrl cambian el zoom; un refresco lo conserva; «Ajustar» vuelve a encajar. |
| S-APP13 | REQ-SIM-03 | pasa | `test_SAPP13_tiempos_truncados_a_dos_decimales` | lo que lleva un temporizador y τ se muestran truncados a la baja a 2 decimales; el preset, tal cual. |
| S-APP14 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP14_nombres_en_vez_de_id` | un modelo hecho con el editor (ID internos) se dibuja y se traza con los nombres: |
| S-APP15 | REQ-SIM-03 | pasa | `test_SAPP15_ejemplos_no_cambian` | en los ejemplos el ID es el nombre: mostrar nombres no cambia nada del dibujo ni de la traza. |
| S-APP16 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP16_ventana_con_nombres` | un modelo del editor, guardado y abierto en la ventana, muestra nombres en el dibujo, |
| S-APP17 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SAPP17_reiniciar_en_play_y_en_pausa` | Reiniciar vuelve a la situación inicial y en Play sigue en Play; en Pausa, que ya está todo |
| S-APP18 | REQ-EDT-01, REQ-SIM-03 | pasa | `test_SAPP18_abrir_ejemplo_o_modelo_deja_pausa_y_edicion` | al abrir un ejemplo o un modelo guardado, el programa queda parado y editable aunque |
| S-APP19 | REQ-SEM-07, REQ-SIM-03 | pasa | `test_SAPP19_inestable_avisa_una_vez_y_para` | si en Play el motor no alcanza una situación estable (D-LIM-EVOL), se detiene, pasa a |
| S-APP20 | REQ-JER-04, REQ-SIM-03 | pasa | `test_SAPP20_play_con_lecturas_que_no_compilan_avisa_y_queda_en_pausa` | si el modelo compila con las lecturas por defecto pero no con las activas (7.7 = B con una |
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
| S-EDI102 | REQ-ACT-01, REQ-EDT-05 | pasa | `test_SEDI102_borrar_una_etapa_borra_sus_acciones_y_se_restaura` | borrar una etapa borra también sus acciones (del modelo y los borradores unidos); la |
| S-EDI103 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI103_botones_nueva_entrada_salida_memoria` | la tabla de variables tiene «Nueva E», «Nueva S» y «Nueva M» (tooltips Nueva entrada, |
| S-EDI104 | REQ-ACT-01, REQ-EDT-07 | pasa | `test_SEDI104_panel_de_acciones_lista_de_variables_sin_crear_desde_aqui` | la variable se elige en una lista ordenada por papel (Salidas, Memorias) con su tipo; nunca |
| S-EDI105 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI105_programador_de_valor_de_una_accion_memorizada` | el valor de una memorizada se programa en el panel de la acción: una booleana elige entre las fichas |
| S-EDI106 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI106_frase_explicativa_y_condicion_con_bloques_al_lado` | arriba del panel de la acción, una frase la explica según su tipo; la condición (o el |
| S-EDI107 | REQ-DAT-01, REQ-EDT-14 | pasa | `test_SEDI107_comentarios_en_la_presentacion_guardar_deshacer_y_borrar` | el comentario de una etapa o transición se guarda en `presentation.notes` |
| S-EDI108 | REQ-EDT-14 | pasa | `test_SEDI108_campo_comentario_en_las_propiedades` | el panel de propiedades de la etapa y de la transición tiene el campo «Comentario»: confirmarlo es una |
| S-EDI109 | REQ-EDT-14, REQ-SIM-03 | pasa | `test_SEDI109_dibujo_de_los_comentarios_sin_solapes` | el comentario se dibuja entre comillas tipográficas, en cursiva: el de una transición a la |
| S-EDI11 | REQ-EDT-02 | pasa | `test_SEDI11_puntos_de_union` | etapas y transiciones tienen puntos de unión arriba y abajo; al acercarse se marcan y del punto |
| S-EDI111 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI111_paleta_de_bloques_una_ficha_por_elemento` | en Entradas, Salidas, Etapas, Memorias (y Variables del valor) hay una ficha por cada |
| S-EDI112 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI112_panel_de_opciones_etapa_transicion_y_encaje_a_1360x860` | el panel de opciones de abajo muestra, de una etapa, etiqueta, tipo, comentario y |
| S-EDI113 | REQ-SIM-03 | pasa | `test_SEDI113_traza_en_simular_y_leyenda_en_ayuda` | al simular el panel inferior muestra la traza (y se pliega y recuerda como siempre); la leyenda es |
| S-EDI114 | REQ-ACT-01, REQ-EDT-07 | pasa | `test_SEDI114_variables_nuevas_visibles_al_instante_en_la_accion` | con las opciones de la acción a la vista, una variable que se crea, renombra, quita o cambia |
| S-EDI115 | REQ-EDT-02 | pasa | `test_SEDI115_no_colocar_un_elemento_encima_de_otro` | al soltar una ficha de la paleta o al terminar de mover (un elemento o un grupo de acciones), si su caja |
| S-EDI116 | REQ-EDT-02 | pasa | `test_SEDI116_lo_escrito_sin_confirmar_no_se_aplica_a_otro_elemento` | si el elemento mostrado en el panel de opciones cambia sin clic (deshacer, rehacer o selección por |
| S-EDI117 | REQ-ACT-01, REQ-EDT-07 | pasa | `test_SEDI117_lista_de_variables_vacia_o_sin_la_variable_actual` | si no hay ninguna variable que la acción pueda escribir (o la elegida ya no existe), la |
| S-EDI118 | REQ-DAT-01, REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI118_nombres_de_variable_con_cifra_delante` | un nombre como 1M1 o 2S3 (nomenclatura industrial) vale como variable: se |
| S-EDI119 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI119_bloque_parentesis_en_todos_los_programadores` | el bloque «( )» está en la carpeta Operadores de todos los programadores (receptividad |
| S-EDI12 | REQ-EDT-02 | pasa | `test_SEDI12_paleta_arrastrar_y_sin_pedir_receptividad` | los elementos de la paleta, a la izquierda, se arrastran al dibujo; una transicion se coloca sin |
| S-EDI120 | REQ-EDT-02 | pasa | `test_SEDI120_dibujo_del_bloque_parentesis_y_de_las_operaciones_anidadas` | el bloque «( )» se dibuja con un paréntesis a cada lado, tan altos como lo que encierra (también si |
| S-EDI121 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI121_panel_inferior_a_todo_el_ancho_y_laterales_solo_arriba` | el panel inferior ocupa todo el ancho de la ventana, por debajo del dibujo y de los |
| S-EDI122 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI122_opciones_sin_controles_cortados_ni_solapes` | con una acción por evento (programador del valor y del evento a la vez) y con una |
| S-EDI123 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI123_las_acciones_de_una_etapa_apartan_lo_que_estorba` | al añadir acciones a una etapa (Añadir…, el panel o unir una suelta; pegar, en |
| S-EDI124 | REQ-ACT-01, REQ-DAT-01, REQ-EDT-02 | pasa | `test_SEDI124_colocacion_en_matriz_de_dos_columnas` | «En matriz de 2» (menú de la etapa y panel de opciones) coloca las acciones en |
| S-EDI126 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI126_ejemplos_paralelo_y_alternativas_con_una_accion_mas` | en el ejemplo «paralelo», una acción en la etapa B (con la C a 140 de ella) desplaza C, su |
| S-EDI127 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI127_sin_poder_apartar_la_accion_se_queda_encima_con_un_aviso` | si no se puede abrir hueco a la derecha (el obstáculo está debajo de la etapa, o pide más |
| S-EDI128 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI128_editar_una_accion_ya_colocada_aparta_lo_que_pisa` | cambiar la variable (de nombre largo), la condición o el tipo de una acción colocada, o la |
| S-EDI129 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI129_apartar_mueve_barras_acciones_sueltas_y_vias_de_enlaces` | al apartar lo que estorba, lo que queda a la derecha del primer obstáculo se mueve con sus |
| S-EDI13 | REQ-EDT-02 | pasa | `test_SEDI13_propiedades_de_la_etapa` | al seleccionar una etapa, el panel de la izquierda muestra su etiqueta y su tipo, editables. |
| S-EDI130 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI130_el_corte_no_parte_una_columna` | si lo que estorba es una transición de una columna, se mueve la columna entera (etapas y |
| S-EDI131 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI131_una_barra_de_alternativa_tambien_se_aparta` | una barra «O» (se dibuja sin grosor) cuenta como obstáculo, con un alto mínimo: si las |
| S-EDI132 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI132_separar_acciones_no_mueve_nada_y_la_primera_accion_si_despeja` | «Eliminar el enlace» y «Separar» dejan cada acción donde estaba y no mueven ninguna otra |
| S-EDI133 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI133_pegar_una_accion_a_una_etapa_aparta_lo_que_estorba` | pegar una acción suelta a una etapa sigue la misma política que añadirla: si cabe, no se |
| S-EDI134 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI134_cambiar_el_tipo_de_una_accion_aparta_lo_que_estorba` | cambiar el tipo de una acción colocada a otro que se dibuja más ancho («al activar», con |
| S-EDI135 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI135_mover_una_accion_de_orden_aparta_lo_que_estorba` | subir o bajar una acción en la etapa (en una matriz de 2, cuyas columnas toman el ancho de |
| S-EDI136 | REQ-ACT-01, REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI136_renombrar_una_variable_que_ensancha_una_accion_aparta_lo_que_estorba` | renombrar una variable con un nombre más largo ensancha las acciones que la |
| S-EDI137 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI137_sin_hueco_tras_desplazar_se_revierte_el_desplazamiento` | si tras desplazar sigue habiendo algo que estorba (aquí, forzado), lo desplazado se |
| S-EDI138 | REQ-EDT-02 | pasa | `test_SEDI138_la_pila_de_rehacer_queda_como_estaba_si_algo_se_deshace` | una operación atómica que falla con un rehacer pendiente (aunque haga varias operaciones antes de |
| S-EDI139 | REQ-EDT-05, REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI139_macroetapa_con_su_expansion_entrada_y_salida` | `add_macro` crea la macroetapa, su expansión (un parcial dentro del |
| S-EDI14 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI14_propiedades_de_la_transicion` | la receptividad se arma con botones, variables, comparaciones y temporizadores; lo que |
| S-EDI140 | REQ-EDT-02, REQ-JER-04 | pasa | `test_SEDI140_ejemplo_macroetapa_reconstruido_con_el_editor` | el ejemplo «macroetapa» hecho con el editor simula igual que el del constructor. |
| S-EDI141 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI141_ejemplo_encapsulacion_reconstruido_con_el_editor` | el ejemplo «encapsulacion», con un recinto nuevo o con un parcial ya creado, simula |
| S-EDI142 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI142_ejemplo_forzado_reconstruido_con_el_editor` | el ejemplo «forzado» hecho con el editor simula igual que el del constructor: G no |
| S-EDI143 | REQ-JER-02 | pasa | `test_SEDI143_las_cuatro_formas_de_forzado` | explícita, actual, vacía e inicial, hechas con `add_force`, imponen lo mismo que las del |
| S-EDI144 | REQ-JER-05, REQ-MOD-07 | pasa | `test_SEDI144_recintos_varios_encapsulantes_anidadas_y_marcas` | una encapsulante con varios recintos (y una encapsulante dentro de un recinto) se |
| S-EDI145 | REQ-EDT-05, REQ-JER-04, REQ-JER-05, REQ-MOD-07 | pasa | `test_SEDI145_rechazo_de_macroetapas_y_recintos_invalidos` | lo estructuralmente inválido se rechaza con los diagnósticos |
| S-EDI146 | REQ-JER-02, REQ-JER-03 | pasa | `test_SEDI146_rechazo_de_ordenes_de_forzado_invalidas_y_conflicto_posible` | ciclos, referencias y formas inválidas se rechazan; dos órdenes con igual destino y |
| S-EDI147 | REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI147_editar_ordenes_de_forzado` | `set_force` cambia destino, forma, etapas y origen conservando el ID de la orden; |
| S-EDI148 | REQ-JER-06 | pasa | `test_SEDI148_vaciar_un_recinto_activo_sigue_deteniendose_u08` | forzar vacío un recinto con su encapsulante activa se detiene con D-SEM-PENDIENTE (U-08); con |
| S-EDI149 | REQ-EDT-05, REQ-MOD-07 | pasa | `test_SEDI149_borrar_una_macroetapa_con_todo_lo_suyo` | borrar una macroetapa se lleva su expansión, su entrada y su salida, lo de dentro (también |
| S-EDI15 | REQ-EDT-02 | pasa | `test_SEDI15_transiciones_mas_altas_de_acertar` | el area de una transicion es mas alta que su trazo: se acierta sin punteria. |
| S-EDI150 | REQ-EDT-05, REQ-JER-05 | pasa | `test_SEDI150_borrar_encapsulantes_recintos_y_etapas_con_marcas_u_ordenes` | borrar una etapa marcada o una de un conjunto explícito las quita de su recinto y de su |
| S-EDI151 | REQ-EDT-06, REQ-MOD-06 | pasa | `test_SEDI151_renombrar_parciales_y_macroetapas` | `rename` cambia la etiqueta de un parcial o de una macroetapa conservando su ID y la |
| S-EDI152 | REQ-EDT-03, REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI152_mover_la_macroetapa_y_consultar_la_jerarquia` | `move` coloca una macroetapa como a una etapa (solo presentación: la |
| S-EDI153 | REQ-EDT-05 | pasa | `test_SEDI153_deshacer_y_rehacer_cada_operacion_de_jerarquia` | cada operación de jerarquía es una transacción que se deshace y se rehace sin dejar restos, también |
| S-EDI154 | REQ-DAT-02, REQ-JER-07, REQ-MOD-07 | pasa | `test_SEDI154_ida_y_vuelta_y_vista_con_macroetapas_recintos_y_ordenes` | un modelo con macroetapa, recinto con enlace de activación y orden de forzado, |
| S-EDI155 | REQ-JER-05, REQ-MOD-07 | pasa | `test_SEDI155_el_recinto_toma_el_dueno_y_el_contenido_cuenta_en_el_dueno` | `add_enclosure` pone como dueño del parcial el de la encapsulante si no declara |
| S-EDI156 | REQ-EDT-06 | pasa | `test_SEDI156_add_partial_rechaza_un_nombre_repetido` | dos parciales no se llaman igual (D-NOMBRE-COLISION), como al renombrarlos o al crear la expansión |
| S-EDI157 | REQ-EDT-09, REQ-JER-07 | pasa | `test_SEDI157_nombres_visibles_de_ordenes_recintos_y_expansiones_tambien_en_los_diagnosticos` | `display_names` da nombre a las órdenes de forzado, a los recintos y a las expansiones sin |
| S-EDI158 | REQ-EDT-04, REQ-MOD-07 | pasa | `test_SEDI158_pegar_ignora_la_jerarquia_y_pega_las_etapas_como_ordinarias` | `copy` ignora las macroetapas, los recintos y las órdenes (aunque estén en la selección) y |
| S-EDI16 | REQ-EDT-02 | pasa | `test_SEDI16_notacion_del_usuario` | ↑a, ↓a y X1 se traducen a la sintaxis del núcleo y vuelven; los espacios se ignoran al escribir y |
| S-EDI17 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI17_barra_de_simultaneidad` | la simultaneidad es una barra de doble trazo que se arrastra desde la paleta, se |
| S-EDI170 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI170_fichas_macroetapa_y_encapsulante_con_su_dibujo_y_su_ayuda` | la paleta ofrece «Macroetapa» y «Encapsulante» tras las demás fichas; su icono |
| S-EDI171 | REQ-EDT-02, REQ-EDT-05, REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI171_soltar_la_ficha_macroetapa_crea_la_macroetapa_con_su_expansion` | soltar «Macroetapa» crea la macroetapa en el punto, con su |
| S-EDI172 | REQ-EDT-02, REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI172_lo_soltado_en_el_marco_de_la_expansion_es_de_su_parcial` | lo que se suelta dentro de la zona de una expansión (etapa, encapsulante, |
| S-EDI173 | REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI173_una_macroetapa_soltada_en_una_expansion_o_un_recinto_queda_anidada` | una macroetapa soltada dentro de la zona de otra expansión, o en el marco de un recinto, es de |
| S-EDI174 | REQ-EDT-02, REQ-EDT-05, REQ-EDT-09, REQ-JER-05, REQ-MOD-07 | pasa | `test_SEDI174_recinto_vacio_se_ve_se_selecciona_y_se_rellena_arrastrando` | «Añadir recinto…» pide el nombre y crea el recinto de la |
| S-EDI175 | REQ-EDT-09, REQ-JER-05 | pasa | `test_SEDI175_convertir_en_encapsulante_y_volver_a_etapa_ordinaria` | el botón derecho en una etapa ordinaria ofrece «Convertir en encapsulante»; en una |
| S-EDI176 | REQ-JER-05 | pasa | `test_SEDI176_enlace_de_activacion_como_casilla_marcada_o_desmarcada` | el botón derecho en una etapa de un recinto ofrece «Enlace de activación» como casilla (marcada si lo |
| S-EDI177 | REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI177_encuadrar_la_expansion_lleva_la_vista_y_la_resalta_sin_tocar_el_modelo` | «Encuadrar la expansión» en una macroetapa encaja en la vista la zona de su expansión y la |
| S-EDI178 | REQ-EDT-05, REQ-EDT-09, REQ-JER-04 | pasa | `test_SEDI178_borrar_solo_la_entrada_o_la_salida_avisa_y_no_cambia_nada` | borrar solo la entrada o la salida de una expansión (el núcleo lo rechaza con |
| S-EDI179 | REQ-DAT-01, REQ-EDT-05, REQ-MOD-07 | pasa | `test_SEDI179_deshacer_y_rehacer_de_toda_la_jerarquia_y_guardar_y_abrir` | macroetapa, contenido de su expansión, encapsulante, recinto, sus etapas, enlace de |
| S-EDI18 | REQ-EDT-02 | pasa | `test_SEDI18_enlaces_seleccionables_flecha_y_quitar` | un enlace se selecciona con un clic en su trazo; si va de abajo arriba se dibuja con flecha; se |
| S-EDI180 | REQ-EDT-02, REQ-JER-04 | pasa | `test_SEDI180_la_ficha_que_se_arrastra_recuadra_el_parcial_donde_caeria` | al arrastrar una etapa, una encapsulante, una macroetapa o una transición sobre el marco de |
| S-EDI181 | REQ-JER-04, REQ-JER-07 | pasa | `test_SEDI181_marcos_de_los_parciales_como_los_dibuja_el_banco` | el rectángulo de cada parcial que entrega el dibujo (y con el que el editor decide dónde cae lo |
| S-EDI182 | REQ-EDT-02, REQ-JER-04, REQ-SIM-03 | pasa | `test_SEDI182_la_macroetapa_se_enlaza_como_una_etapa_y_lo_construido_simula` | construida con los gestos del editor (ficha de macroetapa, «Añadir debajo», |
| S-EDI183 | REQ-EDT-02, REQ-EDT-05, REQ-EDT-09, REQ-JER-02, REQ-JER-03 | pasa | `test_SEDI183_forzar_un_parcial_crea_la_orden_con_nombres_y_en_una_sola_operacion` | «Forzar un parcial…» en una etapa pide (gancho |
| S-EDI184 | REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI184_la_caja_de_la_orden_se_selecciona_y_se_edita_o_se_quita_desde_su_menu` | la caja «R{…}» de una orden se selecciona con un clic (no se arrastra: no es una acción) y |
| S-EDI185 | REQ-EDT-08, REQ-EDT-09, REQ-JER-07 | pasa | `test_SEDI185_el_panel_de_opciones_muestra_la_ficha_de_jerarquia_con_los_botones_del_menu` | al seleccionar una macroetapa, una encapsulante, una etapa de un recinto, la |
| S-EDI186 | REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI186_encuadrar_la_macroetapa_o_la_encapsulante_y_doble_clic_son_solo_navegacion` | «Encuadrar la macroetapa» en la entrada y la salida de una expansión (y en su zona), |
| S-EDI187 | REQ-EDT-02, REQ-JER-04 | pasa | `test_SEDI187_la_zona_de_suelta_de_un_parcial_incluye_un_margen_a_la_derecha_y_debajo` | lo que se suelta a una etapa de ancho (a la derecha) o de alto (debajo) del marco de un |
| S-EDI188 | REQ-EDT-03, REQ-EDT-05, REQ-JER-05 | pasa | `test_SEDI188_el_marco_de_un_recinto_vacio_se_arrastra_con_una_sola_operacion_de_deshacer` | el marco de un recinto sin etapas se mueve arrastrando su borde (a la rejilla; se |
| S-EDI189 | REQ-ACT-01, REQ-MOD-07 | pasa | `test_SEDI189_las_condiciones_de_una_accion_se_leen_en_el_parcial_de_su_etapa` | la condición, el valor o el evento de una acción se comprueban con los nombres del parcial de |
| S-EDI19 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI19_alternativas_con_el_raton` | la alternativa (O) no es un elemento: se construye con el raton. Una segunda transicion |
| S-EDI190 | REQ-EDT-02, REQ-JER-02, REQ-SIM-03 | pasa | `test_SEDI190_el_ejemplo_forzado_construido_solo_con_gestos_simula_como_el_del_constructor` | el ejemplo «forzado» rehecho con gestos del editor (fichas, enlaces, |
| S-EDI191 | REQ-EDT-05, REQ-JER-02, REQ-SIM-03 | pasa | `test_SEDI191_el_ejemplo_forzado_abierto_se_edita_su_orden_con_el_menu_y_simula_igual` | sobre el ejemplo «forzado» del constructor, el botón derecho en la caja «G{B}» |
| S-EDI192 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SEDI192_dialogo_de_la_orden_de_forzado_con_nombres_formas_y_etapas` | el diálogo de «Forzar un parcial…» (el de la ventana, sustituible) ofrece los parciales por su |
| S-EDI193 | REQ-JER-04, REQ-MOD-03, REQ-MOD-07 | pasa | `test_SEDI193_una_macroetapa_unida_a_una_barra_se_ve_unida_en_la_vista` | una etapa y una macroetapa por encima de una barra de simultaneidad Y y la barra |
| S-EDI194 | REQ-EDT-02, REQ-JER-04, REQ-MOD-03 | pasa | `test_SEDI194_la_macroetapa_unida_a_una_barra_se_ve_unida_a_ella_en_el_editor` | una etapa y una macroetapa unidas con el ratón por encima de una barra Y, y la |
| S-EDI195 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI195_un_enlace_soltado_en_el_borde_o_el_nombre_de_un_marco_abre_la_rama_como_en_un_hueco` | soltar el enlace que sale de un punto de unión en el borde o en el nombre del marco de un |
| S-EDI196 | REQ-EDT-05, REQ-JER-02, REQ-JER-05 | pasa | `test_SEDI196_borrar_avisa_de_las_ordenes_y_los_recintos_que_pierden_etapas` | el aviso de borrado enseña, con nombres, el recinto que pierde su enlace de |
| S-EDI197 | REQ-EDT-05, REQ-EDT-10 | pasa | `test_SEDI197_un_borrado_rechazado_deja_la_marca_de_cambios_como_estaba` | si `borrar` se rechaza (la entrada de una expansión sola, junto a una barra que ya se había |
| S-EDI20 | REQ-MOD-03 | pasa | `test_SEDI20_sentido_del_enlace_segun_el_trazo` | de arriba abajo, el enlace no lleva flecha; de abajo arriba, si (sale solo del trazo). |
| S-EDI200 | REQ-EDT-02 | pasa | `test_SEDI200_la_barra_del_negado_es_una_linea_de_2_px_sobre_la_palabra` | la barra de una variable negada es una línea propia de 2 px (el sobrerrayado del texto es de 1 px y |
| S-EDI201 | REQ-EDT-02 | pasa | `test_SEDI201_la_barra_cubre_cada_tramo_negado_en_receptividades_condiciones_y_eventos` | un tramo de segmentos negados seguidos (NOT (p AND q), NOT X(A) con su subíndice) lleva una sola |
| S-EDI202 | REQ-EDT-02 | pasa | `test_SEDI202_la_barra_no_cambia_anchos_ni_disposicion` | la barra no cambia lo que mide un texto ni dónde caen las cajas de las acciones (la disposición no |
| S-EDI203 | REQ-EDT-02 | pasa | `test_SEDI203_dibujo_js_y_css_pintan_la_misma_barra` | el banco web (tools/dibujo.js y dibujo.css) pinta la barra del negado como una línea propia de 2 px, |
| S-EDI204 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SEDI204_el_estado_del_temporizador_es_solo_lo_transcurrido` | antes de empezar no hay nada que mostrar; mientras cuenta, solo el tiempo transcurrido |
| S-EDI205 | REQ-TMP-01 | pasa | `test_SEDI205_dos_temporizadores_de_la_misma_duracion_se_distinguen_por_su_orden` | «3s/p OR 3s/q/2s»: cada temporizador apunta a su propia aparición de «3s» en el texto; el de |
| S-EDI206 | REQ-TMP-01 | pasa | `test_SEDI206_las_acciones_con_retardo_se_marcan_en_el_modelo_sin_depender_del_estado` | la acción con un retardo en su condición o su evento lleva `tmr` (para reservarle sitio arriba); la |
| S-EDI207 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SEDI207_el_tiempo_transcurrido_va_centrado_encima_de_la_duracion` | en la receptividad «ok·3s/XB» el «1 s» se centra encima del «3s» (no a la derecha), justo |
| S-EDI208 | REQ-SIM-03 | pasa | `test_SEDI208_si_no_se_localiza_la_duracion_se_centra_sobre_toda_la_receptividad` | un temporizador cuya duración no está en el texto (token desconocido) se centra encima de toda la |
| S-EDI209 | REQ-SIM-03 | pasa | `test_SEDI209_el_tiempo_transcurrido_no_pisa_la_barra_de_la_transicion_ni_el_texto` | el tiempo transcurrido de una receptividad no toca el trazo de la transición, ni su designación, ni el |
| S-EDI21 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI21_abrir_ramas_con_el_raton_de_verdad` | con eventos de raton reales sobre el dibujo (pulsar, mover, soltar): arrastrar de un punto |
| S-EDI210 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SEDI210_condicion_y_evento_de_una_accion_llevan_su_tiempo_encima_de_su_duracion` | en una acción con condición temporizada, y en una memorizada con un evento con retardo, |
| S-EDI211 | REQ-SIM-03 | pasa | `test_SEDI211_el_tiempo_de_una_accion_con_retardo_no_pisa_la_caja_de_arriba` | en una columna de acciones, el tiempo transcurrido de la segunda cabe en el hueco que la disposición le |
| S-EDI212 | REQ-SIM-03 | pasa | `test_SEDI212_dibujo_js_coloca_el_tiempo_encima_de_la_duracion_igual_que_qt` | el banco web escribe solo lo transcurrido encima de la duración (token y aparición, o todo el texto), con |
| S-EDI213 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI213_la_rueda_hace_zoom_anclada_al_puntero` | con la rueda, el punto del dibujo que está bajo el cursor se queda bajo el cursor (a menos |
| S-EDI214 | REQ-SIM-03 | pasa | `test_SEDI214_la_rueda_ancla_tambien_con_mucho_zoom_y_cerca_del_borde_de_la_escena` | tras acercar al máximo y desplazarse hasta el borde, la rueda sigue anclada (la escena tiene margen |
| S-EDI215 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI215_centrar_todo_deja_todo_lo_dibujado_dentro_y_centrado` | «Centrar todo» (el botón, `ajustar` y Ctrl+0 del menú) encaja y centra todo el dibujo con |
| S-EDI216 | REQ-EDT-02 | pasa | `test_SEDI216_centrar_todo_al_editar_encaja_lo_dibujado_y_no_el_area_minima` | al editar, «Centrar todo» encaja y centra los elementos dibujados (un dibujo pequeño se amplía), no el |
| S-EDI217 | REQ-SIM-03 | pasa | `test_SEDI217_alejar_no_deja_el_dibujo_fuera_de_la_vista` | a cualquier zoom, hasta el mínimo y desplazándose hasta cualquier extremo, queda a la vista al menos |
| S-EDI218 | REQ-SIM-03 | pasa | `test_SEDI218_zoom_manual_fijo_hasta_centrar_y_doble_clic_al_simular` | tras hacer zoom con la rueda la vista no se reajusta sola (ni al refrescar ni al cambiar de tamaño) |
| S-EDI219 | REQ-SIM-03 | pasa | `test_SEDI219_arrastrar_el_dibujo_con_la_mano_deja_la_vista_manual_y_los_botones_zoomean_al_centro` | al simular, arrastrar el dibujo lo deja donde se suelta (no se reencaja con el siguiente refresco); «+» y |
| S-EDI22 | REQ-SIM-03 | pasa | `test_SEDI22_ejemplo_alternativas` | el ejemplo «alternativas» se simula, se dibuja con la flecha de union y se puede editar. |
| S-EDI220 | REQ-EDT-03, REQ-EDT-05, REQ-EDT-14 | pasa | `test_SEDI220_mover_varios_en_una_sola_operacion_y_deshacerla_entera` | `move_many` mueve etapas, transiciones, barras y acciones sueltas a la vez, con |
| S-EDI221 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI221_mover_varios_crea_la_posicion_que_falta_y_quita_estilos` | un elemento sin posición guardada (por ejemplo un recinto vacío) la recibe al moverse; un |
| S-EDI222 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI222_cadena_lineal_con_distancias_irregulares_queda_a_la_distancia_estandar` | una cadena de etapas y transiciones con distancias irregulares queda con la misma |
| S-EDI223 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI223_la_cadena_se_alcanza_desde_cualquier_elemento_enlace_o_parcial_y_las_aisladas_no_cuentan` | la cadena de un elemento es la componente conexa de etapas, macroetapas y transiciones |
| S-EDI224 | REQ-ACT-01, REQ-EDT-03 | pasa | `test_SEDI224_una_etapa_con_muchas_acciones_aumenta_la_distancia_con_el_nivel_siguiente` | lo que sobresale por debajo de una etapa (`extent`, el alto de sus acciones en columna) pide |
| S-EDI225 | REQ-EDT-03, REQ-MOD-03 | pasa | `test_SEDI225_alternativas_y_simultaneidad_con_barras_a_mitad_de_la_distancia` | las ramas de una alternativa quedan al mismo nivel; en una simultaneidad, las etapas de una |
| S-EDI226 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI226_el_enlace_de_realimentacion_y_las_rutas_manuales` | el enlace que vuelve hacia arriba no cuenta para los niveles (una repetición de secuencia no |
| S-EDI227 | REQ-EDT-03, REQ-JER-04 | pasa | `test_SEDI227_una_cadena_sin_enlaces_con_otras_partes_y_los_parciales_no_se_mezclan` | un enlace entre elementos de parciales distintos no los une en una cadena (cada una se reparte |
| S-EDI228 | REQ-EDT-14, REQ-MOD-03 | pasa | `test_SEDI228_bar_link_enlaza_todas_las_parejas_aunque_alguna_sea_un_borrador` | unir un elemento a una barra enlaza en el modelo CADA pareja (arriba, abajo), también si |
| S-EDI229 | REQ-JER-04, REQ-JER-05, REQ-MOD-03, REQ-MOD-07, REQ-SIM-03 | pasa | `test_SEDI229_una_transicion_sobre_una_barra_activa_todo_lo_que_cuelga_de_ella` | una transición con una barra Y debajo y de ella una |
| S-EDI23 | REQ-MOD-03 | pasa | `test_SEDI23_el_punto_de_arriba_recibe_y_el_enlace_entra_por_arriba` | lo que se arrastra desde el punto de arriba de una transicion es lo que le llega (viene de la etapa |
| S-EDI230 | REQ-MOD-03, REQ-SEM-02 | pasa | `test_SEDI230_una_barra_sobre_una_transicion_exige_todas_las_etapas_de_arriba` | varias etapas por encima de una barra Y y una transición debajo: la transición solo se |
| S-EDI231 | REQ-MOD-03 | pasa | `test_SEDI231_dos_transiciones_sobre_una_barra_son_dos_enlaces_independientes` | lo que `bar_link` crea con transiciones por encima de una barra y una etapa por debajo son los enlaces |
| S-EDI232 | REQ-EDT-09, REQ-MOD-03 | pasa | `test_SEDI232_dos_etapas_a_cada_lado_de_una_barra_no_ejecutan_y_se_diagnostican` | una barra entre etapas sin transición (o entre transiciones) deja borradores no ejecutables |
| S-EDI233 | REQ-EDT-05, REQ-MOD-03 | pasa | `test_SEDI233_desunir_y_borrar_la_barra_quitan_solo_sus_enlaces` | quitar un elemento de la barra quita sus enlaces con los del otro lado (y solo esos), borrar |
| S-EDI234 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI234_un_enlace_dibujado_hacia_arriba_que_no_cierra_ningun_ciclo_cuenta_como_descendente` | solo es de realimentación el enlace que vuelve hacia arriba Y cierra un ciclo; si una transición |
| S-EDI235 | REQ-EDT-03, REQ-EDT-14 | pasa | `test_SEDI235_equidistanciar_cualquier_grafo_deja_la_x_en_la_rejilla_sin_tocar_el_modelo_y_es_idempotente` | con cientos de grafos al azar (varias etapas, transiciones con varias etapas antes y después, |
| S-EDI24 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI24_entrada_de_transicion_a_enlace_de_salida` | arrastrar la entrada a un enlace de salida crea otra alternativa, no una simultaneidad. |
| S-EDI240 | REQ-ACT-01, REQ-EDT-05 | pasa | `test_SEDI240_supr_sobre_la_caja_de_una_accion_quita_solo_la_accion` | tras un clic en la caja de la acción de una etapa (la etapa queda seleccionada y la acción |
| S-EDI241 | REQ-EDT-05 | pasa | `test_SEDI241_supr_con_la_etapa_seleccionada_o_varias_cosas_borra_lo_seleccionado` | para borrar la etapa hay que seleccionarla (un clic en la etapa deja de señalar la acción; también |
| S-EDI242 | REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI242_supr_sobre_una_orden_de_forzado_quita_solo_la_orden` | un clic en la caja de una orden de forzado la selecciona (la etapa no) y Supr quita solo la |
| S-EDI243 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SEDI243_varios_seleccionados_se_mueven_juntos_desde_el_primer_clic` | tras seleccionar con el lazo varios elementos (etapas, transiciones, una barra, acciones |
| S-EDI244 | REQ-EDT-02 | pasa | `test_SEDI244_un_clic_sin_mover_deja_solo_ese_elemento_y_mayus_sigue_sumando_y_quitando` | soltar sin haberse movido (un clic simple) sobre un miembro de la selección múltiple deja seleccionado solo |
| S-EDI245 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SEDI245_si_lo_que_se_mueve_queda_encima_de_algo_que_no_se_mueve_vuelve_a_su_sitio` | el mismo aviso de solape que al mover un elemento: si el resultado de mover varios deja algo |
| S-EDI246 | REQ-EDT-02, REQ-EDT-14 | pasa | `test_SEDI246_las_rutas_de_los_enlaces_con_los_dos_extremos_movidos_se_desplazan_con_ellos` | al mover un grupo, las rutas manuales (coordenadas absolutas laneX, exitY, entryY, middleY) de |
| S-EDI247 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI247_el_menu_ofrece_equidistanciar_en_cada_elemento_de_la_cadena_y_en_el_hueco` | el botón derecho en una etapa, una transición o un enlace de una cadena ofrece «Equidistanciar |
| S-EDI248 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI248_la_seleccion_y_todo_el_lienzo_equidistancian_las_cadenas_que_tocan` | con varios elementos seleccionados, el botón derecho en un hueco o en uno de ellos ofrece |
| S-EDI249 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI249_las_acciones_de_una_etapa_piden_mas_altura_y_no_se_solapan_con_el_nivel_siguiente` | una etapa con tres acciones en columna (que llegan hasta 134 por debajo de su centro) separa |
| S-EDI25 | REQ-EDT-02 | pasa | `test_SEDI25_arrastrar_desde_linea_de_seleccion` | clic selecciona un enlace; arrastre desde él abre otra rama en una transacción. |
| S-EDI250 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SEDI250_si_algo_quedaria_encima_de_otro_elemento_no_se_equidistancia_y_se_avisa` | si al equidistanciar un elemento de la cadena quedara encima de otro que no es de ella, no |
| S-EDI251 | REQ-DAT-01, REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI251_con_una_barra_de_simultaneidad_cada_barra_va_a_mitad_y_se_guarda_y_se_abre` | una barra enlazada con el ratón entre una transición y dos etapas se alcanza |
| S-EDI252 | REQ-EDT-14, REQ-SIM-03 | pasa | `test_SEDI252_lo_equidistanciado_no_cambia_lo_que_se_simula` | equidistanciar es solo presentación: el grafcet se simula igual antes y después, con los |
| S-EDI253 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI253_la_orden_de_forzado_es_una_ficha_de_la_paleta_como_las_demas` | la paleta ofrece «Forzado» (la orden de forzado: rectángulo doble con «G{ }») tras las |
| S-EDI254 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02, REQ-JER-03 | pasa | `test_SEDI254_soltar_la_ficha_sobre_una_etapa_la_une_a_ella_y_el_dialogo_la_completa_y_pasa_al_modelo` | arrastrar la ficha sobre una etapa la resalta como destino; soltarla |
| S-EDI255 | REQ-EDT-02, REQ-EDT-09, REQ-JER-02 | pasa | `test_SEDI255_cancelar_el_dialogo_no_haber_otro_parcial_o_un_ciclo_no_cambian_nada_y_encima_de_otro_elemento_no_se_coloca` | soltar la ficha encima de una transición, una macroetapa, una barra o una acción |
| S-EDI256 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI256_la_accion_de_una_etapa_de_la_seleccion_mueve_el_grupo_y_un_clic_la_senala` | con la etapa y sus acciones seleccionadas (lazo), pulsar la caja de una acción no deshace la |
| S-EDI257 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI257_las_ocho_fichas_se_ven_enteras_en_cuatro_filas_a_1366x768` | con la ficha «Forzado» la paleta pasó de tres a cuatro filas de 84 de alto (340 en total, sin |
| S-EDI258 | REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-MOD-03, REQ-SIM-03 | pasa | `test_SEDI258_una_transicion_unida_con_el_raton_a_una_barra_activa_todo_lo_de_debajo_en_cualquier_parcial` | con los gestos del editor (arrastrar de punto de unión a |
| S-EDI259 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI259_la_barra_con_una_etapa_y_una_transicion_por_encima_no_pierde_los_enlaces_de_la_transicion` | con una etapa y una transición por encima de la misma barra (y varias etapas debajo), unidas |
| S-EDI26 | REQ-MOD-03 | pasa | `test_SEDI26_geometria_comun_retorno_y_movimiento` | uniones comunes, retorno fuera de la etapa, flecha automática y recorridos iguales en Qt/web. |
| S-EDI260 | REQ-EDT-07 | pasa | `test_SEDI260_supr_quita_la_variable_seleccionada_como_el_boton` | Supr con una fila seleccionada en la tabla de variables la quita directamente, por el mismo camino que |
| S-EDI261 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI261_supr_de_una_variable_en_uso_se_rechaza_igual_que_quitar` | si el núcleo no deja quitar la variable (se usa), Supr enseña el mismo motivo que el |
| S-EDI262 | REQ-EDT-07 | pasa | `test_SEDI262_supr_con_la_celda_en_edicion_es_del_editor_y_no_borra_el_dibujo` | con el editor de una celda abierto Supr borra texto, no la fila; con la tabla enfocada Supr es de la |
| S-EDI263 | REQ-EDT-07 | pasa | `test_SEDI263_supr_con_varias_filas_y_filas_sin_nombre` | con varias filas seleccionadas Supr las quita todas (una operación de deshacer por variable); si el |
| S-EDI264 | REQ-EDT-07 | pasa | `test_SEDI264_supr_solo_actua_al_editar` | fuera del modo edición (en Play) la tabla de variables no responde a Supr; al volver a Pausa, sí. |
| S-EDI265 | REQ-SIM-03 | pasa | `test_SEDI265_boton_conmutador_entre_es_externas_y_vista_grafcet` | un solo botón conmuta entre el dibujo GRAFCET y las E/S externas: «E/S externas» y su icono en el |
| S-EDI266 | REQ-SIM-03 | pasa | `test_SEDI266_el_estado_de_conexion_hace_salto_de_linea_y_no_se_corta` | el estado de la conexión del panel de E/S ocupa su propia fila bajo el título, hace salto de línea y |
| S-EDI267 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI267_la_paleta_se_encoge_en_ventanas_bajas_sin_subir_el_minimo_de_alto_de_la_ventana` | la paleta de cuatro filas pide su alto (340) pero se encoge hasta tres filas, con barra |
| S-EDI268 | REQ-EDT-07 | pasa | `test_SEDI268_supr_del_teclado_numerico_tambien_quita_la_variable` | el Supr del teclado numérico (con el modificador de teclado numérico) actúa igual que el Supr normal en la |
| S-EDI269 | REQ-SIM-03 | pasa | `test_SEDI269_un_clic_con_temblor_no_deja_la_vista_manual_y_el_arrastre_empieza_pasada_la_distancia` | al simular, un clic en el que el ratón se mueve menos que la distancia de arrastre del sistema (el temblor |
| S-EDI27 | REQ-SIM-03 | pasa | `test_SEDI27_ejemplos_seleccion_salto_repeticion` | las ramas construidas ejecutan selección, salto y repetición sin cambiar el motor. |
| S-EDI270 | REQ-SIM-03 | pasa | `test_SEDI270_el_boton_conmutador_mide_lo_mismo_en_las_dos_vistas_y_no_mueve_la_barra` | el botón «E/S externas» / «Vista GRAFCET» tiene un ancho fijo, el del más ancho de sus dos estados (texto e |
| S-EDI271 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI271_centrar_todo_dice_su_atajo_y_el_doble_clic_de_la_simulacion` | la ayuda del botón «Centrar todo» cita Ctrl+0 y, al simular, el doble clic (que también |
| S-EDI272 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI272_el_divisor_movido_a_mano_se_respeta_aunque_la_paleta_no_quepa_entera` | la paleta solo gana su alto completo mientras el divisor entre el dibujo y el panel inferior |
| S-EDI273 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI273_la_leyenda_dice_que_los_trazos_de_dependencia_solo_se_ven_con_el_boton_y_no_habla_de_la_navegacion_antigua` | la leyenda de la ventana ya no dice que la macroetapa va unida a su expansión por |
| S-EDI274 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI274_el_nombre_de_la_encapsulante_va_a_caballo_del_trazo_superior_de_su_recinto_sobre_su_fondo` | el nombre de la encapsulante se escribe centrado sobre el marco de su recinto, con su línea |
| S-EDI275 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI275_dibujo_js_coloca_el_nombre_de_la_encapsulante_igual_que_escritorio` | tools/dibujo.js escribe el nombre de la encapsulante a caballo del trazo de arriba (línea base 5 |
| S-EDI276 | REQ-EDT-02 | pasa | `test_SEDI276_centrar_todo_deja_a_la_vista_el_nombre_y_el_marco_no_depende_de_el` | el nombre sobresale la mitad del marco, así que la caja del dibujo lo incluye y «Centrar todo» lo deja a la |
| S-EDI28 | REQ-EDT-01, REQ-EDT-02 | pasa | `test_SEDI28_salto_inverso_guardar_y_reabrir` | arrastrar la entrada de una etapa a una salida crea el salto; persiste y se deshace entero. |
| S-EDI280 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI280_la_ficha_grafcet_parcial_es_una_ficha_mas_de_la_paleta` | la paleta ofrece «Grafcet parcial» (marco redondeado con «G») antes de «Forzado», con su |
| S-EDI281 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI281_soltar_la_ficha_en_un_hueco_crea_un_parcial_vacio_con_nombre_unico_y_su_marco` | soltar «Grafcet parcial» en un hueco crea, en una sola operación de deshacer, un |
| S-EDI282 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI282_el_marco_vacio_se_selecciona_se_mueve_se_rellena_y_se_renombra` | el marco vacío de un parcial suelto se agarra por su borde (dentro no hay nada que |
| S-EDI283 | REQ-DAT-01, REQ-EDT-01, REQ-EDT-02 | pasa | `test_SEDI283_un_parcial_suelto_sin_etapas_sobrevive_a_guardar_y_abrir_con_su_marco_en_su_sitio` | dos parciales sueltos sin etapas se guardan y se abren (formato actual, sin |
| S-EDI284 | REQ-EDT-05, REQ-JER-02, REQ-JER-03, REQ-SIM-03 | pasa | `test_SEDI284_un_parcial_suelto_es_destino_de_la_ficha_forzado_y_se_borra_con_aviso_y_un_deshacer` | un parcial suelto sale en el diálogo de la ficha «Forzado» (con sus |
| S-EDI285 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI285_el_menu_del_hueco_ofrece_un_grafcet_parcial_nuevo_aqui` | el botón derecho en un hueco ofrece «Nuevo grafcet parcial aquí» (lo mismo que soltar la |
| S-EDI286 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI286_por_defecto_no_hay_trazos_de_dependencia_y_con_la_opcion_aparecen_los_de_macroetapa_y_encapsulante` | sin la opción (por defecto) no se dibuja ningún trazo discontinuo de dependencia; |
| S-EDI287 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI287_mostrar_u_ocultar_las_dependencias_no_cambia_la_disposicion_los_marcos_ni_la_seleccion` | lo único que cambia al mostrar las dependencias son sus trazos: el resto de lo |
| S-EDI288 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI288_el_boton_mostrar_dependencias_de_la_vista_conmuta_repinta_y_se_recuerda` | la vista tiene el botón conmutable «Mostrar dependencias» tras los controles del zoom, apagado |
| S-EDI289 | REQ-EDT-08, REQ-JER-07, REQ-SIM-03 | pasa | `test_SEDI289_encuadrar_encaja_y_centra_un_rectangulo_con_margen_y_el_tope_de_centrar_todo` | `encuadrar(r)` encaja y centra en la vista el rectángulo de escena `r` con el mismo |
| S-EDI29 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI29_flecha_arrastrar_y_ocultar_sin_cambiar_modelo` | mover y ocultar la flecha son presentación; un arrastre, un deshacer. La flecha sigue |
| S-EDI290 | REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-SIM-03 | pasa | `test_SEDI290_el_boton_mostrar_dependencias_esta_junto_al_zoom_en_edicion_y_en_simulacion_y_se_recuerda` | «Mostrar dependencias» es un botón conmutable junto a los controles del |
| S-EDI291 | REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI291_encuadrar_la_expansion_encaja_su_zona_con_margen_y_la_resalta` | «Encuadrar la expansión» (botón derecho y doble clic en la macroetapa, y su botón del panel) |
| S-EDI292 | REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI292_encuadrar_la_macroetapa_desde_su_expansion_y_el_tope_de_zoom` | al revés, «Encuadrar la macroetapa» (en la zona de la expansión seleccionada y en su entrada |
| S-EDI293 | REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI293_encuadrar_el_recinto_y_la_encapsulante_en_los_dos_sentidos` | desde una encapsulante, «Encuadrar el recinto» (o «los recintos», con varios, todos juntos) |
| S-EDI294 | REQ-EDT-02, REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI294_las_ayudas_y_las_fichas_hablan_de_encuadrar_y_no_de_la_navegacion_antigua` | la ayuda de las fichas de la paleta y del panel de opciones, y los botones de la |
| S-EDI296 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI296_dibujo_js_acepta_la_misma_opcion_apagada_por_defecto_y_calcula_igual_los_trazos_del_recinto` | tools/dibujo.js y escritorio/diagrama.py tienen la misma opción, `dependencias`, |
| S-EDI297 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI297_guardar_el_dibujo_como_imagen_respeta_mostrar_dependencias` | «Guardar el dibujo como imagen» dibuja con el estado actual del botón «Mostrar |
| S-EDI298 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI298_las_fichas_1_y_0_se_arrastran_a_una_receptividad_vacia` | la carpeta «Constantes» del programador trae las fichas 1 (verdadero) y 0 (falso); soltada en |
| S-EDI299 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI299_las_fichas_1_y_0_con_operadores_se_escriben_y_franquean_como_corresponde` | «1» y «0» combinadas con «y», «o» y «no» se escriben con 1 y 0 en la notación del usuario, se |
| S-EDI30 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI30_recolocar_retorno_y_mover_etapa` | tiradores para carril y alturas; extremos conectados al mover etapas. El recorrido no |
| S-EDI300 | REQ-EDT-01, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI300_un_borrador_de_forzado_guarda_destino_forma_y_etapas_y_se_valida` | `add_draft_action` y `update_draft_action` admiten el tipo «forzado» con su parcial |
| S-EDI301 | REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI301_borrar_el_parcial_o_las_etapas_a_las_que_apunta_una_orden_sin_completar_le_quita_el_destino_y_se_deshace` | al borrar el parcial destino la orden sin completar pierde su destino y sus etapas; al borrar una |
| S-EDI302 | REQ-DAT-01, REQ-DAT-02, REQ-JER-02 | pasa | `test_SEDI302_el_borrador_de_forzado_se_guarda_y_se_abre_sin_perder_nada_y_no_se_simula` | un proyecto con una orden de forzado suelta y otra unida a una etapa sin destino se |
| S-EDI303 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI303_soltar_la_ficha_en_un_hueco_crea_una_orden_suelta_con_su_rectangulo_doble_y_sin_efecto` | soltar la ficha «Forzado» en un hueco, como la de una acción, crea una orden suelta |
| S-EDI304 | REQ-ACT-01, REQ-EDT-02, REQ-EDT-05 | pasa | `test_SEDI304_se_mueve_como_una_accion_suelta_y_se_pega_al_lado_de_otra_en_un_grupo` | la orden suelta se agarra por su caja y se mueve a la rejilla (una sola operación de |
| S-EDI305 | REQ-ACT-01, REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI305_se_une_a_una_etapa_con_el_mismo_gesto_que_una_accion_y_sin_destino_no_tiene_efecto` | se une a una etapa arrastrando de su punto de unión izquierdo a la etapa, o del lado |
| S-EDI306 | REQ-EDT-05, REQ-JER-02, REQ-JER-03, REQ-SIM-03 | pasa | `test_SEDI306_al_configurar_el_destino_pasa_al_modelo_en_una_operacion_y_fuerza_al_simular` | con el diálogo de la orden (doble clic o «Configurar orden de forzado…») |
| S-EDI307 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI307_separarla_de_su_etapa_la_devuelve_a_borrador_suelto_con_todos_sus_datos` | quitar el enlace de la etapa con sus acciones (o «Separar de la etapa») deja la orden |
| S-EDI308 | REQ-DAT-01, REQ-EDT-01, REQ-JER-02 | pasa | `test_SEDI308_guardar_y_abrir_conserva_la_orden_suelta_y_la_unida_sin_destino` | una orden suelta (ya configurada) y otra unida a una etapa sin destino se guardan y se |
| S-EDI309 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI309_el_menu_el_doble_clic_el_panel_y_supr_de_la_orden_sin_completar` | el botón derecho en la orden sin completar ofrece configurarla y quitarla (y separarla |
| S-EDI31 | REQ-EDT-02 | pasa | `test_SEDI31_flecha_union_horizontal_independiente` | la flecha de unión no sale por defecto (el enlace baja); se muestra, se mueve y se oculta; la |
| S-EDI310 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI310_el_cuadro_de_no_compila_y_el_panel_dicen_los_nombres_aunque_los_nombres_esten_desfasados` | con la barra Y de dos etapas arriba y una debajo, el resumen de lo que impide simular, el |
| S-EDI311 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI311_los_rechazos_los_avisos_y_los_nombres_de_los_elementos_no_enseñan_ids` | ningún mensaje de la edición (`mensaje`, `informar`, `rechazar`) deja un ID interno, que se cambia |
| S-EDI312 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI312_los_recintos_nuevos_se_llaman_g1_g2_con_el_mismo_contador_que_los_parciales_sueltos_y_las_macroetapas` | «Añadir recinto…» propone G1, G2… (antes R1, R2…): el primer nombre libre entre los parciales y |
| S-EDI313 | REQ-EDT-02, REQ-JER-04 | pasa | `test_SEDI313_el_marco_del_parcial_rodea_el_retorno_los_enlaces_los_textos_y_las_acciones` | el marco del parcial G de la captura (A, B y C con el retorno de tc a A por la izquierda) rodea |
| S-EDI314 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI314_el_marco_del_recinto_rodea_el_retorno_de_su_etapa_inicial_y_sus_acciones` | el marco del recinto R de la captura (con el retorno de t1 a I por la izquierda y las acciones de J |
| S-EDI315 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI315_el_marco_no_cambia_al_simular_ni_por_el_tiempo_de_un_temporizador` | el marco solo depende de lo estructural: el tiempo transcurrido de un temporizador y el estado de |
| S-EDI316 | REQ-EDT-02, REQ-EDT-08, REQ-JER-07 | pasa | `test_SEDI316_mover_y_encuadrar_usan_el_marco_nuevo` | lo que se suelta en el carril del retorno, que ahora queda dentro del marco, es del |
| S-EDI317 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI317_un_parcial_con_acciones_en_todas_las_colocaciones_barras_y_simultaneidades_lo_lleva_dentro` | con acciones en cada colocación (matriz, columna, fila separada), una condición, un evento, una |
| S-EDI318 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI318_las_dos_esquinas_son_las_del_lado_que_mira_a_la_encapsulante_y_salen_de_las_suyas_mas_cercanas` | con el recinto debajo, a la derecha, a la izquierda o encima de la encapsulante, los dos trazos |
| S-EDI319 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI319_el_dibujo_pone_los_dos_trazos_en_cada_lado_y_cambian_si_el_marco_cambia_de_lado` | dibujado, cada recinto lleva dos trazos grises discontinuos, bajo todo lo demás, a las esquinas |
| S-EDI32 | REQ-EDT-01, REQ-SIM-03 | pasa | `test_SEDI32_dibujo_manual_persistencia_y_simulacion` | los ajustes sobreviven a guardar, abrir, simular y guardar otra copia. |
| S-EDI320 | REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI320_las_dependencias_no_cambian_la_disposicion_y_el_trazo_de_la_macroetapa_sigue_igual` | mostrar las dependencias solo añade sus trazos (dos por recinto); la macroetapa sigue unida a su |
| S-EDI321 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI321_con_el_boton_central_arrastrar_desplaza_el_dibujo_agarrando_el_punto_al_simular` | al simular, con el botón central (la rueda) pulsado, arrastrar desplaza el dibujo como si se |
| S-EDI322 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SEDI322_con_el_boton_central_al_editar_no_selecciona_ni_edita_nada_y_el_izquierdo_sigue_igual` | al editar, el botón central desplaza el dibujo (zoom manual) sin que el editor se entere: no |
| S-EDI323 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI323_centrar_seleccion_encuadra_lo_seleccionado_y_sin_seleccion_no_hace_nada` | junto a «Centrar todo» hay «Centrar selección» (con su ayuda): al editar, encuadra con `encuadrar` |
| S-EDI324 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI324_centrar_todo_deja_arriba_el_alto_del_recuadro_del_zoom_de_mas_y_no_lo_tapa` | «Centrar todo» deja arriba, además del margen de siempre, el alto del recuadro de los controles del |
| S-EDI325 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI325_dibujo_js_dibuja_los_mismos_marcos_y_trazos_de_dependencia_que_qt` | con las mismas medidas de texto (8 px por carácter en los dos), `drawDiagram` de |
| S-EDI326 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI326_el_texto_propio_de_la_aplicacion_no_se_sustituye_aunque_el_id_de_una_variable_sea_una_palabra_corriente` | con una variable de ID «a» y nombre «marcha» (los ID de un fichero externo admiten letras sueltas), |
| S-EDI327 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SEDI327_el_cuadro_de_no_compila_con_las_lecturas_activas_dice_los_nombres_y_no_enseña_ids` | el cuadro «El grafcet no compila con las lecturas de interpretación activas…» (7.7 = B con una |
| S-EDI328 | REQ-EDT-05, REQ-JER-02, REQ-JER-03 | pasa | `test_SEDI328_una_orden_suelta_no_ofrece_destinos_que_formarian_un_ciclo_con_la_etapa_de_cualquier_otro_parcial` | el diálogo de una orden suelta (aún sin etapa) no ofrece el parcial que formaría un ciclo |
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
| S-EDI48 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI48_panel_de_acciones_vista_previa_y_avisos` | el panel de la acción no lleva programador de condición dentro (la condición y el evento se |
| S-EDI49 | REQ-EDT-07 | pasa | `test_SEDI49_memorias_en_la_interfaz` | las variables internas se llaman «memorias» en la interfaz; el papel guardado sigue siendo |
| S-EDI50 | REQ-EDT-02 | pasa | `test_SEDI50_soltar_envolver_sustituir_y_quitar` | un bloque suelto en un hueco lo encaja; uno que envuelve sobre un hueco ocupado deja el bloque que |
| S-EDI51 | REQ-EDT-02 | pasa | `test_SEDI51_desplegables_y_campos` | el desplegable de una variable ofrece las booleanas de su papel, el de una etapa todas las etapas y |
| S-EDI52 | REQ-EDT-02 | pasa | `test_SEDI52_texto_y_bloques_sincronizados` | lo escrito en el campo de texto aparece en bloques; un texto que no se puede analizar no cambia los |
| S-EDI53 | REQ-EDT-02 | pasa | `test_SEDI53_deshacer_cambios_de_bloques` | en el panel de la transición cada cambio de bloques es una operación del editor y se deshace con su |
| S-EDI54 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI54_paleta_por_categorias` | la paleta tiene ocho categorías con su color (las constantes 1 y 0, en la suya); las memorias |
| S-EDI55 | REQ-EDT-02 | pasa | `test_SEDI55_ventana_ampliada_sincronizada` | «⤢ Ampliar» abre el programador en una ventana propia, no modal, con el mismo texto; los cambios de |
| S-EDI56 | REQ-EDT-02 | pasa | `test_SEDI56_cabe_a_200_px_y_crece_en_alto` | el área y la paleta caben a 200 px sin barra horizontal; el área crece en alto al estrecharse y |
| S-EDI57 | REQ-EDT-02 | pasa | `test_SEDI57_raton_clic_en_piezas_y_arrastres_recibidos` | un clic en un desplegable abre su menú y en un campo, su editor (Intro aplica, Esc descarta); |
| S-EDI58 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI58_receptividad_1_y_accion_entera` | una receptividad «1» se guarda como true y se valida sin D-TIPO; el valor de una acción |
| S-EDI59 | REQ-EDT-02 | pasa | `test_SEDI59_panel_de_opciones_abajo_sin_pestanas` | el panel inferior, al editar, es un único panel «Opciones» (sin pestañas) con la receptividad de la |
| S-EDI60 | REQ-EDT-02 | pasa | `test_SEDI60_bloques_y_texto_sincronizados_en_el_panel` | un cambio de bloques escribe el texto de la fórmula del panel de opciones y es una operación del |
| S-EDI61 | REQ-EDT-02 | pasa | `test_SEDI61_panel_plegado_se_despliega_con_el_doble_clic` | con el panel inferior plegado no se despliega solo al seleccionar; el doble clic en una transición, |
| S-EDI62 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI62_ficha_accion_en_la_paleta` | la paleta ofrece la ficha «Acción» (continua) con su figura (el lado izquierdo, bajo |
| S-EDI63 | REQ-EDT-02 | pasa | `test_SEDI63_y_y_o_con_colores_distintos` | «y» y «o» siguen en Operadores pero se dibujan con colores distintos entre sí y del resto de |
| S-EDI64 | REQ-EDT-02 | pasa | `test_SEDI64_disposicion_en_columnas` | categorías como carpetas en una columna (las ocho, con su color), a su derecha la columna de |
| S-EDI65 | REQ-EDT-02 | pasa | `test_SEDI65_arrastre_de_las_paletas` | la paleta «Elementos» se arrastra (el arrastre se activa después de fijar el modo de iconos y el |
| S-EDI66 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI66_variables_nuevas_al_dia_en_el_programador` | al crear, renombrar, quitar o cambiar de papel una variable (panel Variables, panel de |
| S-EDI67 | REQ-EDT-02 | pasa | `test_SEDI67_carpetas_en_su_orden_y_temporizadores` | las carpetas del programador van en este orden: Operadores, Constantes, Entradas, Salidas, Etapas (X), |
| S-EDI68 | REQ-EDT-02 | pasa | `test_SEDI68_receptividad_en_el_panel_con_texto_de_solo_lectura` | toda la receptividad está a la derecha del panel de opciones (texto de la fórmula, «Escrito», «Se |
| S-EDI69 | REQ-EDT-02 | pasa | `test_SEDI69_lazo_de_seleccion` | arrastrar desde un hueco dibuja un rectángulo y selecciona lo que queda dentro (etapas, |
| S-EDI70 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI70_soltar_la_ficha_accion_crea_una_accion_suelta` | la ficha «Continua», soltada en cualquier sitio, crea una acción continua suelta sin |
| S-EDI71 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI71_enlazar_una_accion_a_una_etapa_separarla_y_deshacer` | arrastrar del punto de unión de una acción suelta a una etapa la une: con variable pasa a |
| S-EDI72 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI72_tipo_de_accion_por_el_boton_derecho` | el botón derecho en una acción (suelta o unida) ofrece un submenú «Tipo de acción» con |
| S-EDI73 | REQ-DAT-01, REQ-EDT-09, REQ-EDT-14 | pasa | `test_SEDI73_guardar_abrir_con_borradores_avisos_y_deshacer` | los borradores de acción se guardan en la presentación |
| S-EDI74 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI74_opciones_de_una_accion_suelta_o_sin_completar` | «Editar…» de una acción suelta abre sus opciones en el panel inferior (con el límite de |
| S-EDI75 | REQ-ACT-01, REQ-TMP-02 | pasa | `test_SEDI75_accion_limitada_se_dibuja_como_condicion_not_d_sobre_x` | una acción limitada en el tiempo se dibuja como en la norma, con su límite como una |
| S-EDI76 | REQ-EDT-09 | pasa | `test_SEDI76_mensajes_informativos_y_barra_de_estado` | un aviso informativo de la edición no sale en rojo (el rojo es de los errores); el mensaje temporal |
| S-EDI77 | REQ-DAT-01, REQ-EDT-09 | pasa | `test_SEDI77_borradores_danados_al_abrir` | un `draftActions` corrupto no rompe la apertura: se descartan los dañados (no son |
| S-EDI78 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SEDI78_anchos_de_los_paneles_laterales` | al editar, los paneles laterales tienen un ancho único y fijo (el que piden las dos |
| S-EDI79 | REQ-EDT-07 | pasa | `test_SEDI79_tabla_de_variables_nombre_papel_tipo` | la tabla tiene solo Nombre, Papel y Tipo; se ofrecen Booleana, Entera y Decimal con 2 decimales; |
| S-EDI80 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI80_variable_nueva_sin_nombre` | «Nueva variable» añade una fila en blanco que solo existe en la interfaz; al escribir un |
| S-EDI81 | REQ-EDT-09 | pasa | `test_SEDI81_parpadeo_naranja_en_los_errores` | un rechazo, un intento de simular con errores, un clic en Diagnósticos (también en el aviso de un |
| S-EDI82 | REQ-ACT-01, REQ-DAT-01, REQ-EDT-02 | pasa | `test_SEDI82_colocacion_de_las_acciones_de_una_etapa` | por defecto, cajas pegadas en fila; el botón derecho en la etapa ofrece |
| S-EDI83 | REQ-ACT-01 | pasa | `test_SEDI83_condicion_y_banderita_encima_sin_solaparse` | en las tres colocaciones, la condición (trazo vertical a la izquierda de la caja y su texto), la |
| S-EDI84 | REQ-ACT-01 | pasa | `test_SEDI84_banco_dibuja_las_colocaciones_como_el_editor` | tools/dibujo.js (banco y comparador) lee `actionLayout` de la vista y dibuja las cuatro colocaciones |
| S-EDI85 | REQ-EDT-07 | pasa | `test_SEDI85_papel_y_tipo_como_texto_con_desplegable_al_editar` | Papel y Tipo se ven como texto; al editar la celda aparece un desplegable con las opciones y al elegir se |
| S-EDI86 | REQ-ACT-01 | pasa | `test_SEDI86_limitada_dibuja_x_de_la_etiqueta_no_del_id` | la condición de una acción limitada (`NOT 3s/X…`) usa la etiqueta de la etapa (X0), no su ID interno, |
| S-EDI87 | REQ-EDT-02 | pasa | `test_SEDI87_los_elementos_solo_se_colocan_arrastrando` | no hay modo herramienta para colocar: un clic en una ficha solo muestra su ayuda, un clic en el |
| S-EDI88 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI88_paleta_con_una_sola_ficha_de_accion` | la paleta es una sola lista, sin carpetas, con etapa, transición, simultaneidad, una |
| S-EDI89 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI89_punto_derecho_de_la_etapa_y_union_con_acciones_sueltas` | la etapa tiene un punto de unión en el centro de su lado derecho (visible al pasar el |
| S-EDI90 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI90_pegar_una_accion_al_lado_de_otra_con_iman` | soltar (o mover) una acción suelta de modo que toque el lado derecho de otra acción de la |
| S-EDI91 | REQ-ACT-01, REQ-DAT-01 | pasa | `test_SEDI91_grupos_sueltos_se_mueven_y_se_unen_juntos` | varias acciones sueltas pegadas forman un grupo suelto (`grupo` y `orden` en la |
| S-EDI92 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI92_el_enlace_de_las_acciones_se_selecciona_y_se_elimina` | el trazo que une la etapa con sus acciones se selecciona con un clic (se resalta); Supr |
| S-EDI93 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI93_condicion_y_evento_de_una_accion_en_el_panel_de_opciones` | al seleccionar una acción condicionada (o por evento, o una continua limitada de un |
| S-EDI94 | REQ-ACT-01, REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI94_evento_acciones_sueltas_limitada_y_crear_las_que_faltan` | el panel de opciones programa también el evento de una acción, la condición de |
| S-EDI95 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI95_el_panel_conserva_condicion_evento_y_limite` | el panel de la acción no lleva programador de condición dentro y conserva la condición y el |
| S-EDI96 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI96_nombres_de_variable_reservados` | en la interfaz se rechaza, con mensaje y parpadeo, un nombre de variable que no se puede |
| S-EDI97 | REQ-EDT-02 | pasa | `test_SEDI97_y_y_o_de_varias_entradas` | los bloques «y» y «o» llevan un «+» al final que añade otro hueco (sin «×»: un hueco vacío |
| S-EDI98 | REQ-ACT-01, REQ-DAT-01 | pasa | `test_SEDI98_acciones_sueltas_en_grupo_en_el_nucleo` | el editor guarda en `presentation.draftActions` los grupos de acciones sueltas (`grupo`, |
| S-EDI99 | REQ-EDT-02 | pasa | `test_SEDI99_y_y_o_con_muchos_operandos` | un «y» o un «o» de 10, 11 o 26 operandos (las claves de los huecos no chocan con la clase del nodo): |
| S-EJ01 | REQ-ACT-05, REQ-EVT-03, REQ-SEM-06 | pasa | `test_SEJ01_contador_en_etapa_inestable` | ejemplo del responsable; la etapa inestable 2 suma en CT y vuelve a 1 mientras CT < 3. |
| S-EJ02 | REQ-ACT-02, REQ-EVT-01, REQ-EVT-03 | pasa | `test_SEJ02_contador_por_flanco_en_una_etapa` | ejemplo del responsable; una cuenta por cada subida de I02 con 1 activa, ninguna en 0. |
| S-ESC01 | REQ-ACT-03, REQ-EDT-09 | pasa | `test_SESC01_conflictos_seguros_no_compilan` | activación/activación, desactivación/desactivación, activación/desactivación y misma etapa. |
| S-ESC02 | REQ-ACT-03, REQ-ACT-05 | pasa | `test_SESC02_no_son_conflictos_seguros` | la misma constante, etapas en secuencia y eventos distintos no impiden compilar. |
| S-EXP | REQ-EXP-01 | pasa | `test_SEXP_comparacion_encadenada_y_tipos` | comparaciones encadenadas rechazadas; sin conversión booleano↔número. |
| S-FIO01 | REQ-SIM-02 | pasa | `test_SFIO01_digitales_fragmentacion` | E/S externas por transporte separado del motor. |
| S-FIO02 | REQ-ROB-01 | pasa | `test_SFIO02_errores_y_reconexion` | rechaza respuestas defectuosas sin reutilizar el flujo. |
| S-FIO03 | REQ-ROB-01 | pasa | `test_SFIO03_limites_y_confirmacion` | direcciones, booleanos y confirmación de escritura. |
| S-FIO04 | REQ-DAT-02 | pasa | `test_SFIO04_persistencia_separada` | configuración externa no cambia el documento ni se borra al guardar. |
| S-FIO05 | REQ-ROB-01 | pasa | `test_SFIO05_mapa_invalido` | no admite asociaciones incompatibles o repetidas. |
| S-FIO06 | REQ-SIM-02 | pasa | `test_SFIO06_lote_y_salidas` | lote único y salidas efectivas continuas y memorizadas. |
| S-FIO07 | REQ-ROB-01 | pasa | `test_SFIO07_muestra_atomica` | una muestra incompleta o inválida no entra en el motor. |
| S-FIO08 | REQ-SIM-03 | pasa | `test_SFIO08_panel_y_mapa` | E/S externas configurables con tipo y valor visibles. |
| S-FIO09 | REQ-SIM-02 | pasa | `test_SFIO09_ciclo_pausa_diagnostico` | ciclo completo, pausa conserva y diagnóstico solicita cero. |
| S-FIO10 | REQ-ROB-01 | pasa | `test_SFIO10_perdida_y_reconexion_manual` | pérdida de red detiene; reconectar no reanuda el motor. |
| S-FIO11 | REQ-SIM-02 | pasa | `test_SFIO11_registros_red` | registros Modbus big endian y escrituras confirmadas. |
| S-FIO12 | REQ-EXP-01 | pasa | `test_SFIO12_escalado_y_limites` | INT16/UINT16 y escala exacta, sin redondeos implícitos. |
| S-FIO13 | REQ-EXP-01 | pasa | `test_SFIO13_rechaza_perdida_precision` | una entrada no representable no entra en el motor. |
| S-FIO14 | REQ-ROB-01 | pasa | `test_SFIO14_mbap_y_timeout` | cabecera incoherente y servidor silencioso no bloquean el cliente. |
| S-FIO15 | REQ-TMP-02 | pasa | `test_SFIO15_temporizacion_sin_cambios_sensor` | el reloj existente dispara salidas aunque la muestra no cambie. |
| S-FIO16 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO16_ventana_ciclo_y_reinicio` | controles Qt; Pausa deja todo a 0 (sin sesión en marcha y con la salida a cero en la |
| S-FIO17 | REQ-SIM-03 | pasa | `test_SFIO17_etiquetas_y_direcciones_independientes` | etiquetas explicadas conservan claves de conexión y separan áreas. |
| S-FIO18 | REQ-SIM-02 | pasa | `test_SFIO18_proyecto_listo_y_avisos` | proyecto manual preparado y mensajes accionables sin red. |
| S-FIO19 | REQ-SIM-03 | pasa | `test_SFIO19_arrastrar_mover_y_reemplazar` | eventos de arrastre, movimiento, sustitución, tipos y bloqueo. |
| S-FIO20 | REQ-SIM-03 | pasa | `test_SFIO20_pantalla_simple_y_check_confirmado` | ajustes fuera de pantalla principal y check de conexión real. |
| S-FIO21 | REQ-SIM-04 | pasa | `test_SFIO21_reinicio_descarta_lectura_pendiente_sin_cerrar_tcp` | reinicio de ejecución independiente del transporte externo. |
| S-FIO22 | REQ-SIM-03 | pasa | `test_SFIO22_observar_solo_entradas_desde_editor` | conexión de observación sin programa compilado: las entradas solo se leen; Conectar (en Pausa) |
| S-FIO23 | REQ-DAT-02 | pasa | `test_SFIO23_limites_de_canales_configurados` | rangos explícitos, asignaciones fuera y compatibilidad sin rangos. |
| S-FIO24 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SFIO24_canales_offset_mover_desasignar_y_persistir` | canales explícitos y movimiento desde el slot. |
| S-FIO25 | REQ-SIM-03 | pasa | `test_SFIO25_arrastre_desde_tarjeta_asignada` | el gesto comienza sobre la tarjeta, no solo sobre la lista. |
| S-FIO26 | REQ-DAT-02 | pasa | `test_SFIO26_escala_factoryio_100_y_migracion` | entradas/salidas numéricas usan 100 incluso en mapas anteriores. |
| S-FIO27 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO27_la_conexion_sobrevive_a_play_pausa_edicion_reinicio_y_abrir` | una vez conectado, ni Play, Pausa, editar, Reiniciar ni abrir otro ejemplo cierran |
| S-FIO28 | REQ-SIM-03 | pasa | `test_SFIO28_mapa_invalido_tras_editar_avisa_y_no_arranca` | si lo editado deja el mapa sin su variable, Play no arranca el control externo, avisa en el panel |
| S-FIO29 | REQ-SEM-07, REQ-SIM-02 | pasa | `test_SFIO29_inestable_con_modbus_avisa_pausa_y_pone_salidas_a_cero` | un GRAFCET inestable con la planta conectada se detiene (Pausa/edición), avisa una sola |
| S-FIO30 | REQ-SIM-02, REQ-SIM-04 | pasa | `test_SFIO30_pausar_vincular_y_observar_sin_cerrar_tcp` | Pausa conserva TCP, sigue leyendo las entradas y pone a cero todas las salidas asignadas; |
| S-FIO30 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO30_play_inmediato_tras_reiniciar_en_pausa_no_vuelve_a_pausa` | Pausa, Reiniciar en Pausa (que solo vuelve a pedir el cero) y Play inmediato, antes de que |
| S-FIO31 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO31_abrir_otro_proyecto_pone_a_cero_aunque_la_escritura_siguiera_en_vuelo` | Play y Pausa con una escritura de salidas en vuelo descartan su respuesta |
| S-FIO32 | REQ-SIM-03 | pasa | `test_SFIO32_cerrar_la_ventana_cierra_el_tcp` | cerrar la ventana con la conexión viva cierra el TCP (no queda el socket abierto contra la planta). |
| S-FIO33 | REQ-SIM-03 | pasa | `test_SFIO33_marco_con_canales_y_nombres_fuera` | la vista autómata tiene la cabecera «(IP:puerto) Esclavo ID:n», Input e Input Reg a la izquierda, |
| S-FIO34 | REQ-SIM-03 | pasa | `test_SFIO34_color_de_tipo_y_viveza_del_indicador` | la barrita de cada canal es tenue si no está asignado, del color del tipo (Bool verde, Decimal azul, |
| S-FIO35 | REQ-SIM-03 | pasa | `test_SFIO35_arrastre_resalta_la_fila_entera_y_la_x_aparece_al_pasar_el_raton` | al arrastrar una variable sobre un canal se resalta la fila entera (nombre incluido); soltar asigna; |
| S-FIO36 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO36_errores_de_red_habituales_con_frase_legible` | los fallos de socket habituales (WinError 10053, 10054, 10061, reinicio, tubería rota, |
| S-FIO37 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO37_variables_nuevas_del_editor_aparecen_en_es_y_se_pueden_asignar` | cada vez que se muestra E/S externas, sus listas y canales reflejan las variables actuales |
| S-FIO38 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO38_cambiar_tipo_o_papel_de_una_asignada_la_quita_con_aviso_sin_romper_el_panel` | si una variable asignada cambia de tipo o de papel y ya no casa con su área, se quita del |
| S-FIO39 | REQ-SIM-03 | pasa | `test_SFIO39_con_el_panel_a_la_vista_las_variables_nuevas_llegan_sin_salir_y_se_conserva_lo_escrito` | con la vista de E/S abierta (la tabla de variables sigue accesible) una variable nueva aparece al |
| S-FIO40 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO40_con_la_conexion_activa_el_panel_no_cambia_y_avisa_hasta_desconectar` | con Modbus activo el mapa en uso no cambia a mitad de sesión: las variables nuevas no se |
| S-FIO41 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SFIO41_canales_fijados_a_mano_se_conservan_y_se_avisa_si_un_area_se_queda_sin_canales` | con las cantidades de canal escritas a mano no se inventan canales; si una variable |
| S-FIO42 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO42_camino_de_simulacion_el_panel_sigue_a_las_variables_del_modelo_en_ejecucion` | en Play, E/S externas enseña las variables del modelo que se ejecuta; al volver a Pausa y |
| S-FIO43 | REQ-SIM-03 | pasa | `test_SFIO43_la_primera_vez_el_servidor_propuesto_es_el_de_factory_io` | sin nada recordado ni mapa guardado, el panel propone 192.168.1.133, puerto 502 y esclavo 1; no se |
| S-FIO44 | REQ-SIM-03 | pasa | `test_SFIO44_recuerda_el_ultimo_servidor_que_conecto_y_lo_propone_en_proyectos_nuevos_y_al_reiniciar` | tras conectar con éxito, host, puerto y esclavo se recuerdan en los ajustes de la aplicación y se |
| S-FIO45 | REQ-SIM-03 | pasa | `test_SFIO45_la_prueba_de_conexion_con_exito_tambien_recuerda_y_un_fallo_no` | «Probar conexión» con éxito recuerda el servidor; una conexión que falla no lo cambia. |
| S-FIO46 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SFIO46_el_mapa_guardado_del_proyecto_manda_sobre_el_servidor_recordado` | un proyecto con su configuración Modbus guardada abre con la suya, aunque haya un servidor |
| S-FIO47 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO47_pausa_pone_a_cero_coils_y_holding_y_play_arranca_de_la_situacion_inicial` | Pausa deja todo a 0 hasta un nuevo Play: todas las coils y holding asignadas se |
| S-FIO48 | REQ-SIM-03 | pasa | `test_SFIO48_pausa_sin_conexion_deja_el_grafcet_sin_estado_y_cada_play_empieza_de_cero` | sin E/S externas, Pausa también deja el GRAFCET sin etapas activas, sin temporizadores y con |
| S-FIO49 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO49_conectar_o_probar_con_play_activo_pasa_a_pausa_y_un_diagnostico_acaba_con_todo_a_cero` | «Probar conexión» y «Conectar» con Play activo pasan a Pausa (sin etapas activas); |
| S-FIO50 | REQ-ROB-01, REQ-SIM-02 | pasa | `test_SFIO50_con_la_red_caida_en_play_acaba_en_pausa_sin_estado_y_no_se_garantiza_el_cero` | si la red cae en Play, el programa acaba en Pausa sin etapas activas y el estado de la conexión |
| S-FIO51 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO51_conectar_sin_sesion_pone_a_cero_las_asignadas_una_vez_antes_de_leer_y_probar_no_escribe` | Conectar sin sesión (Pausa) escribe exactamente un cero a cada coil y holding |
| S-FIO52 | REQ-ROB-01, REQ-SIM-02 | pasa | `test_SFIO52_desconectar_escribe_el_cero_antes_de_cerrar_el_tcp_y_si_la_red_falla_cierra_igual_con_aviso` | Desconectar con la conexión establecida escribe el cero de todas las salidas asignadas (coils |
| S-FIO53 | REQ-ROB-01, REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO53_desconectar_en_play_pone_a_cero_coils_y_holding_antes_de_cerrar_el_tcp` | «Desconectar» en Play escribe el cero de todas las coils y holding asignadas ANTES |
| S-FIO54 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO54_desconectar_con_la_red_caida_cierra_igual_y_avisa_de_salidas_no_garantizadas` | si la planta ha dejado de responder, «Desconectar» no puede escribir el cero: la conexión se |
| S-FIO55 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO55_cerrar_la_ventana_con_la_conexion_viva_escribe_el_cero_antes_de_cerrar_el_tcp` | cerrar la ventana en Play escribe el cero de las coils y holding asignadas antes de cerrar el |
| S-FIO56 | REQ-DAT-02, REQ-ROB-01 | pasa | `test_SFIO56_cargar_descarta_solo_las_asignaciones_que_ya_no_casan_y_rechaza_lo_corrupto` | un mapa guardado con una variable que ya no existe (o de tipo o papel que ya no casan con el |
| S-FIO57 | REQ-DAT-02, REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO57_un_mapa_guardado_con_variables_que_ya_no_existen_se_carga_sin_ellas_y_con_aviso` | al abrir un proyecto cuyo mapa guardado tiene asignaciones de una variable |
| S-FIO58 | REQ-SIM-04 | pasa | `test_SFIO58_vincular_ya_no_tiene_el_parametro_observar_despues` | limpieza: Reiniciar en Pausa ya no tiene una variante «observar después» (Pausa = sin sesión y todo a 0 lo |
| S-FIO59 | REQ-SIM-02, REQ-SIM-04 | pasa | `test_SFIO59_vincular_no_escribe_nada_hasta_leer_y_aplicar_las_entradas` | Play (vincular) y Reiniciar en Play leen las entradas de la planta ANTES de |
| S-FIO60 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO60_play_lee_las_entradas_antes_de_escribir_y_la_primera_escritura_ya_las_lleva` | con la planta ya con el sensor a 1, Play no escribe antes de leer: la primera |
| S-FIO61 | REQ-ROB-01, REQ-SIM-02 | pasa | `test_SFIO61_pausar_tras_detenerse_el_motor_no_repite_el_cero` | cuando el motor se detiene por un diagnóstico, `tick` ya pide el cero a la planta; |
| S-FIO62 | REQ-ROB-01, REQ-SEM-07 | pasa | `test_SFIO62_un_modelo_inestable_en_play_deja_un_solo_cero_en_la_planta` | cuando el motor se detiene por inestabilidad (D-LIM-EVOL) con la planta |
| S-FIO63 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO63_abrir_otro_proyecto_con_la_conexion_viva_pone_a_cero_tambien_las_salidas_del_mapa_nuevo` | al abrir otro proyecto con la conexión viva se pone a cero lo del mapa anterior y |
| S-FIO64 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO64_observar_pone_a_cero_las_salidas_del_mapa_nuevo_una_vez_por_canal` | cambiar de modelo con la conexión viva (`observar`) pide también el cero de las |
| S-FIO65 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO65_desconectar_con_la_red_caida_dice_que_se_ha_desconectado_sin_invitar_a_reconectar` | si la red falla al desconectar, el aviso dice que se ha desconectado y que las |
| S-FIO66 | REQ-SIM-03 | pasa | `test_SFIO66_abrir_un_modelo_deja_pausa_sin_estado_tambien_en_el_panel_de_es_y_play_lo_arranca` | abrir un ejemplo o un proyecto deja el programa en Pausa y sin estado, como tras |
| S-FIO67 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO67_una_asignada_que_pasa_a_interna_se_quita_con_el_aviso_de_quitar_obsoletas` | si una variable asignada pasa a «interna», el panel avisa de que «ya no es de |
| S-FIO68 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO68_desconectar_mientras_se_conecta_y_la_conexion_falla_no_habla_de_poner_a_cero_la_planta` | si se pulsa Desconectar mientras se conecta (o se prueba) y la conexión se rechaza o |
| S-FIO69 | REQ-ROB-01, REQ-SIM-02, REQ-SIM-04 | pasa | `test_SFIO69_play_con_el_cero_de_pausa_ya_enviado_no_lo_repite_y_en_el_cable_va_cero_lectura_escritura` | Pausa pide el cero; si llega Play (`vincular`) con ese cero enviado y sin |
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
