# 05. Trazabilidad requisito ↔ implementación ↔ prueba

Documento **generado** por `tools/generar_trazabilidad.py`; no editar a mano.

Generado el 2026-11-05T14:42:29+01:00 · Python 3.12.10 · Windows-11-10.0.26200-SP0 · 938 pruebas ejecutadas, 0 fallos, 0 errores.

Leyenda: ✔ pasa · ◆ pasa según una decisión del responsable sobre una U (no es el oráculo del documento 11, que pedía detener; contraste U-01 pendiente) · ⛔ bloqueo por U verificado (el oráculo semántico sigue abierto) · ◐ parcial · ∅ capacidad no implementada en esta iteración (se verifica que no se ejecuta) · — no ejecutado · ✘ falla. **Un ✔ con oráculo I es provisional (U-01): no prueba conformidad.**

## Resumen

| Categoría del requisito | Nº |
|---|---|
| Implementado (P), verificable ya (`IMPL-P`) | 47 |
| Implementado como provisional (I; U-01) (`IMPL-I`) | 15 |
| Parcial (`PARCIAL`) | 9 |
| Implementado según decisión del responsable (U cerrada; contraste U-01 pendiente) (`IMPL-DEC`) | 5 |
| Bloqueado por U (bloqueo implementado) (`BLOQ-U`) | 0 |
| Pendiente de iteración (estructura hecha) (`PEND-ITER`) | 0 |
| Pendiente de interfaz (`PEND-UI`) | 0 |
| Pendiente de plataforma (U-10) (`PEND-PLT`) | 1 |
| Revisión documental (`DOC`) | 5 |

| Estado de los 102 casos del documento 11 | Nº |
|---|---|
| BLOQUEO VERIFICADO | 1 |
| NO EJECUTADO | 6 |
| PARCIAL | 7 |
| PASA | 76 |
| PASA SEGÚN DECISIÓN | 12 |

Pruebas suplementarias S-xx: 836 casos, 841 pruebas, 841 pasan.

## Requisitos

| Requisito | Clase/prio. | Doc. | Categoría | Implementación | Casos | Nota |
|---|---|---|---|---|---|---|
| REQ-ALC-01 | P/alta | 01 | PARCIAL | editor, persistence, engine | T-21a ◐, T-24d ◐ | Ciclo principal sin servicios de terceros verificado sin interfaz (T-24d); falta la interfaz |
| REQ-ALC-02 | P/crítica | 01 | DOC | tools/comprobar_paquete.py | R-02 (documental), S-PKG ✔ | Parte automatizable de R-02: el paquete conserva exactamente los doce Markdown con sus huellas |
| REQ-ALC-03 | P/alta | 01 | IMPL-P | profile, declaration | R-01 (documental), S-DECL ✔ | Cada capacidad marcada provisional / no soportada con su motivo |
| REQ-NOR-01 | P/crítica | 01 | IMPL-P | profile, persistence, declaration | T-22e ✔, S-DECL ✔ | Base normativa declarada en el manifiesto; ejes de versión separados; no se sustituye silenciosamente |
| REQ-NOR-02 | P/crítica | 01 | IMPL-P | declaration | R-01 (documental), S-AJU05 ✔, S-AJU10 ✔, S-AJU11 ✔, S-CMP01 ✔, S-CMP04 ✔, S-CMP05 ✔, S-PRP07 ✔, S-OPT03a ✔, S-DECL ✔ | La declaración excluye toda materia con U crítica y nunca afirma conformidad; R-01 sigue siendo documental |
| REQ-CR-01 | P/crítica | 02 | DOC | tools/paquete.py | R-01 (documental) | Las fuentes y localizadores se conservan en el paquete; la matriz enlaza cada requisito con su documento |
| REQ-CR-02 | P/crítica | 02 | DOC | — | R-02 (documental), S-PKG ✔ | Esta implementación se ha hecho solo con el paquete; ver declaración de procedencia en README |
| REQ-CR-03 | P/crítica | 02 | DOC | — | R-02 (documental) | No se ha detectado contaminación; procedimiento descrito en README |
| REQ-CR-04 | P/alta | 02 | DOC | tests | R-01 (documental) | Ningún oráculo procede de otro producto; los oráculos son los del documento 11 |
| REQ-MOD-01 | P/crítica | 03 | IMPL-P | model, persistence | T-21b ✔, T-22b ✔, S-CLI03 ✔ | IDs únicos, propietario y referencias existentes; duplicados/huérfanos impiden simular |
| REQ-MOD-02 | I/crítica | 03 | IMPL-I | model, editor | T-21b ✔, S-SAL07 ✔ | D-ALTERNANCIA; enlaces etapa→etapa como borrador (P-IMP-05) |
| REQ-MOD-03 | P/crítica | 03 | IMPL-P | editor | T-21c ✔, S-AFI04 ✔, S-EDI258 ✔, S-EDI259 ✔, S-EDI228 ✔, S-EDI229 ✔, S-EDI230 ✔, S-EDI231 ✔, S-EDI232 ✔, S-EDI233 ✔, S-EDI225 ✔, S-EDI07 ✔, S-EDI17 ✔, S-EDI194 ✔, S-EDI19 ✔, S-EDI20 ✔, S-EDI21 ✔, S-EDI23 ✔, S-EDI24 ✔, S-EDI26 ✔, S-EDI193 ✔, S-PAL03 ✔, S-CLQ10 ✔, S-CLI02 ✔, S-CLI13 ✔, S-VIS02 ✔, S-VIS14 ✔, S-COR09 ✔, S-SAL06 ✔, S-SAL08 ✔, S-SAL01 ✔, S-SAL02 ✔, S-SAL04 ✔, S-SAL05 ✔ | Solo se conecta por operación explícita; la geometría no crea relaciones |
| REQ-MOD-04 | I/alta | 03 | IMPL-DEC | model, engine | T-03c ✔, T-10e ◆, T-01d ◆, S-U07 ✔, S-OPT03e ✔ | Sumideros I. U-07 cerrada por el responsable (comparador, 27-10-2026, P-IMP-22): fuente por evento una vez por flanco (6.3 A); sin etapas iniciales, fuente de nivel y transición sin lados no compilan (6.1 A, 6.2 A, 6.4 A) |
| REQ-MOD-05 | P/alta | 03 | IMPL-P | model, expressions, editor | T-09c ✔ | Texto libre conservado como descriptivo; D-EXP-PENDIENTE localizado |
| REQ-MOD-06 | P/crítica | 03 | IMPL-P | model, editor, engine | T-04c ✔, T-21d ✔, S-EDI151 ✔ | Renombrar, mover u ordenar no cambia observables ni revisión semántica (H-13) |
| REQ-MOD-07 | I/alta | 03 | IMPL-I | model, hierarchy | T-18c ✔, T-19c ✔, S-EDI229 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI173 ✔, S-EDI174 ✔, S-EDI179 ✔, S-EDI189 ✔, S-EDI139 ✔, S-EDI144 ✔, S-EDI145 ✔, S-EDI149 ✔, S-EDI154 ✔, S-EDI155 ✔, S-EDI158 ✔, S-EDI193 ✔, S-MTP01 ✔, S-MTP02 ✔, S-MTP03 ✔, S-H08 ✔ | Propiedad única de expansiones y recintos; recursión rechazada; la estructura se ejecuta (P-IMP-23) |
| REQ-SEM-01 | I/crítica | 04 | PARCIAL | engine | T-01a ✔, T-01b ✔, T-01c ✔, T-01d ◆, S-CMP02 ✔, S-U09 ✔, S-H07 ✔ | Situación inicial explícita y su cierre causal en τ=0: acciones al activar las iniciales, evolución inicial y temporizadores desde τ=0 (hoja 08, 1.1–1.4, P-IMP-19). Inicio vacío: no compila (6.1 A, P-IMP-22). Abierto: iniciales dentro de jerarquías (U-08) |
| REQ-SEM-02 | I/crítica | 04 | IMPL-I | engine | T-02c ✔, T-02a ✔, T-02b ✔, T-06a ✔, T-06b ✔, S-EDI230 ✔ | Validación y receptividad; imposición jerárquica pendiente de iteración |
| REQ-SEM-03 | I/crítica | 04 | IMPL-I | engine | T-03a ✔, T-03b ✔, T-03c ✔, T-03d ✔, T-06c ✔ | Cambio conjunto de precedentes y siguientes |
| REQ-SEM-04 | I/crítica | 04 | IMPL-I | engine | T-04a ✔, T-04b ✔, T-04c ✔, T-06a ✔, T-06b ✔, T-13d ✔ | Conjunto simultáneo completo; sin prioridad por orden |
| REQ-SEM-05 | I/crítica | 04 | IMPL-DEC | engine | T-05a ✔, T-05b ◆, S-H05 ✔ | Actividad I. Efectos decididos por el responsable (comparador, 27-10-2026, P-IMP-22): en permanencia o reactivación no se ejecutan acciones al activar ni al desactivar y la duración sigue (3.1 A, 3.2 A, 3.3 A; cierra H-05) |
| REQ-SEM-06 | I/crítica | 04 | IMPL-I | engine | T-07a ✔, T-07b ✔, T-07c ✔, S-EJ01 ✔, S-H09 ✔ | Etapas inestables sin pulso continuo; memorizadas conservadas; eventos en el recorrido según la lectura 5.1 (P-IMP-22) |
| REQ-SEM-07 | P/crítica | 04 | IMPL-P | engine | T-08a ✔, T-08b ✔, S-FIO29 ✔, S-FIO62 ✔, S-APP19 ✔, S-08a ✔, S-H09b ✔, S-OPT03c ✔ | D-LIM-EVOL recuperable, τ sin avanzar, sin falsa estabilidad (T-08a con su oráculo original desde la respuesta 1.2 A; S-08a) |
| REQ-SEM-08 | P/crítica | 04 | IMPL-P | engine, trace | T-04c ✔, T-23b ✔, T-24a ◐, S-U06 ✔ | Mismos observables con independencia de recorrido, geometría y control; entre sistemas: U-10 |
| REQ-SEM-09 | U/crítica | 04 | IMPL-DEC | engine | T-10d ◆, T-11b ⛔, T-15c ◆, S-AJU04 ✔, S-AJU05 ✔, S-CMP01 ✔, S-CMP02 ✔, S-CMP03 ✔, S-CMP05 ✔, S-APP08 ✔, S-U05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔ | U-05 (P-IMP-20) y U-03, U-04, U-06, U-07 (comparador, 27-10-2026, P-IMP-22) cerradas por el responsable; cada lectura sigue siendo seleccionable, «detener» incluida en el banco (P-IMP-15, P-IMP-21; el simulador de escritorio no la ofrece, P-IMP-30). Siguen deteniéndose los eventos internos y de franqueamiento (U-03), 0s/p/d2 y los vencimientos que dependen del orden (U-06) |
| REQ-ACT-01 | I/crítica | 05 | IMPL-I | engine | T-14a ✔, T-14b ✔, T-14c ✔, T-07a ✔, T-12c ✔, S-UIV01 ✔, S-FBR03 ✔, S-EDI317 ✔, S-EDI249 ✔, S-EDI224 ✔, S-EDI256 ✔, S-EDI304 ✔, S-EDI305 ✔, S-EDI240 ✔, S-EDI100 ✔, S-EDI102 ✔, S-EDI104 ✔, S-EDI105 ✔, S-EDI106 ✔, S-EDI114 ✔, S-EDI117 ✔, S-EDI123 ✔, S-EDI124 ✔, S-EDI126 ✔, S-EDI127 ✔, S-EDI128 ✔, S-EDI129 ✔, S-EDI130 ✔, S-EDI131 ✔, S-EDI132 ✔, S-EDI133 ✔, S-EDI134 ✔, S-EDI135 ✔, S-EDI136 ✔, S-EDI137 ✔, S-EDI189 ✔, S-EDI40 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI58 ✔, S-EDI62 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI75 ✔, S-EDI82 ✔, S-EDI83 ✔, S-EDI84 ✔, S-EDI86 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI91 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI39 ✔, S-EDI98 ✔, S-CLQ08 ✔, S-CLQ09 ✔, S-CLI06 ✔, S-CLI10 ✔, S-VIS03 ✔, S-COR05 ✔, S-H10 ✔ | Disyunción sobre situación efectiva; una salida continua leída en una expresión vale según la situación del momento (comparador, 8.2 C; cierra H-10) |
| REQ-ACT-02 | I/crítica | 05 | IMPL-I | engine | T-15a ✔, T-15b ✔, T-01c ✔, T-07b ✔, T-07c ✔, T-18e ◐, S-UIV03 ✔, S-CMP02 ✔, S-EJ02 ✔, S-SAL03 ✔, S-U03 ✔, S-U05b ✔, S-U09 ✔, S-H07 ✔, S-H08c ✔ | Memorizadas por activación, desactivación y evento, también virtuales |
| REQ-ACT-03 | P/crítica | 05 | IMPL-P | model, engine | T-16a ✔, T-16b ✔, S-ESC01 ✔, S-ESC02 ✔ | D-ESCRITURA-CONFLICTO con autores y valores, sin prioridad oculta; un conflicto seguro impide compilar (P-IMP-16) y el resto se detiene en ejecución |
| REQ-ACT-04 | I/crítica | 05 | IMPL-I | model | T-16c ✔ | D-MODO-SALIDA en validación |
| REQ-ACT-05 | U/crítica | 05 | IMPL-DEC | engine, model | T-15c ◆, T-16d ◆, S-EJ01 ✔, S-U05 ✔, S-U05b ✔, S-ESC02 ✔ | Hoja 08, 2.1 C, 2.2 B, 2.3 A, 2.4 A y 2.5 A (P-IMP-20): conflicto si dos escriben a la vez, dependencia cruzada no compila, lo asignado se ve en el mismo instante y vale la última asignación |
| REQ-EVT-01 | I/crítica | 05 | IMPL-I | engine | T-10a ✔, T-10b ✔, T-10c ✔, T-10e ◆, S-EJ02 ✔ | Flancos sobre entradas en la 1.ª evolución; sin retención ni consumo exclusivo |
| REQ-EVT-02 | P/crítica | 05 | IMPL-P | scenario | T-10b ✔, T-13a ✔ | Lotes simultáneos frente a lotes ordenados; D-LOTE |
| REQ-EVT-03 | U/crítica | 05 | PARCIAL | model, engine | T-10d ◆, T-11a ◆, T-11b ⛔, T-05b ◆, S-CMP02 ✔, S-EJ01 ✔, S-EJ02 ✔, S-U03 ✔, S-H05 ✔, S-OPT03a ✔, S-OPT03b ✔, S-OPT03c ✔, S-OPT03e ✔ | Evento en el recorrido: lectura «situación anterior» por defecto; acciones por evento solo si la etapa estaba activa y no sale con él (comparador, 27-10-2026, 5.1–5.3, P-IMP-22; H-23). Eventos internos y de franqueamiento: U-03, bloqueados |
| REQ-EXP-01 | P/alta | 05 | IMPL-P | expressions, values | T-09a ✔, T-09b ✔, T-09c ✔, S-FIO12 ✔, S-FIO13 ✔, S-FIO71 ✔, S-FIO72 ✔, S-FIO73 ✔, S-DEC ✔, S-EXP ✔ | Tipos exactos, unidades, precedencia; sintaxis de literales P-IMP-06 |
| REQ-EXP-02 | P/crítica | 05 | IMPL-P | expressions, engine | T-09d ✔ | Evaluación pura |
| REQ-TMP-01 | P/crítica | 05 | IMPL-P | timeutil, values | T-12d ✔, T-24b ✔, S-AFI03 ✔, S-VIS06 ✔, S-VIS07 ✔, S-VIS09 ✔, S-EDI207 ✔, S-EDI210 ✔, S-EDI204 ✔, S-EDI205 ✔, S-EDI206 ✔, S-EDI41 ✔, S-EDI46 ✔, S-IEJ06 ✔, S-DEC ✔, S-COL01 ✔, S-COL07 ✔ | µs exactos, rango 0..2^63-1, sin redondeo |
| REQ-TMP-02 | I/crítica | 05 | IMPL-I | engine, model | T-12a ✔, T-12b ✔, T-12c ✔, T-12e ✔, T-12f ✔, T-13d ✔, S-EDI75 ✔, S-RED05 ✔, S-RED14 ✔, S-FIO15 ✔, S-U09 ✔, S-12a ✔, S-H09 ✔, S-H09b ✔ | delay ordinario, limitadas, retardadas; duración de etapa inicial según T-12a/T-12c (H-02); salida y reentrada en el mismo instante sin interrumpir la duración (P-IMP-18); bases compuestas no soportadas (H-09) |
| REQ-TMP-03 | U/crítica | 05 | PARCIAL | engine, model | T-13b ◆, T-13c ◆, T-20a ◆, S-CMP02 ✔, S-U06 ✔ | Decidido (comparador, 27-10-2026, P-IMP-22): caída en el vencimiento → primero el vencimiento (4.1 A); rebote → sigue verdadera (4.2 A); lote y vencimiento independientes → juntos (4.3 A; cierra H-17); los tiempos de 0 s se quitan: 0s/p es p y 0s/p/7s es p/7s (chat, 4.4 revisada, P-IMP-28). Sigue en U-06: vencimientos simultáneos que dependen del orden |
| REQ-JER-01 | I/crítica | 06 | IMPL-I | engine, model | T-04c ✔, T-20b ✔, S-H08 ✔, S-H08c ✔ | Partición sin orden y XG derivada de sus etapas. Un parcial dentro de otro solo como recinto o expansión; sin encapsulante no compila (chat 27-10-2026, 8.1 C; cierra H-08) |
| REQ-JER-02 | I/crítica | 06 | IMPL-I | hierarchy, engine | T-17a ✔, T-17b ◐, S-FBR02 ✔, S-EDI253 ✔, S-EDI254 ✔, S-EDI255 ✔, S-EDI280 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI284 ✔, S-EDI285 ✔, S-EDI303 ✔, S-EDI305 ✔, S-EDI306 ✔, S-EDI307 ✔, S-EDI308 ✔, S-EDI309 ✔, S-EDI328 ✔, S-EDI242 ✔, S-EDI183 ✔, S-EDI184 ✔, S-EDI190 ✔, S-EDI191 ✔, S-EDI192 ✔, S-EDI196 ✔, S-EDI142 ✔, S-EDI143 ✔, S-EDI146 ✔, S-EDI147 ✔, S-EDI300 ✔, S-EDI301 ✔, S-EDI302 ✔, S-MTP10 ✔, S-MTP11 ✔, S-MTP12 ✔, S-MTP13 ✔, S-PAL04 ✔, S-CLI01 ✔, S-CLI06 ✔, S-VIS13 ✔ | Forzado explícito, actual (captura), vacío e inicial; el destino no evoluciona mientras está vigente; la retirada libera desde la situación resultante (documento 06, P-IMP-23). Momento, temporizadores, recintos y acciones: U-08 (7.2–7.4, 7.8) |
| REQ-JER-03 | P/crítica | 06 | IMPL-P | model, hierarchy | T-17c ✔, T-17d ✔, S-EDI254 ✔, S-EDI284 ✔, S-EDI306 ✔, S-EDI328 ✔, S-EDI183 ✔, S-EDI146 ✔, S-CLI11 ✔ | Ciclos D-JERARQUIA-CICLO; conflicto posible avisado al validar y detenido al ejecutar (D-FORZADO-CONFLICTO) sin prioridad por ID |
| REQ-JER-04 | I/crítica | 06 | IMPL-I | model, hierarchy, engine | T-18a ✔, T-18b ✔, T-18c ✔, T-18e ◐, S-LEY02 ✔, S-VIS08 ✔, S-EDI286 ✔, S-EDI287 ✔, S-EDI296 ✔, S-EDI320 ✔, S-EDI325 ✔, S-EDI313 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI227 ✔, S-EDI170 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI173 ✔, S-EDI178 ✔, S-EDI180 ✔, S-EDI181 ✔, S-EDI182 ✔, S-EDI187 ✔, S-EDI194 ✔, S-EDI139 ✔, S-EDI140 ✔, S-EDI145 ✔, S-EDI193 ✔, S-IEJ01 ✔, S-IEJ06 ✔, S-MTP20 ✔, S-MTP21 ✔, S-MTP22 ✔, S-MTP23 ✔, S-MTP01 ✔, S-MTP02 ✔, S-MTP03 ✔, S-MTP04 ✔, S-CLI01 ✔, S-APP20 ✔ | Relación expandida: llegar activa la entrada, salir exige la salida; XM por la expansión; reentrada sin borrar memorias (P-IMP-23). Ramas residuales: U-08 (7.5). Iniciales en la expansión: se admiten (7.7 A, P-IMP-24) |
| REQ-JER-05 | I/crítica | 06 | IMPL-I | model, hierarchy | T-19a ✔, T-19b ✔, T-19c ✔, S-AJU01 ✔, S-LEY02 ✔, S-EDI286 ✔, S-EDI287 ✔, S-EDI296 ✔, S-EDI318 ✔, S-EDI319 ✔, S-EDI320 ✔, S-EDI325 ✔, S-EDI314 ✔, S-EDI274 ✔, S-EDI275 ✔, S-EDI312 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI170 ✔, S-EDI174 ✔, S-EDI175 ✔, S-EDI176 ✔, S-EDI188 ✔, S-EDI196 ✔, S-EDI141 ✔, S-EDI144 ✔, S-EDI145 ✔, S-EDI150 ✔, S-EDI155 ✔, S-OTR02 ✔, S-OTR12 ✔, S-LAZ05 ✔, S-LAZ08 ✔, S-LAZ11 ✔, S-MTP20 ✔, S-MTP21 ✔, S-MTP22 ✔, S-MTP02 ✔, S-MTP03 ✔, S-MTP04 ✔, S-PAG38 ✔, S-PAG42 ✔, S-TEC08 ✔, S-CLI01 ✔, S-CLI09 ✔, S-CLI14 ✔, S-COL04 ✔ | Al arrancar, iniciales; al reentrar, enlaces de activación; al salir, se desactivan todos los descendientes (P-IMP-23). Encapsulante en permanencia: el contenido se mantiene (comparador, 3.4 A) |
| REQ-JER-06 | U/crítica | 06 | IMPL-DEC | hierarchy | T-18d ◆, T-20a ◆, T-20c ◆, S-EDI148 ✔ | Cerradas por el responsable: 7.2 B, 7.3 A, 7.4 C, 7.5 A, 7.6 B, 7.7 A y 7.8 A (P-IMP-24 a P-IMP-26). Vaciar por forzado un recinto con su encapsulante activa no se preguntó y se detiene (U-08) |
| REQ-JER-07 | P/alta | 06 | IMPL-P | editor, escritorio | T-21g —, T-24a ◐, S-DBR07 ✔, S-EDI316 ✔, S-EDI289 ✔, S-EDI291 ✔, S-EDI292 ✔, S-EDI293 ✔, S-EDI294 ✔, S-EDI177 ✔, S-EDI181 ✔, S-EDI185 ✔, S-EDI186 ✔, S-EDI152 ✔, S-EDI154 ✔, S-EDI157 ✔ | Plegar, desplegar y navegar entre jerarquías solo cambian la vista; el modelo y la ejecución se conservan (P-IMP-61, P-IMP-62) |
| REQ-EDT-01 | P/alta | 07 | PARCIAL | editor, persistence | T-21a ◐, S-DBR08 ✔, S-DBR09 ✔, S-DBR11 ✔, S-DBR12 ✔, S-FBR06 ✔, S-USO05 ✔, S-EDI283 ✔, S-EDI308 ✔, S-EDI03 ✔, S-EDI04 ✔, S-EDI05 ✔, S-EDI08 ✔, S-EDI28 ✔, S-EDI32 ✔, S-EDI300 ✔, S-GFN08 ✔, S-GFN24 ✔, S-GFN25 ✔, S-LAM11 ✔, S-PAG17 ✔, S-PAG25 ✔, S-PAG30 ✔, S-PAG32 ✔, S-PAG35 ✔, S-PAG41 ✔, S-TEC10 ✔, S-TEC11 ✔, S-CLQ04 ✔, S-ESP04 ✔, S-APP06 ✔, S-APP18 ✔, S-MOD12 ✔ | Crear, abrir, guardar y duplicar sin interfaz; el simulador de escritorio abre proyectos y modelos, crea un grafcet nuevo, lo guarda y lo reabre (P-IMP-29, P-IMP-32), y pregunta antes de descartar cambios; sin duplicar desde la interfaz |
| REQ-EDT-02 | P/alta | 07 | IMPL-P | editor | T-21b ✔, T-21c ✔, S-UIV02 ✔, S-AFI08 ✔, S-AFI01 ✔, S-AFI02 ✔, S-AFI04 ✔, S-LEY01 ✔, S-LEY02 ✔, S-DBR01 ✔, S-DBR02 ✔, S-DBR03 ✔, S-DBR04 ✔, S-DBR05 ✔, S-DBR06 ✔, S-DBR09 ✔, S-DBR13 ✔, S-FBR01 ✔, S-FBR04 ✔, S-VIS08 ✔, S-VIS10 ✔, S-EDI286 ✔, S-EDI287 ✔, S-EDI288 ✔, S-EDI296 ✔, S-EDI318 ✔, S-EDI319 ✔, S-EDI325 ✔, S-EDI313 ✔, S-EDI314 ✔, S-EDI315 ✔, S-EDI316 ✔, S-EDI317 ✔, S-EDI200 ✔, S-EDI201 ✔, S-EDI202 ✔, S-EDI203 ✔, S-EDI274 ✔, S-EDI275 ✔, S-EDI276 ✔, S-EDI213 ✔, S-EDI215 ✔, S-EDI216 ✔, S-EDI271 ✔, S-EDI321 ✔, S-EDI322 ✔, S-EDI323 ✔, S-EDI324 ✔, S-EDI310 ✔, S-EDI311 ✔, S-EDI312 ✔, S-EDI326 ✔, S-EDI258 ✔, S-EDI259 ✔, S-EDI273 ✔, S-EDI290 ✔, S-EDI294 ✔, S-EDI247 ✔, S-EDI248 ✔, S-EDI249 ✔, S-EDI250 ✔, S-EDI251 ✔, S-EDI253 ✔, S-EDI254 ✔, S-EDI255 ✔, S-EDI256 ✔, S-EDI257 ✔, S-EDI267 ✔, S-EDI272 ✔, S-EDI280 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI283 ✔, S-EDI285 ✔, S-EDI243 ✔, S-EDI244 ✔, S-EDI245 ✔, S-EDI246 ✔, S-EDI303 ✔, S-EDI304 ✔, S-EDI305 ✔, S-EDI307 ✔, S-EDI309 ✔, S-EDI42 ✔, S-EDI50 ✔, S-EDI51 ✔, S-EDI54 ✔, S-EDI56 ✔, S-EDI57 ✔, S-EDI64 ✔, S-EDI97 ✔, S-EDI03 ✔, S-EDI100 ✔, S-EDI101 ✔, S-EDI105 ✔, S-EDI106 ✔, S-EDI10 ✔, S-EDI111 ✔, S-EDI112 ✔, S-EDI115 ✔, S-EDI116 ✔, S-EDI119 ✔, S-EDI11 ✔, S-EDI120 ✔, S-EDI121 ✔, S-EDI122 ✔, S-EDI123 ✔, S-EDI124 ✔, S-EDI126 ✔, S-EDI127 ✔, S-EDI128 ✔, S-EDI129 ✔, S-EDI12 ✔, S-EDI130 ✔, S-EDI131 ✔, S-EDI132 ✔, S-EDI133 ✔, S-EDI134 ✔, S-EDI135 ✔, S-EDI136 ✔, S-EDI137 ✔, S-EDI138 ✔, S-EDI13 ✔, S-EDI14 ✔, S-EDI15 ✔, S-EDI170 ✔, S-EDI171 ✔, S-EDI172 ✔, S-EDI174 ✔, S-EDI17 ✔, S-EDI180 ✔, S-EDI182 ✔, S-EDI183 ✔, S-EDI187 ✔, S-EDI18 ✔, S-EDI190 ✔, S-EDI194 ✔, S-EDI195 ✔, S-EDI19 ✔, S-EDI21 ✔, S-EDI24 ✔, S-EDI25 ✔, S-EDI28 ✔, S-EDI297 ✔, S-EDI298 ✔, S-EDI299 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI31 ✔, S-EDI33 ✔, S-EDI34 ✔, S-EDI35 ✔, S-EDI36 ✔, S-EDI38 ✔, S-EDI41 ✔, S-EDI44 ✔, S-EDI48 ✔, S-EDI52 ✔, S-EDI53 ✔, S-EDI55 ✔, S-EDI58 ✔, S-EDI59 ✔, S-EDI60 ✔, S-EDI61 ✔, S-EDI62 ✔, S-EDI63 ✔, S-EDI65 ✔, S-EDI66 ✔, S-EDI67 ✔, S-EDI68 ✔, S-EDI69 ✔, S-EDI70 ✔, S-EDI71 ✔, S-EDI72 ✔, S-EDI74 ✔, S-EDI82 ✔, S-EDI87 ✔, S-EDI88 ✔, S-EDI89 ✔, S-EDI90 ✔, S-EDI92 ✔, S-EDI93 ✔, S-EDI94 ✔, S-EDI95 ✔, S-EDI99 ✔, S-EDI16 ✔, S-EDI45 ✔, S-EDI46 ✔, S-EDI47 ✔, S-EDI01 ✔, S-EDI140 ✔, S-EDI141 ✔, S-EDI142 ✔, S-OTR01 ✔, S-OTR05 ✔, S-OTR06 ✔, S-OTR07 ✔, S-ETI02 ✔, S-ETI03 ✔, S-ETI01 ✔, S-LAZ01 ✔, S-LAZ02 ✔, S-LAZ03 ✔, S-LAZ05 ✔, S-LAZ06 ✔, S-LAZ09 ✔, S-PAL01 ✔, S-PAL02 ✔, S-PAL03 ✔, S-PAL04 ✔, S-PAL05 ✔, S-PAL07 ✔, S-PAN05 ✔, S-PAN09 ✔, S-VIS01 ✔, S-VIS02 ✔, S-VIS03 ✔, S-VIS04 ✔, S-VIS05 ✔, S-VIS11 ✔, S-VIS12 ✔, S-VIS13 ✔, S-VIS14 ✔, S-VIS15 ✔, S-COR05 ✔, S-COR07 ✔, S-COR09 ✔, S-REM08 ✔, S-REM09 ✔, S-SAL09 ✔, S-SAL04 ✔, S-SAL05 ✔, S-COL06 ✔, S-COL02 ✔, S-COL03 ✔, S-COL04 ✔, S-COL08 ✔ | Insertar, conectar, editar; borrador inválido guardable; en la interfaz de escritorio: etapas, transiciones, enlaces y receptividades de un secuencial (P-IMP-32); selección, salto y repetición con el ratón (P-IMP-33), flechas y recorridos manuales persistentes (P-IMP-35), tramos verticales mínimos y transición que se agarra sin sacar rama (P-IMP-36), una flecha por lazo, imán y arrastre desde la paleta (P-IMP-37), receptividades con un programador por bloques y acciones desde la etapa (P-IMP-38); panel de acciones y jerarquías, pendientes |
| REQ-EDT-03 | P/alta | 07 | PARCIAL | editor | T-04c ✔, T-21c ✔, S-DRF03 ✔, S-DRF02 ✔, S-EDI247 ✔, S-EDI248 ✔, S-EDI251 ✔, S-EDI222 ✔, S-EDI223 ✔, S-EDI224 ✔, S-EDI225 ✔, S-EDI226 ✔, S-EDI227 ✔, S-EDI234 ✔, S-EDI235 ✔, S-EDI220 ✔, S-EDI221 ✔, S-EDI10 ✔, S-EDI188 ✔, S-EDI195 ✔, S-EDI29 ✔, S-EDI30 ✔, S-EDI37 ✔, S-EDI01 ✔, S-EDI152 ✔, S-OTR08 ✔, S-OTR12 ✔, S-LAZ01 ✔, S-LAZ04 ✔, S-LAZ07 ✔, S-LAZ08 ✔, S-LAZ09 ✔, S-LAZ10 ✔, S-LAZ11 ✔, S-LAZ12 ✔, S-PAL07 ✔, S-CLQ02 ✔, S-CLQ05 ✔, S-CLQ11 ✔, S-CLI07 ✔ | Mover, alinear, distribuir y deshacer; zoom en la vista del simulador (P-IMP-29); en la interfaz de escritorio, mover con rejilla de 20 y deshacer o rehacer (P-IMP-32); alinear y distribuir, pendientes en la interfaz |
| REQ-EDT-04 | P/crítica | 07 | IMPL-P | editor | T-21e ✔, S-EDI158 ✔, S-OTR02 ✔, S-OTR11 ✔, S-CLQ01 ✔, S-CLQ02 ✔, S-CLQ03 ✔, S-CLQ04 ✔, S-CLQ05 ✔, S-CLQ06 ✔, S-CLQ07 ✔, S-CLQ08 ✔, S-CLQ09 ✔, S-CLQ10 ✔, S-CLQ11 ✔, S-CLI01 ✔, S-CLI02 ✔, S-CLI03 ✔, S-CLI04 ✔, S-CLI05 ✔, S-CLI06 ✔, S-CLI07 ✔, S-CLI08 ✔, S-CLI09 ✔, S-CLI10 ✔, S-CLI11 ✔, S-CLI12 ✔, S-CLI13 ✔, S-CLI14 ✔, S-COR01 ✔, S-COR06 ✔ | Copiar/pegar con IDs nuevos y decisión explícita de referencias externas |
| REQ-EDT-05 | P/crítica | 07 | IMPL-P | editor | T-21f ✔, S-DBR01 ✔, S-DBR02 ✔, S-DBR03 ✔, S-DBR04 ✔, S-DBR05 ✔, S-DBR06 ✔, S-DBR07 ✔, S-DBR10 ✔, S-EDI322 ✔, S-DRF03 ✔, S-DRF04 ✔, S-DRF01 ✔, S-EDI233 ✔, S-EDI250 ✔, S-EDI254 ✔, S-EDI281 ✔, S-EDI282 ✔, S-EDI284 ✔, S-EDI243 ✔, S-EDI245 ✔, S-EDI220 ✔, S-EDI303 ✔, S-EDI304 ✔, S-EDI306 ✔, S-EDI307 ✔, S-EDI309 ✔, S-EDI328 ✔, S-EDI240 ✔, S-EDI241 ✔, S-EDI242 ✔, S-EDI05 ✔, S-EDI102 ✔, S-EDI171 ✔, S-EDI174 ✔, S-EDI178 ✔, S-EDI179 ✔, S-EDI183 ✔, S-EDI184 ✔, S-EDI188 ✔, S-EDI191 ✔, S-EDI196 ✔, S-EDI197 ✔, S-EDI139 ✔, S-EDI145 ✔, S-EDI147 ✔, S-EDI149 ✔, S-EDI150 ✔, S-EDI153 ✔, S-EDI300 ✔, S-EDI301 ✔, S-OTR01 ✔, S-OTR05 ✔, S-OTR11 ✔, S-ETI01 ✔, S-GFN08 ✔, S-GFN10 ✔, S-GFN14 ✔, S-GFN20 ✔, S-IEJ03 ✔, S-LAM01 ✔, S-LAZ01 ✔, S-LAZ03 ✔, S-LAZ04 ✔, S-LAZ06 ✔, S-LAZ07 ✔, S-LAZ08 ✔, S-LAZ10 ✔, S-LAZ12 ✔, S-PAG04 ✔, S-PAG20 ✔, S-PAG24 ✔, S-PAG26 ✔, S-PAG31 ✔, S-PAG34 ✔, S-PAG39 ✔, S-PAG40 ✔, S-PLT05 ✔, S-TEC10 ✔, S-TEC02 ✔, S-CLQ01 ✔, S-CLQ05 ✔, S-CLQ06 ✔, S-CLQ11 ✔, S-CLI04 ✔, S-COR05 ✔, S-SAL06 ✔, S-SAL09 ✔ | Transacciones atómicas; fallo fuera del historial; rehacer descartado |
| REQ-EDT-06 | P/crítica | 07 | IMPL-P | editor | T-21d ✔, S-EDI08 ✔, S-EDI43 ✔, S-EDI151 ✔, S-EDI156 ✔ | Renombrar sin cambiar ID, usos actualizados, colisión diagnosticada, búsqueda con ruta |
| REQ-EDT-07 | P/alta | 07 | IMPL-P | editor | T-09b ✔, T-21d ✔, S-UIV04 ✔, S-USO04 ✔, S-EDI54 ✔, S-EDI103 ✔, S-EDI104 ✔, S-EDI111 ✔, S-EDI114 ✔, S-EDI117 ✔, S-EDI118 ✔, S-EDI260 ✔, S-EDI261 ✔, S-EDI262 ✔, S-EDI263 ✔, S-EDI264 ✔, S-EDI268 ✔, S-EDI40 ✔, S-EDI43 ✔, S-EDI49 ✔, S-EDI66 ✔, S-EDI79 ✔, S-EDI80 ✔, S-EDI85 ✔, S-EDI94 ✔, S-EDI96 ✔, S-EDI39 ✔, S-IEJ04 ✔, S-IEJ07 ✔, S-IEJ08 ✔, S-MAP02 ✔, S-FIO76 ✔, S-FIO37 ✔, S-FIO38 ✔, S-FIO42 ✔, S-FIO67 ✔, S-PAN03 ✔, S-CLQ03 ✔, S-VIS15 ✔, S-REM02 ✔, S-APP14 ✔, S-APP16 ✔, S-MOD10 ✔ | Diccionario de variables y usos afectados por un cambio; en la interfaz de escritorio, panel de variables (nombre, papel, tipo, valor inicial, unidad, usos) y acciones de etapa con su diálogo (P-IMP-38) |
| REQ-EDT-08 | P/alta | 07 | IMPL-P | editor, escritorio | T-21g —, S-EDI316 ✔, S-EDI289 ✔, S-EDI291 ✔, S-EDI292 ✔, S-EDI293 ✔, S-EDI294 ✔, S-EDI177 ✔, S-EDI185 ✔, S-EDI186 ✔, S-EDI152 ✔, S-MTP23 ✔, S-MTP01 ✔ | Navegación entre macroetapas y encapsulantes con ruta visible y vuelta al contexto (P-IMP-61, P-IMP-62) |
| REQ-EDT-09 | P/alta | 07 | IMPL-P | diagnostics | T-21b ✔, T-09c ✔, S-UIV03 ✔, S-UIV05 ✔, S-UIV06 ✔, S-AJU01 ✔, S-AJU06 ✔, S-AJU07 ✔, S-AJU09 ✔, S-ALT01 ✔, S-ALT02 ✔, S-RCT01 ✔, S-AVI01 ✔, S-AVI03 ✔, S-AVI04 ✔, S-DBR10 ✔, S-DBR11 ✔, S-DBR13 ✔, S-FBR01 ✔, S-FBR02 ✔, S-FBR03 ✔, S-FBR04 ✔, S-FBR05 ✔, S-FBR06 ✔, S-USO02 ✔, S-USO04 ✔, S-DRF04 ✔, S-DRF01 ✔, S-EDI310 ✔, S-EDI311 ✔, S-EDI326 ✔, S-EDI327 ✔, S-EDI232 ✔, S-EDI255 ✔, S-EDI257 ✔, S-EDI267 ✔, S-EDI272 ✔, S-EDI06 ✔, S-EDI103 ✔, S-EDI112 ✔, S-EDI118 ✔, S-EDI119 ✔, S-EDI121 ✔, S-EDI122 ✔, S-EDI136 ✔, S-EDI14 ✔, S-EDI174 ✔, S-EDI175 ✔, S-EDI178 ✔, S-EDI183 ✔, S-EDI185 ✔, S-EDI192 ✔, S-EDI261 ✔, S-EDI73 ✔, S-EDI76 ✔, S-EDI77 ✔, S-EDI78 ✔, S-EDI80 ✔, S-EDI81 ✔, S-EDI96 ✔, S-EDI02 ✔, S-EDI157 ✔, S-OTR03 ✔, S-OTR04 ✔, S-OTR09 ✔, S-OTR10 ✔, S-ETI02 ✔, S-GFN23 ✔, S-GFN24 ✔, S-IEJ02 ✔, S-MAP04 ✔, S-MTP10 ✔, S-MTP11 ✔, S-MTP12 ✔, S-MTP13 ✔, S-MTP20 ✔, S-MTP21 ✔, S-MTP22 ✔, S-MTP04 ✔, S-PAL05 ✔, S-PAL06 ✔, S-PAN01 ✔, S-PAN02 ✔, S-PAN03 ✔, S-PAN04 ✔, S-PAN05 ✔, S-PAN06 ✔, S-PAN07 ✔, S-PAN08 ✔, S-PAN09 ✔, S-PAN10 ✔, S-PAN11 ✔, S-CLI12 ✔, S-ESP14 ✔, S-VIS05 ✔, S-REM01 ✔, S-REM02 ✔, S-REM03 ✔, S-REM07 ✔, S-SAL07 ✔, S-SAL08 ✔, S-ESC01 ✔, S-MOD01 ✔, S-MOD02 ✔, S-MOD03 ✔, S-MOD04 ✔, S-MOD05 ✔, S-MOD09 ✔, S-MOD10 ✔, S-MOD11 ✔, S-MOD12 ✔, S-MOD13 ✔ | Código, gravedad, elemento, evidencia y corrección; panel de diagnósticos del editor de escritorio con clic que selecciona y centra el elemento (P-IMP-32); foco de teclado pendiente |
| REQ-EDT-10 | P/crítica | 07 | IMPL-P | persistence | T-22d ✔, S-UIV04 ✔, S-EDI197 ✔ | Recuperación separada cada 30 s si hay cambios, sin sobrescritura; conectada al editor de escritorio, que la ofrece al arrancar (P-IMP-32) |
| REQ-EDT-11 | P/alta | 07 | IMPL-P | escritorio/laminas | T-21h —, S-AJU08 ✔, S-EDI265 ✔, S-LAM01 ✔, S-LAM02 ✔, S-LAM11 ✔, S-LAM03 ✔, S-LAM04 ✔, S-LAM05 ✔, S-LAM06 ✔, S-LAM07 ✔, S-LAM08 ✔, S-LAM09 ✔, S-LAM10 ✔, S-LAM12 ✔, S-LAM13 ✔, S-LAM14 ✔, S-LAM15 ✔, S-MAP05 ✔, S-PAG01 ✔, S-PAG02 ✔, S-PAG03 ✔, S-PAG04 ✔, S-PAG05 ✔, S-PAG06 ✔, S-PAG07 ✔, S-PAG08 ✔, S-PAG09 ✔, S-PAG10 ✔, S-PAG11 ✔, S-PAG12 ✔, S-PAG13 ✔, S-PAG14 ✔, S-PAG15 ✔, S-PAG16 ✔, S-PAG17 ✔, S-PAG18 ✔, S-PAG19 ✔, S-PAG20 ✔, S-PAG21 ✔, S-PAG22 ✔, S-PAG23 ✔, S-PAG24 ✔, S-PAG25 ✔, S-PAG26 ✔, S-PAG27 ✔, S-PAG28 ✔, S-PAG29 ✔, S-PAG30 ✔, S-PAG31 ✔, S-PAG32 ✔, S-PAG33 ✔, S-PAG34 ✔, S-PAG35 ✔, S-PAG36 ✔, S-PAG37 ✔, S-PAG38 ✔, S-PAG39 ✔, S-PAG40 ✔, S-PAG41 ✔, S-PAG42 ✔, S-PLT01 ✔, S-PLT02 ✔, S-PLT03 ✔, S-PLT04 ✔, S-PLT05 ✔, S-PLT06 ✔, S-PLT07 ✔, S-PLT08 ✔, S-PLT09 ✔, S-PLT10 ✔, S-PLT11 ✔, S-PLT12 ✔, S-PLT13 ✔, S-PLT14 ✔, S-PLT15 ✔, S-PLT16 ✔, S-PLT17 ✔, S-TEC10 ✔, S-TEC01 ✔, S-TEC02 ✔, S-TEC03 ✔, S-TEC04 ✔, S-TEC05 ✔, S-TEC06 ✔, S-TEC07 ✔, S-TEC08 ✔, S-TEC09 ✔, S-TEC12 ✔ | Láminas con marco y cajetín; exportación vectorial PDF y SVG sin elementos de edición e impresión (P-IMP-81, P-IMP-82) |
| REQ-EDT-12 | P/alta | 07 | IMPL-P | escritorio/navegacion | T-21g —, T-25a ◐, S-NAV04 ✔, S-NAV01 ✔, S-NAV02 ✔, S-NAV03 ✔, S-NAV05 ✔, S-NAV06 ✔ | Zoom, búsqueda Ctrl+F y filtros por parcial; sin vista general en miniatura por decisión del responsable (P-IMP-83) |
| REQ-EDT-13 | P/alta | 07 | IMPL-P | escritorio/navegacion, diagrama | T-26a —, T-26b —, S-IEJ05 ✔, S-ACC01 ✔, S-ACC02 ✔, S-ACC03 ✔, S-ACC04 ✔, S-ACC05 ✔, S-ACC06 ✔, S-ACC07 ✔, S-NAV07 ✔, S-CLQ01 ✔, S-CLQ03 ✔, S-CLQ07 ✔ | Recorrido y edición con teclado, foco visible y nombres accesibles (P-IMP-83) |
| REQ-EDT-14 | P/crítica | 07 | IMPL-P | editor, engine | T-23d ✔, S-AFI02 ✔, S-AFI04 ✔, S-EDI228 ✔, S-EDI252 ✔, S-EDI222 ✔, S-EDI223 ✔, S-EDI226 ✔, S-EDI234 ✔, S-EDI235 ✔, S-EDI246 ✔, S-EDI220 ✔, S-EDI221 ✔, S-EDI03 ✔, S-EDI107 ✔, S-EDI108 ✔, S-EDI109 ✔, S-EDI73 ✔ | Edición semántica = revisión nueva; la ejecución conserva la suya |
| REQ-SIM-01 | P/crítica | 08 | IMPL-P | engine | T-23a ✔, T-23b ✔, S-IEJ01 ✔, S-IEJ06 ✔, S-IEJ03 ✔ | Estados de sesión, pausas en frontera completa, microavance, puntos antes/después |
| REQ-SIM-02 | P/crítica | 08 | IMPL-P | scenario, engine | T-10b ✔, T-23c ✔, S-RED03 ✔, S-RED04 ✔, S-RED09 ✔, S-MAP07 ✔, S-FIO01 ✔, S-FIO06 ✔, S-FIO11 ✔, S-FIO09 ✔, S-FIO30 ✔, S-FIO51 ✔, S-FIO52 ✔, S-FIO59 ✔, S-FIO61 ✔, S-FIO64 ✔, S-FIO69 ✔, S-FIO16 ✔, S-FIO18 ✔, S-FIO27 ✔, S-FIO29 ✔, S-FIO31 ✔, S-FIO40 ✔, S-FIO47 ✔, S-FIO49 ✔, S-FIO50 ✔, S-FIO53 ✔, S-FIO60 ✔, S-FIO63 ✔, S-PUL01 ✔, S-PUL02 ✔, S-PUL03 ✔, S-PUL04 ✔, S-PUL05 ✔, S-PUL06 ✔, S-APP04 ✔, S-MOD07 ✔ | Escenarios y entradas manuales registradas con origen y ordinal |
| REQ-SIM-03 | P/alta | 08 | IMPL-P | engine | T-02a ✔, T-02b ✔, T-02c ✔, T-23a ✔, S-UIV01 ✔, S-UIV02 ✔, S-UIV05 ✔, S-AJU02 ✔, S-AJU03 ✔, S-AFI05 ✔, S-AFI06 ✔, S-AFI07 ✔, S-AFI08 ✔, S-AFI03 ✔, S-VIS06 ✔, S-VIS07 ✔, S-VIS10 ✔, S-VIS09 ✔, S-USO01 ✔, S-USO02 ✔, S-USO03 ✔, S-USO05 ✔, S-EDI288 ✔, S-EDI207 ✔, S-EDI208 ✔, S-EDI209 ✔, S-EDI210 ✔, S-EDI211 ✔, S-EDI212 ✔, S-EDI315 ✔, S-EDI204 ✔, S-EDI213 ✔, S-EDI214 ✔, S-EDI215 ✔, S-EDI217 ✔, S-EDI218 ✔, S-EDI219 ✔, S-EDI269 ✔, S-EDI271 ✔, S-EDI289 ✔, S-EDI321 ✔, S-EDI323 ✔, S-EDI324 ✔, S-EDI327 ✔, S-EDI258 ✔, S-EDI229 ✔, S-EDI290 ✔, S-EDI252 ✔, S-EDI284 ✔, S-EDI306 ✔, S-EDI109 ✔, S-EDI113 ✔, S-EDI182 ✔, S-EDI190 ✔, S-EDI191 ✔, S-EDI22 ✔, S-EDI265 ✔, S-EDI266 ✔, S-EDI270 ✔, S-EDI27 ✔, S-EDI297 ✔, S-EDI298 ✔, S-EDI299 ✔, S-EDI32 ✔, S-EDI40 ✔, S-EDI78 ✔, S-RED01 ✔, S-RED02 ✔, S-RED06 ✔, S-RED07 ✔, S-RED16 ✔, S-RED03 ✔, S-RED04 ✔, S-RED08 ✔, S-RED09 ✔, S-RED10 ✔, S-RED11 ✔, S-RED12 ✔, S-RED13 ✔, S-RED14 ✔, S-RED15 ✔, S-RED17 ✔, S-MAP02 ✔, S-MAP03 ✔, S-MAP06 ✔, S-MAP08 ✔, S-MAP01 ✔, S-MAP11 ✔, S-FIO76 ✔, S-FIO77 ✔, S-FIO78 ✔, S-FIO36 ✔, S-FIO51 ✔, S-FIO64 ✔, S-FIO65 ✔, S-FIO68 ✔, S-FIO08 ✔, S-FIO16 ✔, S-FIO17 ✔, S-FIO19 ✔, S-FIO20 ✔, S-FIO22 ✔, S-FIO24 ✔, S-FIO25 ✔, S-FIO27 ✔, S-FIO28 ✔, S-FIO30 ✔, S-FIO31 ✔, S-FIO32 ✔, S-FIO33 ✔, S-FIO34 ✔, S-FIO35 ✔, S-FIO37 ✔, S-FIO38 ✔, S-FIO39 ✔, S-FIO40 ✔, S-FIO41 ✔, S-FIO42 ✔, S-FIO43 ✔, S-FIO44 ✔, S-FIO45 ✔, S-FIO46 ✔, S-FIO47 ✔, S-FIO48 ✔, S-FIO49 ✔, S-FIO53 ✔, S-FIO54 ✔, S-FIO55 ✔, S-FIO57 ✔, S-FIO60 ✔, S-FIO63 ✔, S-FIO66 ✔, S-FIO67 ✔, S-PAN08 ✔, S-PAG02 ✔, S-ESP01 ✔, S-ESP02 ✔, S-ESP03 ✔, S-ESP05 ✔, S-ESP06 ✔, S-ESP07 ✔, S-ESP08 ✔, S-ESP09 ✔, S-ESP10 ✔, S-ESP12 ✔, S-ESP14 ✔, S-CTL01 ✔, S-CTL02 ✔, S-PUL01 ✔, S-PUL04 ✔, S-PUL06 ✔, S-VIS04 ✔, S-COR02 ✔, S-COR03 ✔, S-COR04 ✔, S-COR10 ✔, S-COR08 ✔, S-REM04 ✔, S-REM05 ✔, S-REM06 ✔, S-REM08 ✔, S-REM09 ✔, S-SAL01 ✔, S-SAL02 ✔, S-SAL03 ✔, S-APP14 ✔, S-APP15 ✔, S-APP05 ✔, S-APP09 ✔, S-APP10 ✔, S-APP11 ✔, S-APP12 ✔, S-APP13 ✔, S-APP16 ✔, S-APP17 ✔, S-APP18 ✔, S-APP19 ✔, S-APP20 ✔, S-COL06 ✔, S-COL01 ✔, S-COL02 ✔, S-COL03 ✔, S-COL05 ✔, S-COL07 ✔, S-COL08 ✔, S-MOD01 ✔, S-MOD02 ✔, S-MOD04 ✔, S-MOD06 ✔, S-MOD07 ✔, S-MOD08 ✔, S-MOD11 ✔, S-MOD13 ✔ | Observación de actividad, validación, receptividad y franqueamiento |
| REQ-SIM-04 | P/crítica | 08 | IMPL-P | engine | T-23c ✔, T-22f ✔, T-23f ✔, S-AFI07 ✔, S-FIO21 ✔, S-FIO30 ✔, S-FIO58 ✔, S-FIO59 ✔, S-FIO69 ✔, S-ESP13 ✔, S-CTL01 ✔, S-CTL02 ✔, S-REM06 ✔, S-APP17 ✔, S-OPT03d ✔, S-MOD06 ✔ | Instantánea con Z completo y compatibilidad exacta; dentro de recorrido D-INSTANTANEA-FASE |
| REQ-SIM-05 | P/crítica | 08 | IMPL-P | trace | T-04a ✔, T-22g ✔, S-OPT03b ✔ | Traza con conjuntos E, causas, cierre y digest |
| REQ-SIM-06 | P/crítica | 08 | IMPL-P | engine | T-09d ✔, T-23b ✔ | Observar y pausar no modifican comportamiento |
| REQ-SIM-07 | P/crítica | 08 | IMPL-P | engine | T-23e ✔ | Intervención E en pausa estable, rama auditable |
| REQ-SIM-08 | P/alta | 08 | IMPL-P | diagnostics, engine | T-08a ✔, T-08b ✔, T-16a ✔, S-AVI01 ✔, S-AVI02 ✔, S-08a ✔ | Evidencia y corrección recomendada en cada diagnóstico |
| REQ-DAT-01 | P/crítica | 09 | IMPL-P | model, persistence, ids | T-22b ✔, T-21e ✔, S-DBR08 ✔, S-FBR05 ✔, S-GFN01 ✔, S-GFN02 ✔, S-GFN03 ✔, S-EDI251 ✔, S-EDI283 ✔, S-EDI308 ✔, S-EDI107 ✔, S-EDI118 ✔, S-EDI124 ✔, S-EDI179 ✔, S-EDI73 ✔, S-EDI77 ✔, S-EDI82 ✔, S-EDI91 ✔, S-EDI98 ✔, S-EDI302 ✔, S-GFN11 ✔, S-GFN14 ✔, S-GFN20 ✔, S-LAM09 ✔, S-MTP23 ✔, S-CLI05 ✔, S-PUL03 ✔, S-H12 ✔ | Identidades, referencias y propiedad; nombres hexadecimales (H-12) |
| REQ-DAT-02 | P/crítica | 09 | IMPL-P | persistence | T-22a ✔, S-AJU02 ✔, S-AJU03 ✔, S-DBR11 ✔, S-DBR12 ✔, S-CMP04 ✔, S-GFN01 ✔, S-GFN03 ✔, S-GFN04 ✔, S-GFN07 ✔, S-GFN16 ✔, S-GFN17 ✔, S-GFN18 ✔, S-USO03 ✔, S-USO05 ✔, S-DRF04 ✔, S-EDI04 ✔, S-EDI154 ✔, S-EDI302 ✔, S-OTR06 ✔, S-OTR10 ✔, S-OTR13 ✔, S-ETI03 ✔, S-GFN10 ✔, S-GFN11 ✔, S-GFN12 ✔, S-GFN19 ✔, S-GFN25 ✔, S-LAM01 ✔, S-LAM02 ✔, S-LAM12 ✔, S-RED06 ✔, S-FIO04 ✔, S-FIO23 ✔, S-FIO26 ✔, S-FIO56 ✔, S-FIO57 ✔, S-FIO24 ✔, S-FIO41 ✔, S-FIO46 ✔, S-PAG03 ✔, S-PAG08 ✔, S-PAG11 ✔, S-PAG18 ✔, S-PAG19 ✔, S-PAG23 ✔, S-PAG28 ✔, S-PAG33 ✔, S-PAG37 ✔, S-PAG39 ✔, S-PLT01 ✔, S-PLT05 ✔, S-PLT11 ✔, S-PLT12 ✔, S-TEC11 ✔, S-TEC02 ✔, S-TEC03 ✔, S-TEC07 ✔, S-PRP20 ✔, S-PRP21 ✔, S-PRP22 ✔, S-PRP23 ✔, S-PRP01 ✔, S-PRP02 ✔, S-PRP03 ✔, S-PRP04 ✔, S-PRP05 ✔, S-PRP06 ✔, S-RSL01 ✔, S-RSL02 ✔, S-RSL03 ✔, S-RSL04 ✔, S-RSL05 ✔, S-ESP02 ✔, S-ESP03 ✔, S-ESP04 ✔, S-ESP10 ✔, S-ESP11 ✔, S-ESP13 ✔, S-REM04 ✔, S-APP01 ✔, S-APP06 ✔ | Ida y vuelta conserva significado, notas y vista (formato 0.1 provisional, U-11) |
| REQ-DAT-03 | P/crítica | 09 | IMPL-P | persistence | T-22c ✔, T-22e ✔, S-APP02 ✔ | Versión mayor/menor, desconocidos y migración con copia e informe |
| REQ-DAT-04 | P/crítica | 09 | IMPL-P | engine | T-22f ✔, T-23c ✔, T-23f ✔, S-OPT03d ✔ | Instantánea íntegra y compatibilidad exacta; campos U no aplicables declarados |
| REQ-DAT-05 | P/crítica | 09 | IMPL-P | canonical, timeutil | T-24a ◐, T-24b ✔, S-CAN ✔ | Representación canónica y SHA-256 independientes de región |
| REQ-DAT-06 | P/crítica | 09 | IMPL-P | canonical, persistence, expressions | T-25b ✔, T-25c ✔, S-CAN ✔ | Sin código ejecutable, sin rutas fuera de raíz, límites previos |
| REQ-DAT-07 | P/crítica | 09 | IMPL-P | persistence | T-22d ✔ | Guardado atómico con diario; recuperación del último válido |
| REQ-DAT-08 | P/crítica | 09 | IMPL-P | model, trace | T-09c ✔, T-22g ✔, S-CLI08 ✔ | Divergencia texto-significado y trazas truncadas |
| REQ-ARQ-01 | P/crítica | 10 | IMPL-P | todo el núcleo | T-23b ✔, T-24a ◐ | Todo el contrato se verifica sin interfaz (esta batería) |
| REQ-PLT-01 | P/crítica | 10 | PEND-PLT | trace | T-24a ◐ | Trazas canónicas deterministas en Windows; comparación en macOS/Linux pendiente (U-10) |
| REQ-PLT-02 | P/alta | 10 | PARCIAL | timeutil, persistence | T-24b ✔, T-24c ◐, S-H12 ✔ | Región, Unicode, rutas y mayúsculas verificados en Windows; de momento solo Windows 10 y 11 (P-IMP-85); otros sistemas U-10 |
| REQ-PLT-03 | P/alta | 10 | PARCIAL | todo el núcleo | T-24d ◐, T-24e — | Sin conexión verificado; versión portable para Windows sin instalador (P-IMP-29); proyectos .grafnet versionados y misma clave de sello entre versiones (P-IMP-80); comprobación con el ejecutable de entrega pendiente |
| REQ-PLT-04 | P/alta | 10 | PARCIAL | model, persistence, tools/medir_presupuestos.py | T-25a ◐, T-25d — | Límites aplicados; medición indicativa; medición declarada en el equipo del responsable en la entrega (P-IMP-85) |
| REQ-ROB-01 | P/crítica | 10 | IMPL-P | model, engine, persistence | T-08a ✔, T-08b ✔, T-25a ◐, S-USO01 ✔, S-MAP04 ✔, S-FIO02 ✔, S-FIO03 ✔, S-FIO14 ✔, S-FIO07 ✔, S-FIO70 ✔, S-FIO71 ✔, S-FIO74 ✔, S-FIO75 ✔, S-FIO77 ✔, S-FIO10 ✔, S-FIO36 ✔, S-FIO52 ✔, S-FIO61 ✔, S-FIO65 ✔, S-FIO68 ✔, S-FIO69 ✔, S-FIO05 ✔, S-FIO56 ✔, S-FIO50 ✔, S-FIO53 ✔, S-FIO54 ✔, S-FIO55 ✔, S-FIO57 ✔, S-FIO62 ✔, S-ESP11 ✔, S-ESP12 ✔, S-COR03 ✔, S-08a ✔ | Límites de datos y de evolución diagnosticados sin alterar significado |
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
| S-ACC01 | REQ-EDT-13 | pasa | `test_SACC01_tab_inverso_esc_y_salida_sin_trampa` | Tab recorre elementos, Mayús+Tab vuelve y Ctrl+Tab sale hacia controles. |
| S-ACC02 | REQ-EDT-13 | pasa | `test_SACC02_flecha_rejilla_deshacer_e_intro` | flechas mueven un paso con deshacer; Intro permite editar la etiqueta sin ratón. |
| S-ACC03 | REQ-EDT-13 | pasa | `test_SACC03_supr_borra_y_respeta_el_campo_de_texto` | Supr en el dibujo borra; dentro de una etiqueta solo edita el texto. |
| S-ACC04 | REQ-EDT-13 | pasa | `test_SACC04_lista_textual_estados_relaciones_y_foco` | estados y relaciones se leen sin depender del color; botones y paneles tienen nombre. |
| S-ACC05 | REQ-EDT-13 | pasa | `test_SACC05_crear_editar_simular_y_guardar_sin_raton` | creación enlazada, propiedades, validación al Play, Stop y guardar mediante teclado. |
| S-ACC06 | REQ-EDT-13 | pasa | `test_SACC06_conectar_desde_menu_con_destino_por_teclado` | el menú permite enlazar elementos existentes sin gesto de ratón. |
| S-ACC07 | REQ-EDT-13 | pasa | `test_SACC07_movimiento_multiple_y_vista_vacia_sin_trampa` | las flechas desplazan toda la selección en una operación; Tab sale de un dibujo vacío. |
| S-AFI01 | REQ-EDT-02 | pasa | `test_SAFI01_transicion_corta_con_proporcion_igual_en_qt_y_js` | trazo de transición de 16 px frente a caja de etapa de 44 px, igual en los dos renderizadores. |
| S-AFI02 | REQ-EDT-02, REQ-EDT-14 | pasa | `test_SAFI02_doble_barra_separa_lados_y_tapa_trazos_en_su_hueco` | doble barra con 8 px de hueco y conectores detenidos arriba/abajo; nada la atraviesa visualmente. |
| S-AFI03 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SAFI03_lecturas_de_variables_y_tiempos_en_azul_sin_cambiar_verdaderos` | valor y tiempo en #326DCB, incluso al vencer; expresiones verdaderas conservan su verde. |
| S-AFI04 | REQ-EDT-02, REQ-EDT-14, REQ-MOD-03 | pasa | `test_SAFI04_lazos_anidados_sin_cruces_y_rutas_manuales_respetadas` | un retorno exterior rodea al interior; no se altera una ruta manual ni el modelo. |
| S-AFI05 | REQ-SIM-03 | pasa | `test_SAFI05_destino_resaltado_solo_fuera_del_plc_en_ambos_lados` | arrastrar resalta solo el lateral, dentro del PLC no se acepta el drop; válida la asignación exterior. |
| S-AFI06 | REQ-SIM-03 | pasa | `test_SAFI06_fila_completa_arrastrable_y_sin_barrita_en_figura` | gesto desde ambos extremos de la fila, con nombre alineado a la izquierda y figura sin cuadrado verde. |
| S-AFI07 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SAFI07_play_stop_reiniciar_inactivos_en_es_incluidos_atajos` | E/S deshabilita los controles y sus atajos; volver al dibujo los recupera sin parar la simulación. |
| S-AFI08 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SAFI08_icono_dependencia_con_marco_y_trazos_discontinuos_conserva_control` | icono de dependencia con caja y marco lateral; el conmutador sigue dibujando las dependencias. |
| S-AJU01 | REQ-EDT-09, REQ-JER-05 | pasa | `test_SAJU01_el_panel_de_una_etapa_de_un_recinto_tiene_la_casilla_enlace_de_activacion` | el panel de opciones de una etapa de un recinto muestra la casilla «Enlace de |
| S-AJU02 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SAJU02_un_proyecto_nuevo_no_hereda_los_16_8_recordados_de_una_version_anterior` | las preferencias recordadas por una versión anterior (16 digitales y 8 numéricas) |
| S-AJU03 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SAJU03_las_cantidades_de_un_proyecto_concreto_se_respetan_y_no_se_recuerdan_globalmente` | un proyecto con su propio mapa conserva sus cantidades; lo que se recuerda para los |
| S-AJU04 | REQ-SEM-09 | pasa | `test_SAJU04_el_dialogo_de_ajustes_de_simulacion_tiene_una_sola_opcion_con_palabras_normales` | «Ajustes de simulación» muestra solo la lectura de los eventos de entrada, con dos textos sin |
| S-AJU05 | REQ-NOR-02, REQ-SEM-09 | pasa | `test_SAJU05_barra_de_estado_basado_en_iec_60848_y_aviso_de_ajuste_no_habitual` | la barra de estado dice «Basado en IEC 60848» (sin «conformidad» ni |
| S-AJU06 | REQ-EDT-09 | pasa | `test_SAJU06_los_avisos_no_llevan_codigos_internos_ni_rojo_agresivo` | la lista de diagnósticos dice «t1: la receptividad está vacía» (sin D-…, U-… ni H-…), con |
| S-AJU07 | REQ-EDT-09 | pasa | `test_SAJU07_los_rechazos_del_nucleo_se_muestran_sin_codigos` | un rechazo del núcleo (aquí, convertir en macroetapa una etapa inicial) se enseña sin código. |
| S-AJU08 | REQ-EDT-11 | pasa | `test_SAJU08_el_boton_anadir_hoja_es_principal_y_parpadea_mientras_no_hay_hojas` | con la pestaña Planos sin hojas, «+ Añadir hoja» tiene el fondo del acento y texto blanco y |
| S-AJU09 | REQ-EDT-09 | pasa | `test_SAJU09_la_opcion_marcada_del_submenu_tipo_de_etapa_se_distingue` | en «Tipo de etapa» el orden es Etapa, Etapa inicial, Encapsulante, Macroetapa y la fila marcada |
| S-AJU10 | REQ-NOR-02 | pasa | `test_SAJU10_acerca_de_se_abre_desde_el_menu_ayuda_con_version_licencia_y_enlaces` | «Ayuda > Acerca de GRAFCET Connect…» abre un diálogo con la versión (la de escritorio.VERSION), |
| S-AJU11 | REQ-NOR-02 | pasa | `test_SAJU11_la_version_es_una_sola_constante_compartida_con_el_constructor` | tools/construir_ejecutable.py lee la versión de escritorio.VERSION, sin duplicar el número. |
| S-ALT01 | REQ-EDT-09 | pasa | `test_SALT01_panel_de_transicion_enseña_todos_los_operadores_sin_barra` | al seleccionar una transición el panel inferior mide al menos lo justo para ver la paleta de |
| S-ALT02 | REQ-EDT-09 | pasa | `test_SALT02_un_panel_mayor_que_el_minimo_se_respeta` | si el usuario hace el panel más grande que el mínimo, seleccionar una transición no lo cambia. |
| S-APP01 | REQ-DAT-02 | pasa | `test_SAPP01_abrir_lo_guardado` | un ejemplo guardado como proyecto se abre igual (modelo y posiciones) y simula |
| S-APP02 | REQ-DAT-03, REQ-ROB-02 | pasa | `test_SAPP02_abrir_rechaza_lo_que_no_es_modelo` | un documento de otra familia no se abre; uno con campos semánticos desconocidos |
| S-APP03 |  | pasa | `test_SAPP03_colocacion_automatica` | cada etapa, macroetapa y transición tiene posición, dos etapas no |
| S-APP04 | REQ-SIM-02 | pasa | `test_SAPP04_entradas_numericas` | una entrada numérica escrita a mano admite coma decimal y respeta tipo, escala y rango. |
| S-APP05 | REQ-SIM-03 | pasa | `test_SAPP05_ejemplos_en_la_ventana` | cada ejemplo se carga y se dibuja; abrirlo deja Pausa sin estado y, con Play, un clic en una entrada hace |
| S-APP06 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SAPP06_guardar_y_abrir_en_la_ventana` | «Guardar como proyecto» y «Abrir modelo» conservan el modelo y su dibujo. |
| S-APP07 |  | pasa | `test_SAPP07_lecturas_reinician` | Cambiar una lectura reinicia la simulación (queda en Pausa, sin estado, hasta Play) y se señala como distinta de la |
| S-APP08 | REQ-SEM-09 | pasa | `test_SAPP08_ajustes_y_lecturas` | «Ajustes» (entre Simulación y Ayuda) tiene los ajustes de simulación; el diálogo muestra una sola |
| S-APP09 | REQ-SIM-03 | pasa | `test_SAPP09_play_pausa_y_un_solo_control` | un solo control de ejecución. Play simula en tiempo real (traza abajo, sin paleta) y Pausa detiene y |
| S-APP10 | REQ-SIM-03 | pasa | `test_SAPP10_temporizador_en_dibujo_y_tabla` | «temporizada», con E1 activa y 1 s transcurrido, muestra «1,00 s» (solo lo transcurrido) encima de la |
| S-APP11 | REQ-SIM-03 | pasa | `test_SAPP11_paneles_plegables` | el panel derecho y el inferior se pliegan del todo con su flecha y desde «Ver»; el estado se guarda. |
| S-APP12 | REQ-SIM-03 | pasa | `test_SAPP12_zoom_se_conserva` | «+», «−» y la rueda con Ctrl cambian el zoom; un refresco lo conserva; «Ajustar» vuelve a encajar. |
| S-APP13 | REQ-SIM-03 | pasa | `test_SAPP13_tiempos_truncados_a_dos_decimales` | lo que lleva un temporizador y τ se muestran truncados a la baja a 2 decimales; el preset, tal cual. |
| S-APP14 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP14_nombres_en_vez_de_id` | un modelo hecho con el editor (ID internos) se dibuja y se traza con los nombres: |
| S-APP15 | REQ-SIM-03 | pasa | `test_SAPP15_ejemplos_no_cambian` | en los ejemplos el ID es el nombre: mostrar nombres no cambia nada del dibujo ni de la traza. |
| S-APP16 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SAPP16_ventana_con_nombres` | un modelo del editor, guardado y abierto en la ventana, muestra nombres en el dibujo, |
| S-APP17 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SAPP17_reiniciar_en_play_y_en_pausa` | Reiniciar vuelve a la situación inicial y en Play sigue en Play; en Pausa, que ya está todo |
| S-APP18 | REQ-EDT-01, REQ-SIM-03 | pasa | `test_SAPP18_abrir_ejemplo_o_modelo_deja_pausa_y_edicion` | al abrir un ejemplo o un modelo guardado, el ejemplo queda de consulta y el proyecto editable, ambos parados aunque |
| S-APP19 | REQ-SEM-07, REQ-SIM-03 | pasa | `test_SAPP19_inestable_avisa_una_vez_y_para` | si en Play el motor no alcanza una situación estable (D-LIM-EVOL), se detiene, pasa a |
| S-APP20 | REQ-JER-04, REQ-SIM-03 | pasa | `test_SAPP20_play_con_lecturas_que_no_compilan_avisa_y_queda_en_pausa` | si el modelo compila con las lecturas por defecto pero no con las activas (7.7 = B con una |
| S-AVI01 | REQ-EDT-09, REQ-SIM-08 | pasa | `test_SAVI01_parada_por_bucle_se_traduce_sin_jerga` | el presupuesto agotado se cuenta como «no se queda quieto», sin τ ni presupuesto. |
| S-AVI02 | REQ-SIM-08 | pasa | `test_SAVI02_bucle_nombra_las_transiciones_y_etapas_que_se_repiten` | el motivo de parada nombra con sus nombres visibles las transiciones del bucle y deja el detalle |
| S-AVI03 | REQ-EDT-09 | pasa | `test_SAVI03_motivos_frecuentes_en_lenguaje_llano` | los diagnósticos más frecuentes se muestran sin referencias internas ni jerga. |
| S-AVI04 | REQ-EDT-09 | pasa | `test_SAVI04_aviso_largo_se_parte_en_frase_corta_y_ayuda` | un aviso largo deja una frase corta en la lista y el texto completo para la ayuda emergente. |
| S-CAN | REQ-DAT-05, REQ-DAT-06 | pasa | `test_SCAN_formato_canonico` | reglas de representación canónica y lectura estricta (09). |
| S-CLI01 | REQ-EDT-04, REQ-JER-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SCLI01_jerarquia_completa_y_forzados_remapeados` | copia contenido propio y conserva o remapea destinos. |
| S-CLI02 | REQ-EDT-04, REQ-MOD-03 | pasa | `test_SCLI02_frontera_de_enlaces_se_corta` | solo se conservan los enlaces entre elementos copiados. |
| S-CLI03 | REQ-EDT-04, REQ-MOD-01 | pasa | `test_SCLI03_nombres_unicos_sin_duplicar_variables` | 2 con 1–5 ocupados pasa a 6; G1 y t1 usan el siguiente libre. |
| S-CLI04 | REQ-EDT-04, REQ-EDT-05 | pasa | `test_SCLI04_pegar_se_deshace_y_rehace_en_una_operacion` | la copia no cambia el historial y pegar restaura ambos documentos. |
| S-CLI05 | REQ-DAT-01, REQ-EDT-04 | pasa | `test_SCLI05_otro_proyecto_enlaza_variables_por_nombre_y_rechaza_faltantes` | no usa IDs del proyecto origen ni pega parcialmente si faltan variables. |
| S-CLI06 | REQ-ACT-01, REQ-EDT-04, REQ-JER-02 | pasa | `test_SCLI06_accion_y_orden_copiadas_solas_quedan_sueltas` | copiar solo una caja conserva configuración y rompe su enlace de etapa. |
| S-CLI07 | REQ-EDT-03, REQ-EDT-04 | pasa | `test_SCLI07_barras_rutas_y_notas_conservan_geometria_relativa` | barras, notas y rutas internas viajan con sus referencias y coordenadas. |
| S-CLI08 | REQ-DAT-08, REQ-EDT-04 | pasa | `test_SCLI08_texto_y_significado_apuntan_a_la_etapa_copiada_renombrada` | renombrar la copia actualiza texto, bindings y significado de sus receptividades. |
| S-CLI09 | REQ-EDT-04, REQ-JER-05 | pasa | `test_SCLI09_marco_copiado_sin_su_dueno_es_parcial_independiente` | copiar el marco de un recinto no duplica ni referencia la encapsulante exterior. |
| S-CLI10 | REQ-ACT-01, REQ-EDT-04 | pasa | `test_SCLI10_borradores_agrupados_remapean_grupo_y_variables` | copiar un grupo suelto mantiene orden y expresión sin enlazarlo al original. |
| S-CLI11 | REQ-EDT-04, REQ-JER-03 | pasa | `test_SCLI11_pegar_forzado_no_crea_ciclo_silencioso` | un pegado que haría que una orden fuerce su propio parcial se rechaza atómicamente. |
| S-CLI12 | REQ-EDT-04, REQ-EDT-09 | pasa | `test_SCLI12_decisiones_explicitas_conservan_referencia_pendiente` | se mantiene la API de decisión externa pendiente que diagnostica D-REF. |
| S-CLI13 | REQ-EDT-04, REQ-MOD-03 | pasa | `test_SCLI13_marco_copia_barras_de_su_contenido` | copiar un parcial incluye la barra interior aunque no estuviera seleccionada aparte. |
| S-CLI14 | REQ-EDT-04, REQ-JER-05 | pasa | `test_SCLI14_encapsulante_aun_sin_recintos_conserva_su_tipo` | una encapsulante todavía sin recintos no se transforma en ordinaria al copiar. |
| S-CLQ01 | REQ-EDT-04, REQ-EDT-05, REQ-EDT-13 | pasa | `test_SCLQ01_atajos_copiar_cortar_pegar_y_deshacer` | los atajos reales copian, cortan y pegan en transacciones atómicas. |
| S-CLQ02 | REQ-EDT-03, REQ-EDT-04 | pasa | `test_SCLQ02_teclado_pega_bajo_el_raton_en_el_dibujo` | el cursor sobre el dibujo determina el punto de pegado ajustado a rejilla. |
| S-CLQ03 | REQ-EDT-04, REQ-EDT-07, REQ-EDT-13 | pasa | `test_SCLQ03_texto_y_tabla_no_disparan_el_portapapeles_del_diagrama` | Ctrl+C/X/V respeta el foco de campos y tabla de variables. |
| S-CLQ04 | REQ-EDT-01, REQ-EDT-04 | pasa | `test_SCLQ04_otro_proyecto_conserva_portapapeles_y_exige_variables` | cambiar de proyecto conserva la copia y avisa sin pegar si falta una variable. |
| S-CLQ05 | REQ-EDT-03, REQ-EDT-04, REQ-EDT-05 | pasa | `test_SCLQ05_solape_busca_hueco_mas_cercano_y_permite_arrastrar` | pegar encima busca el hueco más cercano, selecciona y se deshace junto. |
| S-CLQ06 | REQ-EDT-04, REQ-EDT-05 | pasa | `test_SCLQ06_cortar_jerarquia_cancela_o_se_deshace_junto` | cortar un marco consulta el borrado y la cancelación no cambia la copia anterior. |
| S-CLQ07 | REQ-EDT-04, REQ-EDT-13 | pasa | `test_SCLQ07_menus_reales_y_pegar_desactivado_si_vacio` | menú Edición y clic derecho ofrecen las acciones con el estado del portapapeles. |
| S-CLQ08 | REQ-ACT-01, REQ-EDT-04 | pasa | `test_SCLQ08_accion_unida_copiada_sola_se_pega_suelta` | Ctrl+C sobre la caja copia solo la acción, no su etapa ni otras acciones. |
| S-CLQ09 | REQ-ACT-01, REQ-EDT-04 | pasa | `test_SCLQ09_marco_incluye_accion_suelta_y_barra_vacia_interiores` | los elementos sin propietario que están dentro del marco viajan con él. |
| S-CLQ10 | REQ-EDT-04, REQ-MOD-03 | pasa | `test_SCLQ10_clic_derecho_barra_aislada_copia_la_barra_no_otra_seleccion` | el menú de una barra aislada opera sobre ella y nunca sobre una selección anterior. |
| S-CLQ11 | REQ-EDT-03, REQ-EDT-04, REQ-EDT-05 | pasa | `test_SCLQ11_grupo_pega_cerca_con_disposicion_y_un_solo_deshacer` | la búsqueda desplaza todo el fragmento sin alterar sus posiciones relativas. |
| S-CMP01 | REQ-NOR-02, REQ-SEM-09 | pasa | `test_SCMP01_catalogo_coherente` | cada lectura del comparador existe en el perfil, tiene su texto y se comprueba. |
| S-CMP02 | REQ-ACT-02, REQ-EVT-03, REQ-SEM-01, REQ-SEM-09, REQ-TMP-03 | pasa | `test_SCMP02_cada_lectura_hace_lo_que_anuncia` | cada alternativa evoluciona como dice su panel. |
| S-CMP03 | REQ-SEM-09 | pasa | `test_SCMP03_las_lecturas_se_distinguen` | en cada ejemplo, las lecturas no acaban todas igual (si no, el ejemplo no sirve para elegir). |
| S-CMP04 | REQ-DAT-02, REQ-NOR-02 | pasa | `test_SCMP04_registro_de_decisiones` | la respuesta se guarda con su origen; los bloques 1 y 2 vienen de la hoja 08. |
| S-CMP05 | REQ-NOR-02, REQ-SEM-09 | pasa | `test_SCMP05_lecturas_por_defecto_son_las_respuestas_incorporadas` | las respuestas incorporadas (hoja 08 y comparador) son las lecturas por defecto; lo abierto se detiene. |
| S-COL01 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SCOL01_vista_valora_referencias_comparacion_temporal_y_constantes_sin_mutar` | verdad de cada nodo con el entorno del motor, sin alterar estado, tiempos ni traza. |
| S-COL02 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SCOL02_qt_colorea_toda_comparacion_temporal_y_acciones_solo_en_simulacion` | operandos, operadores y duración verdaderos en azul eléctrico; edición y falso conservan su color. |
| S-COL03 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SCOL03_activo_azul_electrico_y_seleccion_azul` | etapa y acción activas en azul eléctrico; selección independiente azul. |
| S-COL04 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SCOL04_parcial_y_recinto_rotulos_izquierdos_y_zona_de_nombre` | ambos rótulos alineados a 30 px; nombre inferior del parcial mantiene su zona de arrastre. |
| S-COL05 | REQ-SIM-03 | pasa | `test_SCOL05_norm_sin_clave_compatible_y_constante_numerica_no_booleana` | norm conserva sus segmentos históricos; el 1 numérico no recibe verdad booleana. |
| S-COL06 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SCOL06_web_y_qt_mismos_segmentos_y_azul_electrico_para_actividad_y_verdad` | JS ejecutado colorea los mismos segmentos que Qt y usa el mismo azul eléctrico para actividad y verdad. |
| S-COL07 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SCOL07_limite_temporal_de_accion_refleja_su_duracion_sin_cambiar_el_motor` | el límite dibujado como negación se resalta mientras la condición negada es verdadera. |
| S-COL08 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SCOL08_negadas_en_receptividad_condicion_y_evento_segun_valor_de_negacion` | NOT p y NOT X se resaltan cuando la negación es verdadera, tanto texto como barra. |
| S-COR01 | REQ-EDT-04 | pasa | `test_SCOR01_copiar_continua_sola_conserva_tipo` | una continua copiada sola no adquiere una condición literal. |
| S-COR02 | REQ-SIM-03 | pasa | `test_SCOR02_bloques_sin_huecos_y_limites` | bloques contiguos limitados, sin escribir canales no asignados. |
| S-COR03 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SCOR03_lectura_completa_en_bloque` | una lectura por bloque; una respuesta incompleta no se publica. |
| S-COR04 | REQ-SIM-03 | pasa | `test_SCOR04_flanco_colorea_su_operando_segun_evento` | todo el texto de un flanco usa su valor, no el nivel de la variable. |
| S-COR05 | REQ-ACT-01, REQ-EDT-02, REQ-EDT-05 | pasa | `test_SCOR05_arrastre_real_crea_continua_deshacer` | arrastre derecho crea una continua en una operación. |
| S-COR06 | REQ-EDT-04 | pasa | `test_SCOR06_accion_sola_y_etapa_con_accion` | selección de acción distinta de seleccionar la etapa con su acción. |
| S-COR07 | REQ-EDT-02 | pasa | `test_SCOR07_selector_no_se_comprime_por_el_estilo` | el estilo general no comprime el selector dibujado como una acción. |
| S-COR08 | REQ-SIM-03 | pasa | `test_SCOR08_color_flanco_en_qt` | un nivel verdadero sin flanco conserva el color normal. |
| S-COR09 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SCOR09_retorno_no_atraviesa_acciones_y_js_usa_la_misma_ruta` | carril de retorno fuera de las cajas, compartido por Qt y JS. |
| S-COR10 | REQ-SIM-03 | pasa | `test_SCOR10_escritura_tcp_conjunta_sin_estado_intermedio` | dos actuadores activos se publican juntos, sin pulsos entre peticiones. |
| S-CTL01 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SCTL01_play_stop_muestran_texto_icono_y_conservan_su_comportamiento` | Play inicia y Stop deja todo sin estado; solo cambian los rótulos e iconos. |
| S-CTL02 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SCTL02_operaciones_internas_stop_y_reiniciar_vuelven_al_grafcet` | operaciones internas de Stop/Reiniciar usan el cambio central; la interfaz E/S las deshabilita. |
| S-DBR01 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR01_borrar_las_dos_transiciones_de_la_barra_incluye_el_borrador` | plan y borrado retiran la conexión dependiente completa. |
| S-DBR02 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR02_borrar_un_extremo_preserva_borradores_ajenos` | cualquiera de los extremos arrastra solo sus enlaces. |
| S-DBR03 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR03_keep_dangling_conserva_referencias_ordinarias` | conservar referencias ordinarias no conserva conexiones fantasma. |
| S-DBR04 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR04_borrar_el_borrador_conserva_sus_extremos` | se puede borrar solo la conexión no ejecutable. |
| S-DBR05 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR05_desunir_o_borrar_barra_elimina_solo_sus_parejas` | barra y enlaces cambian juntos y el historial los recupera. |
| S-DBR06 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SDBR06_borrar_extremo_y_despues_la_barra_no_deja_huerfanos` | borrar etapas o transiciones limpia también los extremos de la barra. |
| S-DBR07 | REQ-EDT-05, REQ-JER-07 | pasa | `test_SDBR07_borrar_jerarquia_arrastra_borradores_interiores_y_exteriores` | los borradores siguen el alcance transitivo del borrado. |
| S-DBR08 | REQ-DAT-01, REQ-EDT-01 | pasa | `test_SDBR08_sanea_solo_enlaces_con_un_extremo_ausente_y_marca_dirty` | la reparación conserva entidades, vista y borradores editables. |
| S-DBR09 | REQ-EDT-01, REQ-EDT-02 | pasa | `test_SDBR09_modelo_sin_huerfanos_no_necesita_reparacion` | abrir un borrador editable no lo elimina ni pide guardarlo. |
| S-DBR10 | REQ-EDT-05, REQ-EDT-09 | pasa | `test_SDBR10_reparacion_no_se_repite_al_validar_ni_deshacer` | validar no cambia el documento ni el historial de reparación. |
| S-DBR11 | REQ-DAT-02, REQ-EDT-01, REQ-EDT-09 | pasa | `test_SDBR11_fixture_real_elimina_fantasma_sin_perder_el_modelo` | Salto-de-etapas se abre reparado desde la fixture. |
| S-DBR12 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SDBR12_guardar_y_reabrir_conserva_reparacion_sin_nuevo_aviso` | guardar la reparación permite reabrir sin enlaces fantasma. |
| S-DBR13 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SDBR13_apertura_conserva_otras_referencias_incompletas` | la limpieza de borradores no oculta otros errores de referencia. |
| S-DEC | REQ-EXP-01, REQ-TMP-01 | pasa | `test_SDEC_decimales_y_enteros_exactos` | sin redondeo silencioso ni desbordamiento. |
| S-DECL | REQ-ALC-03, REQ-NOR-01, REQ-NOR-02 | pasa | `test_SDECL_declaracion_sin_conformidad` | la declaración excluye U críticas y no afirma conformidad. |
| S-DRF01 | REQ-EDT-05, REQ-EDT-09 | pasa | `test_SDRF01_referencia_borrada_conserva_nombre_y_bloqueo` | borrar una etapa referenciada conserva X1 en la vista, el significado inválido y deshacer. |
| S-DRF02 | REQ-EDT-03 | pasa | `test_SDRF02_disposicion_automatica_usa_60_sin_cambiar_modelo` | el dibujo automático deja 60 entre etapa y transición, 120 entre etapas; no cambia el modelo. |
| S-DRF03 | REQ-EDT-03, REQ-EDT-05 | pasa | `test_SDRF03_anadir_automatico_y_equidistanciar_comparten_60_y_deshacer` | Ctrl+Intro añade a 60 y equidistanciar usa el mismo paso en una operación reversible. |
| S-DRF04 | REQ-DAT-02, REQ-EDT-05, REQ-EDT-09 | pasa | `test_SDRF04_supr_no_expone_ids_en_qt_js_ni_tras_reabrir` | Supr conserva subíndices legibles, bloquea Play y se guarda/abre sin IDs visibles. |
| S-EDI01 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI01_parcial_raiz_etiquetas_y_agrupar` | el grafcet nuevo tiene el parcial raíz «g»; las etiquetas nuevas son 0, 1… (solo el |
| S-EDI02 | REQ-EDT-09 | pasa | `test_SEDI02_comprobar_receptividad_sin_cambiar_el_modelo` | un texto mal escrito se diagnostica sin tocar el modelo; las variables que faltan se listan. |
| S-EDI03 | REQ-EDT-01, REQ-EDT-02, REQ-EDT-14 | pasa | `test_SEDI03_crear_enlazar_y_simular` | E0 (inicial) → t1 «marcha» → E1 → t2 «paro» → E0 se crea con el ratón, |
| S-EDI04 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SEDI04_guardar_abrir_y_simular` | el grafcet creado se guarda como proyecto, se abre y simula igual; en Editar se |
| S-EDI05 | REQ-EDT-01, REQ-EDT-05 | pasa | `test_SEDI05_deshacer_rehacer_mover_y_borrar` | un arrastre es una sola operación de deshacer; borrar avisa de lo que arrastra y se |
| S-EDI06 | REQ-EDT-09 | pasa | `test_SEDI06_receptividad_mal_escrita_y_diagnosticos` | una receptividad que no se interpreta se conserva como texto, se diagnostica con su corrección, |
| S-EDI07 | REQ-MOD-03 | pasa | `test_SEDI07_enlaces_en_borrador_y_añadir_debajo` | dos elementos del mismo tipo quedan como borrador con su diagnóstico; «añadir debajo» crea |
| S-EDI08 | REQ-EDT-01, REQ-EDT-06 | pasa | `test_SEDI08_etiquetas_y_cambios_sin_guardar` | renombrar una etapa conserva su identidad y actualiza el dibujo; con cambios sin |
| S-EDI10 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI10_el_ratón_real_y_el_dibujo` | los clics del ratón sobre el dibujo llegan al editor; la selección y las marcas se |
| S-EDI100 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI100_limitada_con_condicion_a_medias_pasa_a_borrador` | la condición a medias (con huecos) de una limitada de un fichero antiguo la deja como |
| S-EDI101 | REQ-EDT-02 | pasa | `test_SEDI101_renombrar_con_la_seleccion_cambiada_no_hace_nada` | un editingFinished que llega tarde (la selección cambió, o el elemento ya no existe, por ejemplo tras |
| S-EDI102 | REQ-ACT-01, REQ-EDT-05 | pasa | `test_SEDI102_borrar_una_etapa_borra_sus_acciones_y_se_restaura` | borrar una etapa borra también sus acciones (del modelo y los borradores unidos); la |
| S-EDI103 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI103_botones_nueva_entrada_salida_memoria` | la tabla de variables tiene «+ Entrada», «+ Salida» y «+ Memoria» (tooltips Nueva entrada, |
| S-EDI104 | REQ-ACT-01, REQ-EDT-07 | pasa | `test_SEDI104_panel_de_acciones_lista_de_variables_sin_crear_desde_aqui` | la variable se elige en una lista ordenada por papel (Salidas, Memorias) con su tipo; nunca |
| S-EDI105 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI105_programador_de_valor_de_una_accion_memorizada` | el valor de una memorizada se programa en el panel de la acción: una booleana elige entre las fichas |
| S-EDI106 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI106_frase_explicativa_y_condicion_con_bloques_al_lado` | arriba del panel de la acción, una frase la explica según su tipo; la condición (o el |
| S-EDI107 | REQ-DAT-01, REQ-EDT-14 | pasa | `test_SEDI107_comentarios_en_la_presentacion_guardar_deshacer_y_borrar` | el comentario de una etapa o transición se guarda en `presentation.notes` |
| S-EDI108 | REQ-EDT-14 | pasa | `test_SEDI108_campo_comentario_en_las_propiedades` | el panel de propiedades de la etapa y de la transición tiene el campo «Comentario»: confirmarlo es una |
| S-EDI109 | REQ-EDT-14, REQ-SIM-03 | pasa | `test_SEDI109_dibujo_de_los_comentarios_sin_solapes` | el comentario se dibuja entre comillas tipográficas, en cursiva: el de una transición a la |
| S-EDI11 | REQ-EDT-02 | pasa | `test_SEDI11_puntos_de_union` | etapas y transiciones tienen puntos de unión arriba y abajo; al acercarse se marcan y del punto |
| S-EDI111 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI111_paleta_de_bloques_una_ficha_por_elemento` | en Entradas, Salidas, Etapas, Memorias (y Variables del valor) hay una ficha por cada |
| S-EDI112 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI112_panel_de_opciones_etapa_transicion_y_encaje_a_1360x860` | el panel de opciones de abajo muestra, de una etapa, etiqueta, tipo, comentario y |
| S-EDI113 | REQ-SIM-03 | pasa | `test_SEDI113_traza_en_simular_y_leyenda_en_ayuda` | al simular la traza queda oculta y puede desplegarse y plegarse con su flecha; la leyenda es |
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
| S-EDI158 | REQ-EDT-04, REQ-MOD-07 | pasa | `test_SEDI158_pegar_conserva_jerarquia_y_destino_externo` | copiar macroetapa y encapsulante incluye sus contenidos y conserva el destino externo. |
| S-EDI16 | REQ-EDT-02 | pasa | `test_SEDI16_notacion_del_usuario` | ↑a, ↓a y X1 se traducen a la sintaxis del núcleo y vuelven; los espacios se ignoran al escribir y |
| S-EDI17 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI17_barra_de_simultaneidad` | la simultaneidad es una barra de doble trazo que se arrastra desde la paleta, se |
| S-EDI170 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI170_fichas_macroetapa_y_encapsulante_con_su_dibujo_y_su_ayuda` | la paleta ofrece «Macroetapa» y «Encapsulante» tras las demás fichas; su icono |
| S-EDI171 | REQ-EDT-02, REQ-EDT-05, REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI171_soltar_la_ficha_macroetapa_crea_la_macroetapa_con_su_expansion` | soltar «Macroetapa» crea la macroetapa en el punto, con su |
| S-EDI172 | REQ-EDT-02, REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI172_lo_soltado_en_el_marco_de_la_expansion_es_de_su_parcial` | lo que se suelta dentro de la zona de una expansión (etapa, encapsulante, |
| S-EDI173 | REQ-JER-04, REQ-MOD-07 | pasa | `test_SEDI173_una_macroetapa_soltada_en_una_expansion_o_un_recinto_queda_anidada` | una macroetapa soltada dentro de la zona de otra expansión, o en el marco de un recinto, es de |
| S-EDI174 | REQ-EDT-02, REQ-EDT-05, REQ-EDT-09, REQ-JER-05, REQ-MOD-07 | pasa | `test_SEDI174_recinto_vacio_se_ve_se_selecciona_y_se_rellena_arrastrando` | «Añadir recinto…» pide el nombre y crea el recinto de la |
| S-EDI175 | REQ-EDT-09, REQ-JER-05 | pasa | `test_SEDI175_convertir_en_encapsulante_y_volver_a_etapa_ordinaria` | el botón derecho en una etapa ofrece «Tipo de etapa» (Etapa, Encapsulante, |
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
| S-EDI200 | REQ-EDT-02 | pasa | `test_SEDI200_la_barra_del_negado_es_una_linea_de_1_25_px_sobre_la_palabra` | la barra de una variable negada es una línea propia de 1,25 px (el sobrerrayado del texto es de 1 px y |
| S-EDI201 | REQ-EDT-02 | pasa | `test_SEDI201_la_barra_cubre_cada_tramo_negado_en_receptividades_condiciones_y_eventos` | un tramo de segmentos negados seguidos (NOT (p AND q), NOT X(A) con su subíndice) lleva una sola |
| S-EDI202 | REQ-EDT-02 | pasa | `test_SEDI202_la_barra_no_cambia_anchos_ni_disposicion` | la barra no cambia lo que mide un texto ni dónde caen las cajas de las acciones (la disposición no |
| S-EDI203 | REQ-EDT-02 | pasa | `test_SEDI203_dibujo_js_y_css_pintan_la_misma_barra` | el banco web (tools/dibujo.js y dibujo.css) pinta la barra del negado como una línea propia de 1,25 px, |
| S-EDI204 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SEDI204_el_estado_del_temporizador_es_solo_lo_transcurrido` | antes de empezar no hay nada que mostrar; mientras cuenta, solo el tiempo transcurrido |
| S-EDI205 | REQ-TMP-01 | pasa | `test_SEDI205_dos_temporizadores_de_la_misma_duracion_se_distinguen_por_su_orden` | «3s/p OR 3s/q/2s»: cada temporizador apunta a su propia aparición de «3s» en el texto; el de |
| S-EDI206 | REQ-TMP-01 | pasa | `test_SEDI206_las_acciones_con_retardo_se_marcan_en_el_modelo_sin_depender_del_estado` | la acción con un retardo en su condición o su evento lleva `tmr` (para reservarle sitio arriba); la |
| S-EDI207 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SEDI207_el_tiempo_transcurrido_va_alineado_encima_de_la_duracion` | en la receptividad «ok·3s/XB» el «1,00 s» se alinea con el inicio del «3s», justo |
| S-EDI208 | REQ-SIM-03 | pasa | `test_SEDI208_si_no_se_localiza_la_duracion_se_alinea_con_toda_la_receptividad` | un temporizador cuya duración no está en el texto (token desconocido) se alinea al inicio de toda la |
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
| S-EDI22 | REQ-SIM-03 | pasa | `test_SEDI22_ejemplo_alternativas` | un proyecto de prueba de alternativas se simula y se edita conservando las flechas de unión. |
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
| S-EDI257 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI257_secciones_y_fichas_accesibles_a_1366x768` | secciones legibles; todas las fichas accesibles con desplazamiento a 1366×768. |
| S-EDI258 | REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-MOD-03, REQ-SIM-03 | pasa | `test_SEDI258_una_transicion_unida_con_el_raton_a_una_barra_activa_todo_lo_de_debajo_en_cualquier_parcial` | con los gestos del editor (arrastrar de punto de unión a |
| S-EDI259 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SEDI259_la_barra_con_una_etapa_y_una_transicion_por_encima_no_pierde_los_enlaces_de_la_transicion` | con una etapa y una transición por encima de la misma barra (y varias etapas debajo), unidas |
| S-EDI26 | REQ-MOD-03 | pasa | `test_SEDI26_geometria_comun_retorno_y_movimiento` | uniones comunes, retorno fuera de la etapa, flecha automática y recorridos iguales en Qt/web. |
| S-EDI260 | REQ-EDT-07 | pasa | `test_SEDI260_supr_quita_la_variable_seleccionada_como_el_boton` | Supr con una fila seleccionada en la tabla de variables la quita directamente, por el mismo camino que |
| S-EDI261 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SEDI261_supr_de_una_variable_en_uso_se_rechaza_igual_que_quitar` | si el núcleo no deja quitar la variable (se usa), Supr enseña el mismo motivo que el |
| S-EDI262 | REQ-EDT-07 | pasa | `test_SEDI262_supr_con_la_celda_en_edicion_es_del_editor_y_no_borra_el_dibujo` | con el editor de una celda abierto Supr borra texto, no la fila; con la tabla enfocada Supr es de la |
| S-EDI263 | REQ-EDT-07 | pasa | `test_SEDI263_supr_con_varias_filas_y_filas_sin_nombre` | con varias filas seleccionadas Supr las quita todas (una operación de deshacer por variable); si el |
| S-EDI264 | REQ-EDT-07 | pasa | `test_SEDI264_supr_solo_actua_al_editar` | fuera del modo edición (en Play) la tabla de variables no responde a Supr; al volver a Pausa, sí. |
| S-EDI265 | REQ-EDT-11, REQ-SIM-03 | pasa | `test_SEDI265_pestanas_entre_grafcet_planos_y_es_externas` | las tres pestañas identifican la página y se sincronizan por cualquier vía. |
| S-EDI266 | REQ-SIM-03 | pasa | `test_SEDI266_el_estado_de_conexion_hace_salto_de_linea_y_no_se_corta` | el estado de la conexión del panel de E/S ocupa su propia fila bajo el título, hace salto de línea y |
| S-EDI267 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI267_la_paleta_se_encoge_en_ventanas_bajas_sin_subir_el_minimo_de_alto_de_la_ventana` | en ambos tamaños las fichas se alcanzan con scroll, sin aumentar el mínimo de ventana. |
| S-EDI268 | REQ-EDT-07 | pasa | `test_SEDI268_supr_del_teclado_numerico_tambien_quita_la_variable` | el Supr del teclado numérico (con el modificador de teclado numérico) actúa igual que el Supr normal en la |
| S-EDI269 | REQ-SIM-03 | pasa | `test_SEDI269_un_clic_con_temblor_no_deja_la_vista_manual_y_el_arrastre_empieza_pasada_la_distancia` | al simular, un clic en el que el ratón se mueve menos que la distancia de arrastre del sistema (el temblor |
| S-EDI27 | REQ-SIM-03 | pasa | `test_SEDI27_ejemplos_seleccion_salto_repeticion` | las ramas construidas ejecutan selección, salto y repetición sin cambiar el motor. |
| S-EDI270 | REQ-SIM-03 | pasa | `test_SEDI270_las_pestanas_no_se_mueven_al_cambiar_de_vista` | las pestañas tienen textos y geometría estables al cambiar entre los tres espacios. |
| S-EDI271 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI271_centrar_todo_dice_su_atajo_y_el_doble_clic_de_la_simulacion` | la ayuda del botón «Centrar todo» cita Ctrl+0 y, al simular, el doble clic (que también |
| S-EDI272 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SEDI272_el_divisor_movido_a_mano_se_respeta_aunque_la_paleta_no_quepa_entera` | la paleta solo gana su alto completo mientras el divisor entre el dibujo y el panel inferior |
| S-EDI273 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI273_la_leyenda_dice_que_los_trazos_de_dependencia_solo_se_ven_con_el_boton_y_no_habla_de_la_navegacion_antigua` | la leyenda de la ventana ya no dice que la macroetapa va unida a su expansión por |
| S-EDI274 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI274_el_nombre_de_la_encapsulante_va_a_caballo_del_trazo_superior_de_su_recinto_sobre_su_fondo` | el nombre de la encapsulante se escribe a la izquierda sobre el marco de su recinto, con su línea |
| S-EDI275 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SEDI275_dibujo_js_coloca_el_nombre_de_la_encapsulante_igual_que_escritorio` | tools/dibujo.js escribe el nombre de la encapsulante a caballo del trazo de arriba (línea base 5 |
| S-EDI276 | REQ-EDT-02 | pasa | `test_SEDI276_centrar_todo_deja_a_la_vista_el_nombre_y_el_marco_no_depende_de_el` | el nombre sobresale la mitad del marco, así que la caja del dibujo lo incluye y «Centrar todo» lo deja a la |
| S-EDI28 | REQ-EDT-01, REQ-EDT-02 | pasa | `test_SEDI28_salto_inverso_guardar_y_reabrir` | arrastrar la entrada de una etapa a una salida crea el salto; persiste y se deshace entero. |
| S-EDI280 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI280_la_ficha_grafcet_parcial_es_una_ficha_mas_de_la_paleta` | la paleta ofrece «Grafcet parcial» (marco redondeado con «G») antes de «Forzado», con su |
| S-EDI281 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI281_soltar_la_ficha_en_un_hueco_crea_un_parcial_vacio_con_nombre_unico_y_su_marco` | soltar «Grafcet parcial» en un hueco crea, en una sola operación de deshacer, un |
| S-EDI282 | REQ-EDT-02, REQ-EDT-05, REQ-JER-02 | pasa | `test_SEDI282_el_marco_vacio_se_selecciona_se_mueve_se_rellena_y_se_renombra` | el marco vacío de un parcial suelto se agarra por su borde (dentro no hay nada que |
| S-EDI283 | REQ-DAT-01, REQ-EDT-01, REQ-EDT-02 | pasa | `test_SEDI283_un_parcial_suelto_sin_etapas_sobrevive_a_guardar_y_abrir_con_su_marco_en_su_sitio` | dos parciales sueltos sin etapas se guardan y se abren (formato actual, sin |
| S-EDI284 | REQ-EDT-05, REQ-JER-02, REQ-JER-03, REQ-SIM-03 | pasa | `test_SEDI284_un_parcial_suelto_es_destino_de_la_ficha_forzado_y_se_borra_con_aviso_y_un_deshacer` | un parcial suelto sale en el diálogo de la ficha «Forzado» (con sus |
| S-EDI285 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SEDI285_el_menu_del_hueco_omite_creacion_redundante_con_paleta` | el botón derecho en un hueco ofrece «Nuevo grafcet parcial aquí» (lo mismo que soltar la |
| S-EDI286 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI286_por_defecto_no_hay_trazos_de_dependencia_y_con_la_opcion_aparecen_los_de_macroetapa_y_encapsulante` | sin la opción (por defecto) no se dibuja ningún trazo discontinuo de dependencia; |
| S-EDI287 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SEDI287_mostrar_u_ocultar_las_dependencias_no_cambia_la_disposicion_los_marcos_ni_la_seleccion` | lo único que cambia al mostrar las dependencias son sus trazos: el resto de lo |
| S-EDI288 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SEDI288_el_boton_mostrar_dependencias_de_la_vista_conmuta_repinta_y_se_recuerda` | la vista tiene el botón conmutable «Mostrar dependencias» tras los controles del zoom, apagado |
| S-EDI289 | REQ-EDT-08, REQ-JER-07, REQ-SIM-03 | pasa | `test_SEDI289_encuadrar_encaja_y_centra_un_rectangulo_con_margen_y_el_tope_de_centrar_todo` | `encuadrar(r)` encaja y centra en la vista el rectángulo de escena `r` con el mismo |
| S-EDI29 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SEDI29_flecha_arrastrar_y_ocultar_sin_cambiar_modelo` | mover y ocultar la flecha son presentación; un arrastre, un deshacer. La flecha sigue |
| S-EDI290 | REQ-EDT-02, REQ-JER-04, REQ-JER-05, REQ-SIM-03 | pasa | `test_SEDI290_dependencias_en_barra_en_edicion_y_simulacion_y_se_recuerda` | «Mostrar dependencias» es un botón conmutable junto a los controles del |
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
| S-EDI64 | REQ-EDT-02 | pasa | `test_SEDI64_categorias_horizontales_y_bloques_en_columna` | categorías en una franja horizontal (las ocho, con su color), debajo la columna de |
| S-EDI65 | REQ-EDT-02 | pasa | `test_SEDI65_arrastre_de_las_paletas` | la paleta «Elementos» se arrastra (el arrastre se activa después de fijar el modo de iconos y el |
| S-EDI66 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SEDI66_variables_nuevas_al_dia_en_el_programador` | al crear, renombrar, quitar o cambiar de papel una variable (panel Variables, panel de |
| S-EDI67 | REQ-EDT-02 | pasa | `test_SEDI67_carpetas_en_su_orden_y_temporizadores` | las carpetas del programador van en este orden: Entradas, Etapas (X), Memorias, Operadores, |
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
| S-EDI88 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SEDI88_paleta_por_secciones_y_cinco_fichas_de_accion` | la paleta es una sola lista, sin carpetas, con etapa, transición, simultaneidad, una |
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
| S-ESP01 | REQ-SIM-03 | pasa | `test_SESP01_sin_proyecto_ni_preferencias_usa_el_del_simulador` | sin configuración propia ni recordada se proponen servidor y cantidades iniciales de conexión. |
| S-ESP02 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SESP02_recordado_incluye_canales_y_escalas_sin_asignaciones` | un proyecto sin mapa usa la conexión y los tiempos recordados (no las cantidades de canales, |
| S-ESP03 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SESP03_json_del_proyecto_manda_sobre_preferencias` | servidor, cantidades y escala del proyecto tienen prioridad sobre la última configuración. |
| S-ESP04 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SESP04_primera_guarda_adjunta_mapa_y_viaja_con_el_proyecto` | la primera guarda de proyecto incluye la conexión y la copia transportada conserva sus ajustes. |
| S-ESP05 | REQ-SIM-03 | pasa | `test_SESP05_preferencias_anteriores_validas_no_se_sustituyen_silenciosamente` | una dirección previamente recordada manda sobre el valor inicial y se identifica su procedencia. |
| S-ESP06 | REQ-SIM-03 | pasa | `test_SESP06_filas_iguales_y_registros_alineados_con_cantidades_distintas` | sensores, canales y actuadores usan la misma altura; los registros comienzan en la misma horizontal. |
| S-ESP07 | REQ-SIM-03 | pasa | `test_SESP07_led_activo_saturado_e_inactivo_neutro` | la señal activa tiene color saturado y la inactiva es neutra en lista y canal. |
| S-ESP08 | REQ-SIM-03 | pasa | `test_SESP08_cabecera_colorea_todos_los_estados_sin_perder_texto` | estado inicial neutro, estable verde, fallo y desconexión con el fondo original, con mensaje conservado. |
| S-ESP09 | REQ-SIM-03 | pasa | `test_SESP09_no_hay_controles_del_bloque_inferior_ni_prueba_guiada` | la configuración no ofrece Aplicar, cargar/guardar archivos, probar, guía ni Cerrar inferior. |
| S-ESP10 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SESP10_asignar_y_editar_configuracion_aplican_sin_boton` | arrastrar/asignar y terminar la edición de un campo aplican el mapa sin botón adicional. |
| S-ESP11 | REQ-DAT-02, REQ-ROB-01 | pasa | `test_SESP11_mapa_invalido_avisa_sin_sobrescribir_el_archivo` | una configuración guardada inválida se señala y el original no se sobrescribe al abrir. |
| S-ESP12 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SESP12_preferencias_invalidas_vuelven_a_valores_validos` | preferencias corruptas no dejan una propuesta inválida ni alteran las guardadas. |
| S-ESP13 | REQ-DAT-02, REQ-SIM-04 | pasa | `test_SESP13_guardar_no_altera_el_mapa_de_una_conexion_viva` | guardar depura una copia para el proyecto sin cambiar los controles ni el mapa en uso. |
| S-ESP14 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SESP14_capacidad_a_1366_y_panel_usable_a_1000` | los 20+10 canales por lado caben sin scroll a 1366×768 y la vista pequeña conserva acceso. |
| S-ETI01 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SETI01_transicion_nueva_oculta_en_la_misma_operacion_deshacer` | la transición colocada nace sin etiqueta visible y se deshace en una operación. |
| S-ETI02 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SETI02_opcion_desmarcada_y_etiqueta_oculta_al_colocar` | la ficha crea una transición oculta; el clic en Mostrar etiqueta la activa y se puede deshacer. |
| S-ETI03 | REQ-DAT-02, REQ-EDT-02 | pasa | `test_SETI03_guardar_y_abrir_conserva_una_visible_y_otra_oculta` | el nuevo valor inicial no cambia la elección ya guardada en un proyecto. |
| S-EXP | REQ-EXP-01 | pasa | `test_SEXP_comparacion_encadenada_y_tipos` | comparaciones encadenadas rechazadas; sin conversión booleano↔número. |
| S-FBR01 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SFBR01_forzado_suelto_bloquea_play_y_parpadea_su_caja` | la orden suelta sin configurar impide Play, se nombra y parpadea. |
| S-FBR02 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SFBR02_forzado_unido_incompleto_y_completo` | faltan destino, forma o etapas; completar elimina el bloqueo y permite Play. |
| S-FBR03 | REQ-ACT-01, REQ-EDT-09 | pasa | `test_SFBR03_accion_normal_suelta_bloquea_y_al_completar_se_puede_simular` | la acción normal suelta bloquea Play; unirla y completarla retira el error. |
| S-FBR04 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SFBR04_accion_normal_unida_incompleta_bloquea_y_parpadea` | la acción normal unida sin variable también bloquea Play con nombre y parpadeo. |
| S-FBR05 | REQ-DAT-01, REQ-EDT-09 | pasa | `test_SFBR05_guardar_y_abrir_conserva_bloqueos_de_borradores` | el proyecto conserva las órdenes y acciones sueltas y sus bloqueos al abrir. |
| S-FBR06 | REQ-EDT-01, REQ-EDT-09 | pasa | `test_SFBR06_abrir_fixture_limpia_y_avisa_una_vez` | abrir el proyecto real retira el enlace huérfano y avisa una vez. |
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
| S-FIO26 | REQ-DAT-02 | pasa | `test_SFIO26_escala_factoryio_100_por_defecto_y_personalizable` | entradas/salidas numéricas usan 100 por defecto y respetan las escalas guardadas. |
| S-FIO27 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO27_la_conexion_sobrevive_a_play_pausa_edicion_reinicio_y_abrir` | una vez conectado, ni Play, Pausa, editar, Reiniciar ni abrir otro ejemplo cierran |
| S-FIO28 | REQ-SIM-03 | pasa | `test_SFIO28_borrar_variable_asignada_depura_mapa_sin_impedir_play` | borrar una salida asignada solicita su cero, conserva TCP y permite Play con el mapa depurado. |
| S-FIO29 | REQ-SEM-07, REQ-SIM-02 | pasa | `test_SFIO29_inestable_con_modbus_avisa_pausa_y_pone_salidas_a_cero` | un GRAFCET inestable con la planta conectada se detiene (Pausa/edición), avisa una sola |
| S-FIO30 | REQ-SIM-02, REQ-SIM-04 | pasa | `test_SFIO30_pausar_vincular_y_observar_sin_cerrar_tcp` | Pausa conserva TCP, sigue leyendo las entradas y pone a cero todas las salidas asignadas; |
| S-FIO30 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO30_play_inmediato_tras_reiniciar_en_pausa_no_vuelve_a_pausa` | Pausa, Reiniciar en Pausa (que solo vuelve a pedir el cero) y Play inmediato, antes de que |
| S-FIO31 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO31_abrir_otro_proyecto_pone_a_cero_aunque_la_escritura_siguiera_en_vuelo` | Play y Pausa con una escritura de salidas en vuelo descartan su respuesta |
| S-FIO32 | REQ-SIM-03 | pasa | `test_SFIO32_cerrar_la_ventana_cierra_el_tcp` | cerrar la ventana con la conexión viva cierra el TCP (no queda el socket abierto contra la planta). |
| S-FIO33 | REQ-SIM-03 | pasa | `test_SFIO33_marco_con_canales_y_nombres_fuera` | la vista autómata tiene la cabecera «(IP:puerto) Esclavo ID:n», Entrada e Entrada numérica a la izquierda, |
| S-FIO34 | REQ-SIM-03 | pasa | `test_SFIO34_color_de_tipo_y_viveza_del_indicador` | la barrita de cada canal es tenue si no está asignado, del color del tipo (Bool verde, Decimal azul, |
| S-FIO35 | REQ-SIM-03 | pasa | `test_SFIO35_arrastre_resalta_solo_lateral_y_la_x_aparece_al_pasar_el_raton` | al arrastrar una variable sobre un canal se resalta el lateral exterior al PLC (nombre incluido); soltar asigna; |
| S-FIO36 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO36_errores_de_red_habituales_con_frase_legible` | los fallos de socket habituales (WinError 10053, 10054, 10061, reinicio, tubería rota, |
| S-FIO37 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO37_variables_nuevas_del_editor_aparecen_en_es_y_se_pueden_asignar` | cada vez que se muestra E/S externas, sus listas y canales reflejan las variables actuales |
| S-FIO38 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO38_cambiar_tipo_o_papel_de_una_asignada_la_quita_con_aviso_sin_romper_el_panel` | si una variable asignada cambia de tipo o de papel y ya no casa con su área, se quita del |
| S-FIO39 | REQ-SIM-03 | pasa | `test_SFIO39_con_el_panel_a_la_vista_las_variables_nuevas_llegan_sin_salir_y_se_conserva_lo_escrito` | con la vista de E/S abierta (la tabla de variables sigue accesible) una variable nueva aparece al |
| S-FIO40 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SFIO40_conexion_activa_actualiza_variables_y_mapa_sin_reconectar` | altas y asignaciones se publican entre ciclos conservando TCP y canales existentes. |
| S-FIO41 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SFIO41_canales_fijados_a_mano_se_conservan_y_se_avisa_si_un_area_se_queda_sin_canales` | con las cantidades de canal escritas a mano no se inventan canales; si una variable |
| S-FIO42 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO42_camino_de_simulacion_el_panel_sigue_a_las_variables_del_modelo_en_ejecucion` | en Play, E/S externas enseña las variables del modelo que se ejecuta; al volver a Pausa y |
| S-FIO43 | REQ-SIM-03 | pasa | `test_SFIO43_la_primera_vez_el_servidor_propuesto_es_el_del_simulador` | sin nada recordado ni mapa guardado, el panel propone 192.168.1.133, puerto 502 y esclavo 1; no se |
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
| S-FIO57 | REQ-DAT-02 | pasa | `test_SFIO57_cargar_ignora_modo_y_escucha_del_modo_servidor_retirado` | un mapa guardado con `modo` y `escucha` (modo servidor ya retirado) se carga como cliente. |
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
| S-FIO70 | REQ-ROB-01 | pasa | `test_SFIO70_texto_numero_con_coma_espanola` | los números de los mensajes llevan coma decimal y sin ceros de más. |
| S-FIO71 | REQ-EXP-01, REQ-ROB-01 | pasa | `test_SFIO71_entrada_entera_con_decimales_dice_que_variable_y_que_hacer` | una Entera que recibe 1,3 (130 con escala 100) no entra en el motor y el error nombra la |
| S-FIO72 | REQ-EXP-01 | pasa | `test_SFIO72_entrada_decimal_con_mas_decimales_de_los_declarados` | un Decimal de 2 decimales que recibe 1,234 lo dice con el nombre de la variable. |
| S-FIO73 | REQ-EXP-01 | pasa | `test_SFIO73_salida_no_representable_nombra_la_variable` | una salida con más decimales que el registro, o fuera de su rango, lo dice con el nombre. |
| S-FIO74 | REQ-ROB-01 | pasa | `test_SFIO74_muestra_incompleta_y_mensajes_de_red_sin_codigos` | la muestra incompleta y los fallos de red se explican sin códigos ni jerga. |
| S-FIO75 | REQ-ROB-01 | pasa | `test_SFIO75_el_error_de_conversion_llega_al_estado_del_coordinador` | lo que sube hasta el estado es el texto del alumno, no uno genérico ni con «Detalle». |
| S-FIO76 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SFIO76_decimal_se_coloca_solo_igual_que_entera` | Entera y Decimal, entrada o salida, van al primer registro libre; una booleana que pasa a |
| S-FIO77 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SFIO77_aviso_ambar_de_entera_con_escala_distinta_de_uno` | una Entera en un registro con escala 100 lleva un aviso junto a su fila y en la nota; una |
| S-FIO78 | REQ-SIM-03 | pasa | `test_SFIO78_la_linea_de_sondeo_y_ciclo_no_se_ve` | la medida de sondeo y ciclo se conserva (texto y tooltip) pero la línea queda oculta. |
| S-GFN01 | REQ-DAT-01, REQ-DAT-02 | pasa | `test_SGFN01_ida_vuelta_preserva_json_notas_imagenes_y_es` | el contenedor conserva byte a byte todos los documentos y recursos del proyecto. |
| S-GFN02 | REQ-DAT-01 | pasa | `test_SGFN02_fallo_atomico_conserva_archivo_anterior_y_limpia_temporal` | un fallo al sustituir no modifica el archivo anterior ni deja temporales. |
| S-GFN03 | REQ-DAT-01, REQ-DAT-02 | pasa | `test_SGFN03_sello_rechaza_modificado_sin_sello_otra_clave_y_manual` | contenido alterado, sin sello, de otra edición o hecho a mano no se acepta como válido. |
| S-GFN04 | REQ-DAT-02 | pasa | `test_SGFN04_rutas_peligrosas_y_version_no_compatible_se_rechazan` | ni una importación autorizada admite rutas que escapen o una versión desconocida. |
| S-GFN07 | REQ-DAT-02 | pasa | `test_SGFN07_construccion_exige_clave_y_no_deja_modulo_en_repositorio` | sin clave se rechaza repartir; la clave se genera y elimina fuera del árbol de trabajo, incluso al fallar. |
| S-GFN08 | REQ-EDT-01, REQ-EDT-05 | pasa | `test_SGFN08_ctrl_s_guardar_como_y_nombre_con_asterisco` | Ctrl+S crea un archivo, Ctrl+Mayús+S guarda otra copia y el título sigue nombre y cambios. |
| S-GFN10 | REQ-DAT-02, REQ-EDT-05 | pasa | `test_SGFN10_archivo_manipulado_conserva_edicion_actual` | rechazar un archivo manipulado no descarta ni sustituye la edición actual. |
| S-GFN11 | REQ-DAT-01, REQ-DAT-02 | pasa | `test_SGFN11_archivo_conserva_mapa_y_recursos` | el archivo conserva E/S y recursos sin exponer carpetas como formato de proyecto. |
| S-GFN12 | REQ-DAT-02 | pasa | `test_SGFN12_rechaza_carpetas_json_y_otro_sello` | una versión repartible solo admite archivos .grafnet firmados con su propia clave. |
| S-GFN14 | REQ-DAT-01, REQ-EDT-05 | pasa | `test_SGFN14_fallo_al_guardar_no_cambia_destino_ni_dirty` | fallar Guardar como conserva el archivo, el estado anteriores. |
| S-GFN16 | REQ-DAT-02 | pasa | `test_SGFN16_construccion_real_sin_clave_no_invoca_compilador` | la orden de construcción se niega sin clave antes de llamar al empaquetador. |
| S-GFN17 | REQ-DAT-02 | pasa | `test_SGFN17_conversion_conserva_modelos_y_escenarios_adicionales` | abrir y guardar un contenedor conserva todos sus documentos, no solo el modelo editable. |
| S-GFN18 | REQ-DAT-02 | pasa | `test_SGFN18_nuitka_ausente_no_instala_ni_cambia_de_via` | si no hay Nuitka se informa y no se sustituye silenciosamente la construcción elegida. |
| S-GFN19 | REQ-DAT-02 | pasa | `test_SGFN19_acerca_distingue_desarrollo_sin_mostrar_clave` | Acerca de identifica desarrollo sin revelar la clave y la marca no aparece en una versión repartible. |
| S-GFN20 | REQ-DAT-01, REQ-EDT-05 | pasa | `test_SGFN20_extension_y_cancelacion_no_sobrescriben_ni_modifican` | añadir .grafnet respeta un archivo existente y cancelar Guardar como conserva la edición. |
| S-GFN23 | REQ-EDT-09 | pasa | `test_SGFN23_aplicacion_sin_recuperacion_ni_opciones_de_password` | la aplicación no inicia autoguardado ni conserva controles o diálogos de contraseña y recuperación. |
| S-GFN24 | REQ-EDT-01, REQ-EDT-09 | pasa | `test_SGFN24_guardar_como_no_abre_dialogos_adicionales` | elegir el nombre es suficiente para guardar el proyecto, sin un diálogo de protección. |
| S-GFN25 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_SGFN25_no_se_guarda_un_proyecto_como_carpeta` | la interfaz solo escribe proyectos .grafnet y nunca crea la carpeta del formato anterior. |
| S-H05 | REQ-EVT-03, REQ-SEM-05 | pasa | `test_SH05_activar_etapa_ya_activa_no_ejecuta_sus_acciones` | hallazgo H-05, cerrado por el comparador (3.3 A). Con «detener», U-04. |
| S-H07 | REQ-ACT-02, REQ-SEM-01 | pasa | `test_SH07_memoria_inicial_no_nula_no_compila` | hoja 08, 1.5 A (cierra H-07); otro valor inicial se pone al activar la etapa inicial. |
| S-H08 | REQ-JER-01, REQ-MOD-07 | pasa | `test_SH08_parcial_dentro_de_otro` | hallazgo H-08, cerrado por el responsable (8.1 C): sin encapsulante no compila; como recinto, sí. |
| S-H08c | REQ-ACT-02, REQ-JER-01 | pasa | `test_SH08c_etapa_inactiva_de_otro_parcial_no_fuerza_la_salida_a_cero` | decisión del responsable (4-nov-2026), manda la etapa activa. |
| S-H09 | REQ-SEM-06, REQ-TMP-02 | pasa | `test_SH09_reentrada_en_el_mismo_instante_conserva_la_duracion` | P-IMP-18 (cierra H-09); la salida y reentrada sin tiempo no reinicia el retardo. |
| S-H09b | REQ-SEM-07, REQ-TMP-02 | pasa | `test_SH09b_etapa_que_sale_por_su_temporizador_y_reentra_no_se_estabiliza` | consecuencia de P-IMP-18; ciclo instantáneo sin fin, cortado con D-LIM-EVOL (doc. 04). |
| S-H10 | REQ-ACT-01 | pasa | `test_SH10_leer_salida_continua` | hallazgo H-10, cerrado por el comparador (8.2 C): se lee según la situación del momento, también la inestable. |
| S-H12 | REQ-DAT-01, REQ-PLT-02 | pasa | `test_SH12_id_de_documento_y_nombre_de_fichero` | hallazgo H-12. |
| S-IEJ01 | REQ-JER-04, REQ-SIM-01 | pasa | `test_SIEJ01_siete_ejemplos_compilan_con_entradas_y_salidas` | los siete ejemplos tienen entradas, salidas y posiciones, y arrancan sin diagnósticos. |
| S-IEJ02 | REQ-EDT-09 | pasa | `test_SIEJ02_inicio_vacio_paneles_y_cabecera_en_una_fila` | el inicio es un proyecto vacío con laterales abiertos y propiedades plegadas; ayuda junto al título. |
| S-IEJ03 | REQ-EDT-05, REQ-SIM-01 | pasa | `test_SIEJ03_ejemplo_solo_lectura_incluso_tras_play_stop` | los ejemplos permiten simular e imprimir, sin editar ni guardar copias editables. |
| S-IEJ04 | REQ-EDT-07 | pasa | `test_SIEJ04_autoasignar_nuevas_respetando_mapa_y_memorias` | las nuevas E/S ocupan el primer canal libre compatible; no se asignan memorias ni se pisa un canal. |
| S-IEJ05 | REQ-EDT-13 | pasa | `test_SIEJ05_supr_bloque_no_borra_la_etapa` | Supr elimina el bloque seleccionado, conservando el resto del árbol y el elemento GRAFCET. |
| S-IEJ06 | REQ-JER-04, REQ-SIM-01, REQ-TMP-01 | pasa | `test_SIEJ06_evoluciones_de_los_siete_ejemplos` | cada ejemplo responde a sus entradas y alcanza la salida descrita. |
| S-IEJ07 | REQ-EDT-07 | pasa | `test_SIEJ07_autoasignacion_no_pisa_si_no_hay_capacidad` | agotar canales deja la nueva variable sin asignar, con aviso, y conserva las existentes. |
| S-IEJ08 | REQ-EDT-07 | pasa | `test_SIEJ08_autoasignacion_inmediata_con_conexion_activa` | conectado se publica la variable y se solicita el mapa nuevo sin esperar a desconectar. |
| S-LAM01 | REQ-DAT-02, REQ-EDT-05, REQ-EDT-11 | pasa | `test_SLAM01_presentacion_validada_y_deshacer_sin_cambiar_modelo` | los ajustes son presentación y una sola operación reversible. |
| S-LAM02 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SLAM02_cajetin_completo_se_conserva_en_archivo_del_proyecto` | guardar y abrir conserva todos los campos y el formato sin ampliar el modelo. |
| S-LAM03 | REQ-EDT-11 | pasa | `test_SLAM03_pdf_y_svg_vectoriales_con_tamano_iso_y_orientacion` | A4/A3 en las dos orientaciones producen vector y el tamaño físico elegido. |
| S-LAM04 | REQ-EDT-11 | pasa | `test_SLAM04_sin_seleccion_tiradores_ni_marcas_y_sin_mutacion` | la escena limpia excluye marcas de edición y exportar no altera modelo ni presentación. |
| S-LAM05 | REQ-EDT-11 | pasa | `test_SLAM05_estado_opcional_capturado_de_la_misma_revision` | solo la opción de estado incluye la actividad; la captura no sigue cambios posteriores. |
| S-LAM06 | REQ-EDT-11 | pasa | `test_SLAM06_mosaico_numerado_sin_cortar_simbolos_y_svg_recortado` | la escala fija pagina con referencias, conserva proporción y no corta símbolos o textos. |
| S-LAM07 | REQ-EDT-11 | pasa | `test_SLAM07_escala_sin_referencia_y_simbolo_mayor_se_avisan` | no se inventa una unidad física ni se parte un símbolo que no cabe. |
| S-LAM08 | REQ-EDT-11 | pasa | `test_SLAM08_impresion_comparte_paginas_pdf_y_respeta_cancelacion` | imprimir usa las mismas láminas y el diálogo del sistema; cancelar no imprime. |
| S-LAM09 | REQ-DAT-01, REQ-EDT-11 | pasa | `test_SLAM09_fallo_de_exportacion_conserva_archivo_anterior` | un fallo de exportación no destruye la salida anterior ni deja temporales. |
| S-LAM10 | REQ-EDT-11 | pasa | `test_SLAM10_vista_previa_navega_y_aplica_campos_con_eventos` | la vista previa pasa hojas y aplica el cajetín mediante sus controles reales. |
| S-LAM11 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SLAM11_menu_y_ctrl_p_abren_laminas_y_guarda_cajetin` | Proyecto y Ctrl+P abren la vista, imprimen y guardan el cajetín en .grafnet. |
| S-LAM12 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SLAM12_notas_imagenes_y_reparto_en_dos_ejes` | notas e imágenes se conservan y el mosaico numera por filas y columnas. |
| S-LAM13 | REQ-EDT-11 | pasa | `test_SLAM13_cerrar_previa_sin_cambios_no_ensucia_el_proyecto` | consultar la vista previa sin cambios no añade metadatos ni una operación de deshacer. |
| S-LAM14 | REQ-EDT-11 | pasa | `test_SLAM14_texto_largo_del_cajetin_no_invade_otras_celdas_en_svg` | el SVG emite solo las líneas que caben en cada celda del cajetín, igual que Qt/PDF. |
| S-LAM15 | REQ-EDT-11 | pasa | `test_SLAM15_paginar_conserva_cajas_y_textos_del_dibujo` | crear el mosaico no destruye los símbolos de QGraphicsScene. |
| S-LAZ01 | REQ-EDT-02, REQ-EDT-03, REQ-EDT-05 | pasa | `test_SLAZ01_parcial_vacio_se_selecciona_se_mueve_y_se_borra` | el marco vacío completo entra en el lazo, se mueve y se borra con deshacer. |
| S-LAZ02 | REQ-EDT-02 | pasa | `test_SLAZ02_lazo_parcial_no_incluye_el_marco` | tocar o contener solo parte del marco no lo selecciona. |
| S-LAZ03 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SLAZ03_recinto_con_contenido_consulta_borrado_y_cancela` | el recinto completo entra en el lazo y conserva la confirmación de jerarquía. |
| S-LAZ04 | REQ-EDT-03, REQ-EDT-05 | pasa | `test_SLAZ04_marco_con_contenido_mueve_su_seleccion_sin_duplicar` | agarrar el marco seleccionado desplaza su contenido una sola vez y se deshace junto. |
| S-LAZ05 | REQ-EDT-02, REQ-JER-05 | pasa | `test_SLAZ05_recinto_vacio_entra_en_lazo` | un recinto sin etapas también queda seleccionado por su rectángulo completo. |
| S-LAZ06 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SLAZ06_parcial_suelto_con_contenido_se_borra_y_restaura` | el parcial suelto poblado se selecciona entero y Supr conserva su confirmación. |
| S-LAZ07 | REQ-EDT-03, REQ-EDT-05 | pasa | `test_SLAZ07_dos_marcos_vacios_se_mueven_con_la_seleccion` | varios marcos vacíos seleccionados por lazo se mueven juntos y una sola vez. |
| S-LAZ08 | REQ-EDT-03, REQ-EDT-05, REQ-JER-05 | pasa | `test_SLAZ08_borde_recinto_lleno_mueve_rutas_y_deshace_junto` | borde sin selección previa mueve todo, rutas incluidas, en una operación. |
| S-LAZ09 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SLAZ09_nombre_parcial_lleno_y_clic_interior` | el nombre mueve el parcial lleno; el interior conserva la selección de elementos. |
| S-LAZ10 | REQ-EDT-03, REQ-EDT-05 | pasa | `test_SLAZ10_marco_lleno_rechaza_solape_sin_historial` | el arrastre por borde conserva el rechazo y aviso de solape del movimiento múltiple. |
| S-LAZ11 | REQ-EDT-03, REQ-JER-05 | pasa | `test_SLAZ11_marco_lleno_lleva_hijo_vacio_sin_doble_desplazamiento` | un recinto anidado vacío acompaña al contenido y se deshace con él. |
| S-LAZ12 | REQ-EDT-03, REQ-EDT-05 | pasa | `test_SLAZ12_marco_lleno_lleva_barras_y_acciones_sueltas` | todo lo contenido en el marco, incluidas barras y acciones sueltas, se mueve junto. |
| S-LEY01 | REQ-EDT-02 | pasa | `test_SLEY01_leyenda_tiene_secciones_y_miniaturas_dibujadas_con_el_diagrama` | cada entrada con imagen lleva una miniatura dibujada con diagrama.dibujar; hay seis secciones y la |
| S-LEY02 | REQ-EDT-02, REQ-JER-04, REQ-JER-05 | pasa | `test_SLEY02_la_leyenda_nombra_el_boton_de_dependencias_y_no_habla_de_la_navegacion_antigua` | explica que los trazos macroetapa-expansión y encapsulante-recinto solo se |
| S-MAP01 | REQ-SIM-03 | pasa | `test_SMAP01_cero_anterior_antes_de_publicar_mapa_sin_cerrar_tcp` | las peticiones en vuelo terminan con su mapa; se confirma cero antes de sustituirlo. |
| S-MAP02 | REQ-EDT-07, REQ-SIM-03 | pasa | `test_SMAP02_altas_renombres_bajas_y_arrastre_conectado` | las variables y el mapa cambian en vivo conservando la asignación al renombrar. |
| S-MAP03 | REQ-SIM-03 | pasa | `test_SMAP03_cantidades_cero_y_restablecer_sin_pisar_asignaciones` | cero canales es válido; restablecer propone 32/12 y conserva direcciones ocupadas. |
| S-MAP04 | REQ-EDT-09, REQ-ROB-01 | pasa | `test_SMAP04_ayuda_siempre_en_pie_y_nunca_ventana` | quitar asignaciones y cambiar de vista no crea una ventana de ayuda. |
| S-MAP05 | REQ-EDT-11 | pasa | `test_SMAP05_cadena_para_plano_incluye_accion_interrogante` | traer una cadena conserva su acción pendiente y su diagnóstico sin exigir compilar. |
| S-MAP06 | REQ-SIM-03 | pasa | `test_SMAP06_conectar_correcto_error_y_desconexion_conservan_es` | iniciar desde E/S, incluso con Play previo, no cambia la pestaña ni al fallar. |
| S-MAP07 | REQ-SIM-02 | pasa | `test_SMAP07_contacto_nc_menu_presion_y_suelta` | el menú NC invierte reposo y pulsación, produciendo dos cambios reales. |
| S-MAP08 | REQ-SIM-03 | pasa | `test_SMAP08_red_correcta_rechazada_timeout_y_caida_no_cambian_pagina` | los resultados asíncronos de red conservan E/S, también con error o caída. |
| S-MAP11 | REQ-SIM-03 | pasa | `test_SMAP11_play_invalida_un_mapa_en_vuelo_sin_resucitar_monitor` | una respuesta antigua de reasignación no reemplaza la sesión nueva de Play. |
| S-MOD01 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SMOD01_play_stop_ancho_fijo_y_reiniciar_no_se_desplaza` | el ancho mayor de Play/Stop evita mover los controles siguientes. |
| S-MOD02 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SMOD02_play_oculta_y_stop_restaura_tamanos_y_divisor_manual` | Play oculta paleta e inferior; Stop restaura sus tamaños y el reparto manual. |
| S-MOD03 | REQ-EDT-09 | pasa | `test_SMOD03_plegado_previo_y_ancho_derecho_manual_se_conservan` | se respetan los paneles plegados previamente y el ancho que el usuario haya dejado con el divisor. |
| S-MOD04 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SMOD04_zoom_y_puntos_en_pantalla_iguales_al_entrar_y_salir` | la geometría en pantalla se conserva aunque se amplíe el área visible al ocultar paneles. |
| S-MOD05 | REQ-EDT-09 | pasa | `test_SMOD05_encuadre_extremo_a_1000_y_centrar_sigue_disponible` | se conserva el encuadre cerca del límite de desplazamiento, y Centrar todo mantiene su función. |
| S-MOD06 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SMOD06_stop_y_reiniciar_desde_es_por_boton_y_atajo` | botones y atajos inactivos en E/S; volver a GRAFCET los recupera con el conmutador coherente. |
| S-MOD07 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SMOD07_pulsador_interruptor_y_ctrl_se_distinguen_sin_cambiar_texto` | iconos distintos distinguen tipo y enclavamiento y se actualizan al liberar Ctrl. |
| S-MOD08 | REQ-SIM-03 | pasa | `test_SMOD08_cabecera_es_solo_verde_o_color_original` | desconexión y fallo restauran el fondo neutro manteniendo sus mensajes. |
| S-MOD09 | REQ-EDT-09 | pasa | `test_SMOD09_punta_reiniciar_en_extremo_y_simetrica_a_tangente` | la punta angular de la referencia continúa la tangente, con brazos simétricos. |
| S-MOD10 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SMOD10_variables_texto_mas_margenes_cabe_sin_ensanchar_panel` | se conserva la corrección anterior, con dos columnas y espacio para texto y relleno. |
| S-MOD11 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SMOD11_altura_automatica_previa_se_restaura_con_receptividad_seleccionada` | también la altura automática del editor se conserva al parar, sin un nuevo reparto. |
| S-MOD12 | REQ-EDT-01, REQ-EDT-09 | pasa | `test_SMOD12_abrir_otro_ejemplo_cancela_restauraciones_pendientes` | abrir otra fuente permite el encuadre inicial, sin aplicar el del proyecto anterior. |
| S-MOD13 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SMOD13_entradas_booleanas_y_numericas_caben_en_el_ancho_conservado` | conservar el ancho derecho no recorta pulsadores, interruptores ni edición numérica. |
| S-MTP01 | REQ-EDT-08, REQ-JER-04, REQ-MOD-07 | pasa | `test_SMTP01_etapa_a_macroetapa_conserva_id_nombre_posicion_y_enlaces_y_equivale_a_add_macro` | `set_step_kind(etapa, "macro")` deja una macroetapa con el ID, el |
| S-MTP02 | REQ-JER-04, REQ-JER-05, REQ-MOD-07 | pasa | `test_SMTP02_macroetapa_a_etapa_ordinaria_o_encapsulante_solo_con_la_expansion_vacia` | una macroetapa pasa a etapa ordinaria o encapsulante con su ID y sus |
| S-MTP03 | REQ-JER-04, REQ-JER-05, REQ-MOD-07 | pasa | `test_SMTP03_rechazos_al_convertir_en_macroetapa` | una encapsulante con recintos, una etapa inicial, una con acciones |
| S-MTP04 | REQ-EDT-09, REQ-JER-04, REQ-JER-05 | pasa | `test_SMTP04_etapa_con_ordenes_o_enlace_de_activacion_no_pasa_a_macroetapa_con_texto_claro` | una etapa que es origen de una orden de forzado, la que lleva el |
| S-MTP10 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SMTP10_accion_a_orden_de_forzado_aceptar_cancelar_y_deshacer` | «Tipo de acción > Orden de forzado» en una acción de una etapa abre el diálogo de |
| S-MTP11 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SMTP11_accion_sin_completar_o_suelta_a_orden_y_rechazos` | una acción sin completar unida a una etapa pasa a orden del modelo; una suelta, a |
| S-MTP12 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SMTP12_ciclo_de_forzado_al_convertir_una_accion_no_cambia_nada` | si el núcleo rechaza la orden (ciclo, D-JERARQUIA-CICLO), la acción sigue donde |
| S-MTP13 | REQ-EDT-09, REQ-JER-02 | pasa | `test_SMTP13_orden_de_forzado_a_accion_del_modelo_sin_completar_y_suelta` | el menú de una orden de forzado (del modelo, sin completar unida o suelta) lleva |
| S-MTP20 | REQ-EDT-09, REQ-JER-04, REQ-JER-05 | pasa | `test_SMTP20_submenu_tipo_de_etapa_con_iconos_marcas_y_casilla_de_inicial` | el botón derecho en una etapa ofrece «Tipo de etapa» con icono por |
| S-MTP21 | REQ-EDT-09, REQ-JER-04, REQ-JER-05 | pasa | `test_SMTP21_los_cuatro_cambios_de_tipo_de_etapa_con_el_menu` | Etapa <-> Encapsulante y Etapa/Encapsulante <-> Macroetapa desde el |
| S-MTP22 | REQ-EDT-09, REQ-JER-04, REQ-JER-05 | pasa | `test_SMTP22_rechazos_del_tipo_de_etapa_se_muestran_en_rojo_y_no_cambian_nada` | una encapsulante con recintos no vuelve a etapa ni pasa a macroetapa; |
| S-MTP23 | REQ-DAT-01, REQ-EDT-08, REQ-JER-04 | pasa | `test_SMTP23_macroetapa_por_conversion_se_guarda_y_se_abre_y_simula_como_la_de_la_ficha` | la macroetapa que sale de convertir una etapa desde el menú tiene la |
| S-NAV01 | REQ-EDT-12 | pasa | `test_SNAV01_buscar_revela_encuadra_y_selecciona_sin_modificar` | Ctrl+F encuentra por nombre y revela un elemento de un parcial oculto sin editarlo. |
| S-NAV02 | REQ-EDT-12 | pasa | `test_SNAV02_filtro_informa_y_solo_afecta_a_la_vista` | ocultar o atenuar no cambia el modelo ni el estado que recibe la vista. |
| S-NAV03 | REQ-EDT-12 | pasa | `test_SNAV03_busqueda_compacta_sin_minimapa` | Ctrl+F muestra la búsqueda en la cabecera, sin lista expandida ni minimapa. |
| S-NAV04 | REQ-EDT-12 | pasa | `test_SNAV04_filtro_web_como_qt` | el renderizador web etiqueta los parciales y oculta/atenúa solo el resto, con aviso. |
| S-NAV05 | REQ-EDT-12 | pasa | `test_SNAV05_filtro_y_busqueda_con_simulacion_real` | la búsqueda y el filtro conservan la situación completa de una simulación real. |
| S-NAV06 | REQ-EDT-12 | pasa | `test_SNAV06_siguiente_anterior_y_sin_resultados` | las flechas y el teclado recorren coincidencias repetidas con contador y sin cambiar el modelo. |
| S-NAV07 | REQ-EDT-13 | pasa | `test_SNAV07_textos_de_atajos_y_menu_sin_seleccionar` | el menú muestra Ctrl+Enter y Supr y omite Seleccionar, sin perder los atajos reales. |
| S-OPT03a | REQ-EVT-03, REQ-NOR-02, REQ-SEM-09 | pasa | `test_SOPT03a_por_defecto_situacion_anterior` | por defecto, la respuesta 5.1 («situación anterior»); «detener» sigue disponible. |
| S-OPT03b | REQ-EVT-03, REQ-SEM-09, REQ-SIM-05 | pasa | `test_SOPT03b_lectura_situacion_anterior` | el evento solo franquea lo validado antes de él → B, con hipótesis en la traza. |
| S-OPT03c | REQ-EVT-03, REQ-SEM-07, REQ-SEM-09 | pasa | `test_SOPT03c_lectura_recorrido` | el evento sigue disponible en el recorrido → C; con reinicio, ciclo sin fin. |
| S-OPT03d | REQ-DAT-04, REQ-SIM-04 | pasa | `test_SOPT03d_instantanea_exige_la_misma_lectura` | no se mezclan instantáneas de lecturas distintas. |
| S-OPT03e | REQ-EVT-03, REQ-MOD-04 | pasa | `test_SOPT03e_limites_de_la_opcion` | valores no admitidos se rechazan; la repetición de fuentes la decide 6.3, no U-03. |
| S-OTR01 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SOTR01_presentacion_y_deshacer_sin_modificar_modelo` | crear, editar, mover y borrar notas solo cambia presentación y se deshace. |
| S-OTR02 | REQ-EDT-04, REQ-JER-05 | pasa | `test_SOTR02_copiar_parcial_y_nota_suelta_con_identidades_nuevas` | las notas propias viajan con el parcial y una nota suelta se pega en el destino. |
| S-OTR03 | REQ-EDT-09 | pasa | `test_SOTR03_pestanas_abren_minimo_o_distancia_y_la_izquierda_es_fija` | arrastrar una pestaña cerrada hacia el centro abre al mínimo o a la distancia elegida. |
| S-OTR04 | REQ-EDT-09 | pasa | `test_SOTR04_divisores_cerrados_abren_hacia_el_centro` | el divisor de un panel cerrado admite el gesto de apertura, incluido Elementos. |
| S-OTR05 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SOTR05_texto_desde_paleta_se_mueve_redimensiona_y_deshace` | un Texto de Otros se selecciona, mueve y redimensiona mediante eventos reales. |
| S-OTR06 | REQ-DAT-02, REQ-EDT-02 | pasa | `test_SOTR06_png_y_jpg_incorporados_y_tamano_con_raton` | PNG/JPG se incorporan al proyecto, conservan proporciones y no dependen del archivo original. |
| S-OTR07 | REQ-EDT-02 | pasa | `test_SOTR07_dialogo_texto_edita_fuente_tamano_y_color` | el diálogo confirma texto, familia, tamaño y color; cancelar no modifica nada. |
| S-OTR08 | REQ-EDT-03 | pasa | `test_SOTR08_etapa_interior_arrastra_y_borde_enlaza` | el interior cerca de los conectores mueve la etapa; el borde conserva el enlace. |
| S-OTR09 | REQ-EDT-09 | pasa | `test_SOTR09_accion_por_evento_reserva_mas_espacio_al_evento` | en una acción por evento el editor del evento es claramente mayor que el del valor. |
| S-OTR10 | REQ-DAT-02, REQ-EDT-09 | pasa | `test_SOTR10_qt_y_js_dibujan_notas_y_proyecto_se_reabre` | texto e imagen se conservan al guardar y ambos renderizadores usan la misma geometría y estilo. |
| S-OTR11 | REQ-EDT-04, REQ-EDT-05 | pasa | `test_SOTR11_atajos_copian_cortan_y_pegan_texto_entre_proyectos` | el portapapeles de texto sobrevive al proyecto y cortar/pegar se deshace de una vez. |
| S-OTR12 | REQ-EDT-03, REQ-JER-05 | pasa | `test_SOTR12_arrastrar_marco_mueve_texto_con_el_contenido_una_vez` | la anotación de un parcial se mueve con su marco en una operación. |
| S-OTR13 | REQ-DAT-02 | pasa | `test_SOTR13_cancelar_o_archivo_no_valido_no_crea_imagen` | cancelar o elegir datos que no son PNG/JPG conserva el proyecto y da un aviso breve. |
| S-PAG01 | REQ-EDT-11 | pasa | `test_SPAG01_planos_es_pagina_incrustada_sin_editor_modal` | el botón Planos abre una página de la ventana, con lista, lienzo y propiedades. |
| S-PAG02 | REQ-EDT-11, REQ-SIM-03 | pasa | `test_SPAG02_navegar_grafcet_planos_es_y_controles_coherentes` | GRAFCET, Planos y E/S conservan sus botones y bloquean Play/Reiniciar en Planos. |
| S-PAG03 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG03_guardar_aplica_cambios_sin_esperar_el_temporizador` | Ctrl+S incluye los campos recién editados en Planos sin necesitar Aplicar. |
| S-PAG04 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG04_cambio_vista_y_cancelacion_de_nuevo_no_pierden_campos` | salir de Planos aplica los campos y cancelar Nuevo conserva el proyecto. |
| S-PAG05 | REQ-EDT-11 | pasa | `test_SPAG05_lista_de_hojas_aplica_campos_y_refleja_el_original` | las hojas de la izquierda muestran su selección vinculada y guardan sus ajustes por separado. |
| S-PAG06 | REQ-EDT-11 | pasa | `test_SPAG06_zoom_visual_no_cambia_escala_ni_cajetin_y_exporta_limpio` | zoom y selección de colocación afectan solo a la pantalla, sin cambiar el PDF/SVG. |
| S-PAG07 | REQ-EDT-11 | pasa | `test_SPAG07_imprimir_y_exportar_desde_el_plano_actual` | Ctrl+P y la barra imprimen/exportan la hoja seleccionada, sin abrir otro editor. |
| S-PAG08 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG08_cambios_se_aplican_en_memoria_sin_autoguardado_a_archivo` | editar un campo deja el proyecto modificado, pero no guarda archivos automáticamente. |
| S-PAG09 | REQ-EDT-11 | pasa | `test_SPAG09_planos_vacio_hasta_creacion_explicita` | abrir Planos no crea hojas ni añade el dibujo completo por defecto. |
| S-PAG10 | REQ-EDT-11 | pasa | `test_SPAG10_traer_seleccion_explicita_confirmar_y_cancelar` | Traer vuelve al editor y solo incluye los elementos seleccionados al confirmar. |
| S-PAG11 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG11_varios_planos_hojas_y_dibujos_persisten` | cada plano conserva varias hojas y cada hoja varias selecciones vinculadas. |
| S-PAG12 | REQ-EDT-11 | pasa | `test_SPAG12_tamano_impreso_50_200_no_modifica_original` | cada GRAFCET se escala del 50 al 200 %, conservando los 11,64 mm de referencia al 100 %. |
| S-PAG13 | REQ-EDT-11 | pasa | `test_SPAG13_rueda_sin_ctrl_y_arrastre_central_desplazan_vista` | rueda sin Ctrl y botón central navegan como en el dibujo principal sin mover lo impreso. |
| S-PAG14 | REQ-EDT-11 | pasa | `test_SPAG14_exportacion_incluye_todas_las_colocaciones` | PDF/SVG contienen todas las selecciones de la hoja sin selección azul ni fondo sepia. |
| S-PAG15 | REQ-EDT-11 | pasa | `test_SPAG15_insertar_sin_sitio_no_cambia_hoja` | una selección que no cabe se rechaza sin insertar parcialmente ni reducirla a escondidas. |
| S-PAG16 | REQ-EDT-11 | pasa | `test_SPAG16_enviar_a_hoja_existente_y_escalas_independientes` | Enviar a plano permite elegir una hoja existente y conserva el tamaño de sus otras selecciones. |
| S-PAG17 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG17_orden_herramientas_y_tamanos` | pestañas antes de herramientas propias, sin botones generales duplicados. |
| S-PAG18 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG18_importar_real_pdf_dxf_svg_y_reabrir_sin_original` | la acción visible importa formatos externos y los incorpora al archivo. |
| S-PAG19 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG19_cancelacion_error_y_pdf_cancelado_no_cambian_hoja` | cancelar importación o fallar no modifica presentación ni historial. |
| S-PAG20 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG20_texto_en_hoja_propiedades_mover_eliminar_historial` | un clic coloca texto libre; propiedades, arrastre y borrado se deshacen. |
| S-PAG21 | REQ-EDT-11 | pasa | `test_SPAG21_edicion_interna_zona_y_textos_libres` | textos importados y zona se editan en la hoja como textos libres, sin enlaces a campos. |
| S-PAG22 | REQ-EDT-11 | pasa | `test_SPAG22_plantilla_libre_campos_contextuales_y_exportacion` | sin campos extensos; textos usan el mismo dibujo en PDF/SVG/impresión. |
| S-PAG23 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG23_migracion_nombres_repetidos_sin_perdida` | la lista única reúne hojas con nombres iguales de planes distintos sin descartarlas. |
| S-PAG24 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG24_colocacion_grafcet_deshacer_sin_reaplicar_valor_viejo` | Ctrl+Z/Y en Planos restaura tamaño y posición, sin reescribir el estado deshecho. |
| S-PAG25 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG25_propiedades_texto_sin_recortes_y_cajetin_sin_franja` | propiedades utilizables a 1000×600 y franja extra ausente solo de la plantilla propia. |
| S-PAG26 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG26_traer_solo_selecciona_y_restaura_paneles` | Traer oculta herramientas y paneles, solo selecciona y restaura al cancelar. |
| S-PAG27 | REQ-EDT-11 | pasa | `test_SPAG27_texto_heredado_libre_y_edicion_marcada` | un texto antes automático se escribe libremente, sin selector de campos ni botones de diálogo. |
| S-PAG28 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG28_rotulos_antiguos_y_margen_fijo` | elimina rótulos auxiliares propios heredados y bloquea la edición de márgenes. |
| S-PAG29 | REQ-EDT-11 | pasa | `test_SPAG29_mtext_dxf_respetan_banda_y_altura_visible` | MTEXT superior/centrado usa las letras visibles, no el interlineado de Qt; no corta el marco. |
| S-PAG30 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG30_enviar_al_final_del_menu_con_separador` | Enviar a plano es la última sección del menú contextual real. |
| S-PAG31 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG31_marco_completo_sin_invadir_cajetin_con_raton` | se puede colocar a la izquierda del cajetín, pero no encima, y deshacer el arrastre. |
| S-PAG32 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG32_miniaturas_todas_zoom_y_anadir_al_final` | todas las hojas tienen miniatura, independiente del zoom; botón y nuevas hojas al final. |
| S-PAG33 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG33_dxf_antiguo_recupera_interior_completo_sin_tocar_zona_manual` | DXF ya incorporado recupera marco/cajetín desde sus líneas; una zona manual se conserva. |
| S-PAG34 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG34_suprimir_colocacion_deshacer_y_texto_no_borran_original` | Supr elimina solo el GRAFCET seleccionado de la hoja en una transacción reversible. |
| S-PAG35 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG35_rotulos_completos_boton_separado_y_flecha_incorporada` | títulos de hojas completos, botones con contraste y flecha sin borde nativo superpuesto. |
| S-PAG36 | REQ-EDT-11 | pasa | `test_SPAG36_exportar_propone_plano_y_conserva_hoja_actual` | PDF/SVG se proponen como plano, sin cambiar formatos ni la hoja que se exporta. |
| S-PAG37 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPAG37_cambiar_ejemplos_y_reabrir_mismos_ids_no_bloquea_planos` | el editor de hojas de la fuente anterior no escribe ni dibuja sobre el nuevo proyecto. |
| S-PAG38 | REQ-EDT-11, REQ-JER-05 | pasa | `test_SPAG38_jerarquias_solo_se_llevan_si_se_seleccionan` | Planos usa la selección exacta; Copiar conserva su ampliación jerárquica habitual. |
| S-PAG39 | REQ-DAT-02, REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG39_menu_hojas_reordena_deshace_y_guarda_orden` | menú contextual real para subir/bajar hojas; orden y datos reversibles. |
| S-PAG40 | REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPAG40_suprimir_hojas_menu_teclado_y_ultima_con_deshacer` | Supr y menú eliminan la hoja completa, sin tocar el modelo, y se deshacen. |
| S-PAG41 | REQ-EDT-01, REQ-EDT-11 | pasa | `test_SPAG41_tarjetas_no_recortan_rotulos_con_varias_hojas_y_fuente_grande` | tarjeta completa a distintos tamaños/fuentes; lateral desplazable y Añadir al final. |
| S-PAG42 | REQ-EDT-11, REQ-JER-05 | pasa | `test_SPAG42_traer_cadena_ctrl_quita_y_shift_suma_sin_hijas` | clic elige cadena propia, Ctrl ajusta elementos y Mayús suma la hija solo expresamente. |
| S-PAL01 | REQ-EDT-02 | pasa | `test_SPAL01_icono_y_arrastre_comparten_dibujo_y_pixeles` | las trece fichas usan la misma función y la misma imagen en lista y arrastre, solo escalada y centrada. |
| S-PAL02 | REQ-EDT-02 | pasa | `test_SPAL02_cajas_de_acciones_y_forzado_tienen_la_altura_de_etapa` | la altura de referencia es 44 en etapas, cinco acciones y forzado, con cajas de acción idénticas. |
| S-PAL03 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SPAL03_solo_transicion_tiene_conectores_y_barra_sin_ramas` | no hay tallos en etapas ni enlaces a acciones; la simultaneidad contiene solo dos trazos. |
| S-PAL04 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SPAL04_g_sobre_el_borde_y_fuente_normal_proporcionada` | la G corta el borde inferior tanto al arrastrar como en el icono, con peso normal. |
| S-PAL05 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SPAL05_dos_columnas_cabeceras_completas_y_nombres_debajo` | orden y cabeceras se conservan, dos fichas por fila y espacio para todos los nombres. |
| S-PAL06 | REQ-EDT-09 | pasa | `test_SPAL06_ancho_y_minimo_no_crecen_y_scroll_alcanza_todas` | se conserva el ancho de 218 y el mínimo anterior; a 1366×768 y 1000×600 se alcanzan las fichas. |
| S-PAL07 | REQ-EDT-02, REQ-EDT-03 | pasa | `test_SPAL07_gestos_reales_arrastran_parcial_y_accion_a_su_escala` | pulsar y arrastrar conserva MIME, imagen compartida y punto de colocación con zoom y DPR. |
| S-PAN01 | REQ-EDT-09 | pasa | `test_SPAN01_cabeceras_y_pestanas_fuera_del_dibujo` | cada cabecera pliega y la pestaña nombrada recupera su panel, con menú y ajustes coherentes. |
| S-PAN02 | REQ-EDT-09 | pasa | `test_SPAN02_izquierdo_ancho_fijo_y_arrastre_para_plegar` | el izquierdo no se amplía; arrastrar hacia dentro lo pliega y su pestaña recupera el ancho fijo. |
| S-PAN03 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SPAN03_derecho_amplia_nombre_y_pliega_antes_de_comprimir_tabla` | solo Nombre absorbe el ancho extra; bajar del mínimo pliega y restaura el tamaño útil anterior. |
| S-PAN04 | REQ-EDT-09 | pasa | `test_SPAN04_inferior_pliega_bajo_minimo_y_recupera_altura_por_atajo` | el editor no se comprime por debajo de su mínimo útil; la pestaña y Ctrl+J conservan la altura anterior. |
| S-PAN05 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SPAN05_formula_estado_y_controles_en_una_fila_con_vista_previa` | fórmula, estado, ampliar y papelera comparten fila; vista previa y edición manual siguen disponibles. |
| S-PAN06 | REQ-EDT-09 | pasa | `test_SPAN06_editor_compacto_util_a_1000_y_categorias_accesibles` | a 1000×600 los controles no se cortan, y las categorías largas conservan su desplazamiento. |
| S-PAN07 | REQ-EDT-09 | pasa | `test_SPAN07_preferencias_de_plegado_se_recuperan_en_otra_ventana` | se registra el plegado; una ventana nueva abre los laterales y mantiene propiedades plegadas. |
| S-PAN08 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SPAN08_simulacion_y_edicion_conservan_paneles_y_nombres_de_pestanas` | Play oculta Elementos, y los paneles de edición se recuperan sin perder sus preferencias. |
| S-PAN09 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SPAN09_minimo_inferior_se_actualiza_tras_arrastre_y_cambio_de_elemento` | pasar de etapa a transición aumenta el mínimo útil aunque el alto se haya elegido a mano. |
| S-PAN10 | REQ-EDT-09 | pasa | `test_SPAN10_pestanas_plegadas_sin_hueco_al_volver_de_es` | cambiar de pantalla en E/S no reserva el ancho del contenido plegado. |
| S-PAN11 | REQ-EDT-09 | pasa | `test_SPAN11_ancho_elegido_se_conserva_tras_es_y_redimensionar` | el lateral abierto conserva el ancho elegido sin absorber el dibujo al volver de E/S. |
| S-PKG | REQ-ALC-02, REQ-CR-02 | pasa | `test_SPKG_paquete_de_transferencia_intacto` | parte automatizable de R-02 (doce Markdown, huellas de la versión implementada). |
| S-PLT01 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPLT01_dxf_entidades_bloques_unidades_textos_y_campos` | DXF en mm/pulgadas conserva geometría, atributos, tildes, alineación y transformaciones. |
| S-PLT02 | REQ-EDT-11 | pasa | `test_SPLT02_sugerencias_no_enlazan_sin_aceptacion` | HOJA se propone y permanece fija hasta aceptar expresamente el enlace. |
| S-PLT03 | REQ-EDT-11 | pasa | `test_SPLT03_pdf_a4_a3_fondo_300ppp_sin_textos_y_giro` | PDF conserva mm, extrae textos editables y deja un fondo PNG sin duplicarlos. |
| S-PLT04 | REQ-EDT-11 | pasa | `test_SPLT04_pdf_pagina_elegida_y_textos_en_trazos_avisados` | elegir otra página respeta su contenido; los textos en trazos se conservan y se avisan. |
| S-PLT05 | REQ-DAT-02, REQ-EDT-05, REQ-EDT-11 | pasa | `test_SPLT05_guardar_abrir_sin_original_ni_importadores_y_deshacer` | plantilla autónoma en .grafnet y una operación reversible sin tocar modelo. |
| S-PLT06 | REQ-EDT-11 | pasa | `test_SPLT06_exportaciones_contienen_fondo_y_texto_editado_con_zona` | PDF/SVG y mosaico reutilizan fondo, campos editados y zona útil sin invadir el cajetín. |
| S-PLT07 | REQ-EDT-11 | pasa | `test_SPLT07_svg_autonomo_tamano_real_y_personalizado` | SVG autónomo se usa de fondo sin campos y conserva sus medidas físicas. |
| S-PLT08 | REQ-EDT-11 | pasa | `test_SPLT08_editor_textos_mover_borrar_anadir_y_marcar_zona` | edición real de contenido, posición, tamaño, giro y zona; cancelar conserva el original. |
| S-PLT09 | REQ-EDT-11 | pasa | `test_SPLT09_importar_invalido_y_cancelar_no_cambian_lamina` | errores, DWG y cancelación dejan formato, plantilla y campos intactos. |
| S-PLT10 | REQ-EDT-11 | pasa | `test_SPLT10_pdf_cifrado_invalido_y_vacio_rechazados` | cifrado, archivo no válido y página vacía dan avisos claros antes de importar. |
| S-PLT11 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPLT11_validacion_de_primitivas_y_limites_de_zona` | no se aceptan coordenadas, primitivas o zonas corruptas. |
| S-PLT12 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_SPLT12_importacion_aceptada_se_guarda_con_campos_y_mismo_modelo` | aceptar la importación permite aplicar y guardar la plantilla desde Lámina. |
| S-PLT13 | REQ-EDT-11 | pasa | `test_SPLT13_dxf_sin_unidades_y_caja_no_iso` | sin INSUNITS se usan mm y un marco no ISO conserva su caja propia. |
| S-PLT14 | REQ-EDT-11 | pasa | `test_SPLT14_pdf_texto_en_formulario_anidado_se_extrae_y_quita` | los textos dentro de Form XObjects también son editables y desaparecen del fondo. |
| S-PLT15 | REQ-EDT-11 | pasa | `test_SPLT15_zona_automatica_usa_marco_interior_y_no_cuadricula` | con doble marco, la zona útil empieza dentro del marco interior, fuera de la cuadrícula. |
| S-PLT16 | REQ-EDT-11 | pasa | `test_SPLT16_escala_fija_por_defecto_etapas_de_1164_mm` | decisión del responsable, etapa de 44 unidades a unos 11,64 mm por defecto, sin ajuste automático. |
| S-PLT17 | REQ-EDT-11 | pasa | `test_SPLT17_textos_fit_aligned_respetan_anclas_y_altura` | TEXT FIT y ALIGNED conservan el ancho entre anclas; ALIGNED escala también la altura. |
| S-PRP01 | REQ-DAT-02 | pasa | `test_SPRP01_info_sellada_con_autor_fechas_y_versiones` | cada guardado escribe `_grafnet/info.json` sellado con los cinco campos. |
| S-PRP02 | REQ-DAT-02 | pasa | `test_SPRP02_creado_se_conserva_y_modificado_cambia` | entre guardados, creado y version_creacion se conservan; modificado y version_guardado se actualizan. |
| S-PRP03 | REQ-DAT-02 | pasa | `test_SPRP03_archivo_anterior_sin_info_abre_y_no_inventa_creacion` | un archivo sin info.json abre igual; al guardarlo no se inventan creado ni version_creacion. |
| S-PRP04 | REQ-DAT-02 | pasa | `test_SPRP04_info_manipulado_sin_resellar_se_rechaza` | info.json está cubierto por el sello: cambiarlo sin resellar rechaza el archivo. |
| S-PRP05 | REQ-DAT-02 | pasa | `test_SPRP05_info_mal_formado_con_sello_valido_se_ignora` | un info.json con tipos o tamaño incorrectos no rechaza el archivo: datos desconocidos. |
| S-PRP06 | REQ-DAT-02 | pasa | `test_SPRP06_huella_cambia_con_el_contenido_y_no_con_la_clave` | la huella (sin clave) identifica el contenido sellado. |
| S-PRP07 | REQ-NOR-02 | pasa | `test_SPRP07_version_del_programa_y_manifiesto_no_divergen` | escritorio.VERSION, APP_VERSION y appVersion del manifiesto son la misma, 1.0.0. |
| S-PRP20 | REQ-DAT-02 | pasa | `test_SPRP20_proyecto_nuevo_se_sellara_al_guardar_y_toma_el_usuario_como_autor` | sin guardar no hay sello ni fechas; el autor por defecto es el usuario del sistema. |
| S-PRP21 | REQ-DAT-02 | pasa | `test_SPRP21_cambiar_el_autor_marca_modificado_lo_guarda_y_lo_recuerda` | el autor cambia en el diálogo, marca el asterisco y viaja en info.json. |
| S-PRP22 | REQ-DAT-02 | pasa | `test_SPRP22_proyecto_guardado_muestra_sello_algoritmo_huella_y_programa` | el diálogo informa del sello vigente, la huella agrupada y el programa, sin clave. |
| S-PRP23 | REQ-DAT-02 | pasa | `test_SPRP23_archivo_anterior_muestra_desconocida` | un archivo sin info.json abre y el diálogo dice «desconocida (archivo anterior a la 1.0)». |
| S-PUL01 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SPUL01_presionar_y_soltar_producen_dos_cambios_y_evoluciones` | el pulsador da 1 al presionar y 0 al soltar, procesando ambas evoluciones. |
| S-PUL02 | REQ-SIM-02 | pasa | `test_SPUL02_ctrl_enclava_y_otro_clic_libera_sin_perder_otras_entradas` | Ctrl+clic mantiene varias entradas y permite pulsar otras; el siguiente clic libera. |
| S-PUL03 | REQ-DAT-01, REQ-SIM-02 | pasa | `test_SPUL03_menu_cambia_tipo_y_lo_recuerda_sin_guardarlo` | el tipo de entrada se cambia en menú y dura la sesión sin entrar en los documentos. |
| S-PUL04 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SPUL04_conexion_externa_no_admite_cambios_manuales` | las entradas conectadas siguen perteneciendo exclusivamente a la conexión. |
| S-PUL05 | REQ-SIM-02 | pasa | `test_SPUL05_soltar_fuera_del_boton_no_deja_entrada_activa` | soltar el pulsador fuera de su rectángulo también devuelve la entrada a 0. |
| S-PUL06 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SPUL06_soltar_ctrl_libera_todos_los_enclavados_y_conserva_interruptor` | teclado y ratón reales liberan al soltar Ctrl cada pulsador y procesan sus evoluciones. |
| S-RCT01 | REQ-EDT-09 | pasa | `test_SRCT01_cambiar_el_tamaño_de_la_ventana_recentra_tras_el_retardo` | al redimensionar la ventana, un temporizador de disparo único llama a «Centrar todo»; plegar un |
| S-RED01 | REQ-SIM-03 | pasa | `test_SRED01_aviso_no_ejecuta_motor_en_trabajador` | la red notifica; solo el propietario aplica la muestra. |
| S-RED02 | REQ-SIM-03 | pasa | `test_SRED02_periodo_nuevo_y_explicito` | periodo inicial de 20 ms sin alterar valores explícitos. |
| S-RED03 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SRED03_respuesta_inmediata_sin_tick_periodico` | leer, evolucionar y escribir por respuesta, sin esperar al periodo. |
| S-RED04 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SRED04_siguiente_lectura_y_stop_sin_refresco_periodico` | sondeo autónomo y Stop a cero con el reloj periódico parado. |
| S-RED05 | REQ-TMP-02 | pasa | `test_SRED05_reloj_conserva_fracciones` | callbacks frecuentes conservan el tiempo inferior al milisegundo. |
| S-RED06 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SRED06_periodos_cortos_guardar_y_abrir` | 5 y 10 ms se validan y guardan sin cambiar el valor inicial. |
| S-RED07 | REQ-SIM-03 | pasa | `test_SRED07_planificacion_con_fracciones_de_milisegundo` | un sondeo de 5 ms usa plazos del reloj de alta resolución. |
| S-RED08 | REQ-SIM-03 | pasa | `test_SRED08_selector_admite_5_y_10_ms` | el panel admite 5 y 10 ms y conserva esos valores al recargar. |
| S-RED09 | REQ-SIM-02, REQ-SIM-03 | pasa | `test_SRED09_intercambio_real_a_5_y_10_ms` | intercambio TCP y cero de Stop con periodos cortos, sin prometer cadencia exacta. |
| S-RED10 | REQ-SIM-03 | pasa | `test_SRED10_desconectar_conserva_vista_es_en_play_y_stop` | desconectar por el botón detiene y pone a cero sin sacar al usuario de E/S. |
| S-RED11 | REQ-SIM-03 | pasa | `test_SRED11_tiempos_visibles_y_detalle` | se distinguen el sondeo real, el ciclo y la espera al aplicar la entrada. |
| S-RED12 | REQ-SIM-03 | pasa | `test_SRED12_es_no_reconstruye_el_dibujo_oculto` | la vista E/S actualiza valores sin reconstruir el GRAFCET oculto. |
| S-RED13 | REQ-SIM-03 | pasa | `test_SRED13_reloj_solo_no_reconstruye_pero_un_cambio_si` | el reloj avanza sin recrear el dibujo idéntico; una entrada sí lo actualiza. |
| S-RED14 | REQ-SIM-03, REQ-TMP-02 | pasa | `test_SRED14_temporizador_sigue_redibujando` | los cambios del tiempo mostrado invalidan la reutilización del dibujo. |
| S-RED15 | REQ-SIM-03 | pasa | `test_SRED15_tablas_reutilizan_celdas_y_actualizan_valor_y_color` | actualizar valores conserva las celdas y cambia texto y color cuando corresponde. |
| S-RED16 | REQ-SIM-03 | pasa | `test_SRED16_parada_por_ambos_haces_con_marcha_por_pulso` | el ensayo de dos etapas se para al recibirse ambos haces, con Marcha ya liberada. |
| S-RED17 | REQ-SIM-03 | pasa | `test_SRED17_ultima_parada_conserva_entradas_y_tiempos_de_ese_instante` | el diagnóstico conserva la entrada previa a la salida a cero, no una muestra posterior. |
| S-REM01 | REQ-EDT-09 | pasa | `test_SREM01_divisor_no_realimenta_relayout_de_paleta` | el arrastre real del divisor mantiene mínimos, barra y celdas estables al cambiar solo el alto. |
| S-REM02 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SREM02_variables_ajustan_filas_y_botones_debajo_con_limite` | tabla sin espacio sobrante, botones debajo y desplazamiento interno con muchas filas. |
| S-REM03 | REQ-EDT-09 | pasa | `test_SREM03_diagnostico_en_lienzo_selecciona_sin_tapar_zoom` | sin errores no hay indicador; el error con nombre se pulsa sobre el dibujo y conserva selección y parpadeo. |
| S-REM04 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SREM04_bool_sin_escala_numerica_editable_y_configuracion_portable` | BOOL muestra guion y guarda 1; INT16/UINT16 admiten escala, dirección, formato y uso. |
| S-REM05 | REQ-SIM-03 | pasa | `test_SREM05_listas_simetria_arrastre_compacto_y_plc_sin_relleno` | nombres a la izquierda, fila arrastrable y figura compacta sin barrita; PLC sin relleno. |
| S-REM06 | REQ-SIM-03, REQ-SIM-04 | pasa | `test_SREM06_play_stop_y_reiniciar_desde_es_por_boton_y_teclado` | E/S bloquea botones y atajos; los controles vuelven a funcionar en GRAFCET. |
| S-REM07 | REQ-EDT-09 | pasa | `test_SREM07_reiniciar_sigue_referencia_angular_y_tangente` | brazos horizontal y vertical iguales y simétricos respecto a la tangente de la referencia gráfica. |
| S-REM08 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SREM08_borde_activo_por_encima_en_qt_y_svg_ambos_ordenes_y_forzado` | borde compartido activo prioritario, también con forzado, sin cambiar anchos ni posiciones. |
| S-REM09 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SREM09_lima_actividad_texto_con_contraste_y_seleccion_azul` | lima en actividad y texto verdadero; la marca histórica conserva el verde oscuro legible. |
| S-RSL01 | REQ-DAT-02 | pasa | `test_SRSL01_resella_sin_cambiar_el_contenido_salvo_el_sello` | un archivo sellado con la clave de desarrollo se copia a sellados_1.0 con la clave real. |
| S-RSL02 | REQ-DAT-02 | pasa | `test_SRSL02_ya_sellado_para_la_distribucion_no_hace_nada` | con la clave real ya válida, se informa y no se escribe nada. |
| S-RSL03 | REQ-DAT-02 | pasa | `test_SRSL03_sello_no_valido_no_se_toca` | un sello válido con otra clave, o roto, no se resella ni se copia. |
| S-RSL04 | REQ-DAT-02 | pasa | `test_SRSL04_carpeta_no_recursiva_y_destino_existente_se_sustituye` | una carpeta aporta sus .grafnet directos; repetir sustituye la copia anterior. |
| S-RSL05 | REQ-DAT-02 | pasa | `test_SRSL05_clave_corta_se_rechaza_y_nunca_se_imprime` | la clave debe tener 32 bytes como mínimo y no aparece en la salida. |
| S-SAL01 | REQ-MOD-03, REQ-SIM-03 | pasa | `test_SSAL01_destino_activo_y_receptividad_no_colorean_retornos_no_validados` | no se propaga actividad desde la etapa destino; paridad real Qt/JS en tres ejemplos. |
| S-SAL02 | REQ-MOD-03, REQ-SIM-03 | pasa | `test_SSAL02_alternativas_no_invierten_el_sentido_de_los_enlaces` | rápida y marcha no llevan de E2 a E1; repetir sí, y E0 no salta a E3. |
| S-SAL03 | REQ-ACT-02, REQ-SIM-03 | pasa | `test_SSAL03_valor_actual_sobre_destino_asignacion_centrado_y_solo_lectura` | valor observado sobre la variable destino, centrado y tabular en Qt/JS, ausente en edición. |
| S-SAL04 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SSAL04_retornos_desde_derecha_rodean_condicion_y_banderita` | el retorno pasa por encima de las marcas y conserva su unión final, también con ruta manual. |
| S-SAL05 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SSAL05_convergencia_con_predecesores_debajo_sale_por_debajo_y_lleva_flecha` | los retornos hacia una sincronización no atraviesan etapas ni otras transiciones. |
| S-SAL06 | REQ-EDT-05, REQ-MOD-03 | pasa | `test_SSAL06_barra_y_no_representa_alternativas_bloqueo_y_deshacer` | Y con varias transiciones se diagnostica; Y agrupa las etapas de una sola transición, sin exigir pareja. |
| S-SAL07 | REQ-EDT-09, REQ-MOD-02 | pasa | `test_SSAL07_cadena_transiciones_bloquea_play_e_icono_alineado_al_zoom` | transiciones consecutivas bloquean Play; icono anclado al zoom con cualquier ancho de aviso. |
| S-SAL08 | REQ-EDT-09, REQ-MOD-03 | pasa | `test_SSAL08_y_invalida_bloquea_vista_y_play_senala_su_barra` | la barra Y inválida bloquea el simulador y Play y se puede localizar en el dibujo. |
| S-SAL09 | REQ-EDT-02, REQ-EDT-05 | pasa | `test_SSAL09_rodeo_de_marcas_conserva_arrastre_de_ruta_y_deshacer` | arrastrar los tres tiradores conserva la ruta manual y el rodeo, en una operación cada vez. |
| S-TEC01 | REQ-EDT-11 | pasa | `test_STEC01_cajetin_180_por_36_y_divisiones_en_los_tres_formatos` | cajetín propio fijo de 180×36, divisiones 20/18/22/30 y bloque inferior de 60 mm. |
| S-TEC02 | REQ-DAT-02, REQ-EDT-05, REQ-EDT-11 | pasa | `test_STEC02_hoja_vinculada_es_presentacion_y_deshacer_atomico` | crear y colocar una hoja no modifica el modelo y puede deshacerse. |
| S-TEC03 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_STEC03_primera_ejecucion_recupera_faltantes_sin_sobrescribir` | QStandardPaths localiza Documentos, crea la estructura y respeta modificaciones. |
| S-TEC04 | REQ-EDT-11 | pasa | `test_STEC04_default_a4_vertical_y_sin_a4_horizontal_en_preselecciones` | la creación ofrece A4 vertical por defecto y A3 en ambas orientaciones, sin preset A4 horizontal. |
| S-TEC05 | REQ-EDT-11 | pasa | `test_STEC05_pdf_vectorial_cotas_cajetin_y_rotulos_correctos` | el PDF conserva el cajetín 180×36 mm y las referencias sin rasterizar la plantilla propia. |
| S-TEC06 | REQ-EDT-11 | pasa | `test_STEC06_arrastrar_centrar_y_escalar_no_mueven_el_cajetin` | arrastrar y centrar el GRAFCET cambia solo su colocación en la zona libre. |
| S-TEC07 | REQ-DAT-02, REQ-EDT-11 | pasa | `test_STEC07_biblioteca_no_sobrescribe_ni_restaura_sin_permiso` | guardar y restaurar piden permiso y conservan el archivo si se cancela. |
| S-TEC08 | REQ-EDT-11, REQ-JER-05 | pasa | `test_STEC08_vinculo_refleja_nombre_posicion_y_contenido_jerarquico` | la hoja conserva IDs y vuelve a resolver geometría, rótulos y contenido de la selección. |
| S-TEC09 | REQ-EDT-11 | pasa | `test_STEC09_accion_seleccionada_sola_usa_el_mismo_fragmento_que_copiar` | una acción unida enviada sola conserva su dibujo como acción suelta, sin incluir su etapa. |
| S-TEC10 | REQ-EDT-01, REQ-EDT-05, REQ-EDT-11 | pasa | `test_STEC10_enviar_seleccion_crear_guardar_abrir_y_vincular` | el menú crea la hoja vinculada y esta se conserva dentro de .grafnet. |
| S-TEC11 | REQ-DAT-02, REQ-EDT-01 | pasa | `test_STEC11_guardar_por_defecto_en_documentos_grafcet` | Guardar como propone Documentos/GRAFCET Connect/GRAFCET, fuera de la instalación. |
| S-TEC12 | REQ-EDT-11 | pasa | `test_STEC12_centrar_recupera_una_colocacion_fuera_de_zona` | si al cambiar escala la colocación deja de caber, Centrar la recupera sin alterar la plantilla. |
| S-U03 | REQ-ACT-02, REQ-EVT-03 | pasa | `test_SU03_accion_por_evento_en_etapa_que_sale` | acción por evento en una etapa que sale con ese evento: no se ejecuta (comparador, 5.2 B). |
| S-U03 | REQ-EVT-03 | pasa | `test_SU03_flanco_sobre_variable_interna` | eventos internos estáticamente bloqueados (U-03). |
| S-U05 | REQ-ACT-05, REQ-SEM-09 | pasa | `test_SU05_receptividad_lee_valor_asignado` | hoja 08, 2.3 A; la receptividad ve el valor recién asignado y sigue en el mismo instante. |
| S-U05b | REQ-ACT-02, REQ-ACT-05 | pasa | `test_SU05b_asignaciones_sucesivas_vale_la_ultima` | hoja 08, 2.4 A; dos asignaciones distintas sucesivas en un instante, vale la última. |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_delay_cero` | los tiempos de 0 s se quitan (chat, 4.4 revisada): 0s/p es p y 0s/p/2s es p/2s, retardo a la desconexión puro. |
| S-U06 | REQ-TMP-03 | pasa | `test_SU06_lote_y_vencimiento_coincidentes` | lote y vencimiento independientes en el mismo τ se procesan juntos (comparador 4.3 A; cierra H-17). |
| S-U06 | REQ-SEM-08, REQ-TMP-03 | pasa | `test_SU06_vencimientos_que_dependen_del_orden` | vencimientos simultáneos con efecto mutuo (U-06). |
| S-U07 | REQ-MOD-04 | pasa | `test_SU07_fuente_de_nivel_y_transicion_sin_lados` | fuente de nivel y transición sin lados no compilan (comparador 6.2 A y 6.4 A); con «detener», U-07. |
| S-U09 | REQ-ACT-02, REQ-SEM-01, REQ-TMP-02 | pasa | `test_SU09_inicializacion_decidida` | hoja 08, 1.1 A, 1.2 A y 1.3 A (U-09 cerrada por el responsable). |
| S-UIV01 | REQ-ACT-01, REQ-SIM-03 | pasa | `test_SUIV01_acciones_reales_y_trazos_completos_con_inicial` | solo contribuciones reales; recuadros, texto, palito y banderita activos en lima. |
| S-UIV02 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SUIV02_transiciones_negras_simultaneidad_y_marca_historica_paridad` | negro inactivo, lima verdadero y verde oscuro última franqueada, también en barras Y. |
| S-UIV03 | REQ-ACT-02, REQ-EDT-09 | pasa | `test_SUIV03_banderita_identifica_accion_y_exige_evento_sin_elegir_flanco` | b no es un evento; error con variable y etapa, ayuda inmediata y modelo sin cambios implícitos. |
| S-UIV04 | REQ-EDT-07, REQ-EDT-10 | pasa | `test_SUIV04_selector_de_variable_en_caja_de_accion_con_popup_real` | selector con figura de acción conserva lista, teclado, variable elegida y deshacer. |
| S-UIV05 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SUIV05_panel_derecho_se_redimensiona_al_editar_y_simular` | divisor real habilitado en ambos modos; el panel izquierdo conserva su ancho. |
| S-UIV06 | REQ-EDT-09 | pasa | `test_SUIV06_incidencias_triangular_bajo_zoom_a_izquierda_del_texto` | icono rojo junto al texto, debajo del zoom, manteniendo clic en diagnóstico y espacios transparentes. |
| S-USO01 | REQ-ROB-01, REQ-SIM-03 | pasa | `test_SUSO01_tres_gestos_no_muestran_ventanas_sin_padre` | soltar variable, reducir canales y cerrar Configuración nunca muestran ventanas transitorias. |
| S-USO02 | REQ-EDT-09, REQ-SIM-03 | pasa | `test_SUSO02_rueda_no_edita_ningun_campo_de_configuracion` | la rueda ignora edición incluso con foco, sin quitar la edición por teclado. |
| S-USO03 | REQ-DAT-02, REQ-SIM-03 | pasa | `test_SUSO03_numericas_nuevas_100_y_escalas_guardadas_se_respetan` | las altas numéricas proponen 100 y guardar/abrir conserva incluso una escala explícita de 1. |
| S-USO04 | REQ-EDT-07, REQ-EDT-09 | pasa | `test_SUSO04_botones_variables_caben_con_su_texto` | la rejilla de dos columnas deja todo el texto visible con el ancho lateral habitual. |
| S-USO05 | REQ-DAT-02, REQ-EDT-01, REQ-SIM-03 | pasa | `test_SUSO05_salto_de_etapas_carga_integro_y_simula` | limpiar un huérfano no pierde entidades, G1 ni la posibilidad de simular. |
| S-VIS01 | REQ-EDT-02 | pasa | `test_SVIS01_inicial_solape_y_deshacer` | etapa inicial desde la paleta, sin permitir solapes y con deshacer. |
| S-VIS02 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SVIS02_simultaneidad_unica_crea_barras_Y` | la ficha única crea barras Y sin semántica nueva. |
| S-VIS03 | REQ-ACT-01, REQ-EDT-02 | pasa | `test_SVIS03_cinco_acciones_desde_paleta` | cada ficha crea el borrador de acción de su tipo. |
| S-VIS04 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SVIS04_encabezados_y_dependencias` | encabezados sin arrastre; dependencias accesible al editar y simular. |
| S-VIS05 | REQ-EDT-02, REQ-EDT-09 | pasa | `test_SVIS05_propiedades_compactas_y_divisor_manual_respetado` | sin selección se libera el lienzo; el reparto manual se conserva. |
| S-VIS06 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SVIS06_dos_decimales_sin_cambiar_lleva_ni_preset` | shown mantiene dos decimales al contar y vencer; la tabla conserva sus unidades. |
| S-VIS07 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SVIS07_digitos_tabulares_alineados_al_token_de_desconexion` | el tiempo sigue el extremo derecho del token de desconexión con dígitos tabulares. |
| S-VIS08 | REQ-EDT-02, REQ-JER-04 | pasa | `test_SVIS08_dependencias_por_esquinas_en_ocho_orientaciones_qt_y_js` | las dependencias unen las esquinas enfrentadas, superiores de E e inferiores de S; con empate horizontal conservan el trazado anterior. |
| S-VIS09 | REQ-SIM-03, REQ-TMP-01 | pasa | `test_SVIS09_js_usa_nth_y_token_sin_capsula` | JS sitúa el tiempo sobre la aparición exacta y ancla a izquierda o derecha según el retardo. |
| S-VIS10 | REQ-EDT-02, REQ-SIM-03 | pasa | `test_SVIS10_tiempo_receptividad_no_tapa_el_enlace_vertical` | el tiempo sobre el primer token deja libre el enlace vertical. |
| S-VIS11 | REQ-EDT-02 | pasa | `test_SVIS11_cajas_y_conectores_de_acciones_y_forzado_iguales` | las seis fichas comparten caja y trazo sin conector sin perder sus marcas distintivas. |
| S-VIS12 | REQ-EDT-02 | pasa | `test_SVIS12_solo_transicion_conserva_conectores_verticales` | etapas sin conectores y transición con conectores más largos y centrados. |
| S-VIS13 | REQ-EDT-02, REQ-JER-02 | pasa | `test_SVIS13_rotulo_del_parcial_corta_el_borde_inferior` | la G se monta sobre la línea inferior del marco y deja ver el fondo a sus lados. |
| S-VIS14 | REQ-EDT-02, REQ-MOD-03 | pasa | `test_SVIS14_ficha_unica_conserva_apertura_y_cierre_por_enlace` | una sola ficha con ayuda conserva los gestos de apertura y cierre de simultaneidad. |
| S-VIS15 | REQ-EDT-02, REQ-EDT-07 | pasa | `test_SVIS15_carpetas_por_uso_en_panel_y_ventana_ampliada` | el orden por uso es idéntico y cada carpeta sigue cargando sus bloques en ambos editores. |

## Revisión bidireccional del paquete

Referencias que el paquete declara en un solo sentido. No son errores: el documento 11 no exige simetría fila a fila. Se listan para que el revisor decida si deben completarse.

- **requisito→caso sin retorno** (20): REQ-SEM-04→T-04c, REQ-SEM-08→T-24a, REQ-EXP-01→T-09c, REQ-JER-01→T-04c, REQ-JER-07→T-24a, REQ-EDT-03→T-04c, REQ-EDT-09→T-09c, REQ-EDT-12→T-25a, REQ-SIM-02→T-10b, REQ-SIM-03→T-02a, REQ-SIM-03→T-02b, REQ-SIM-03→T-02c, REQ-SIM-05→T-04a, REQ-SIM-08→T-08a, REQ-SIM-08→T-08b, REQ-SIM-08→T-16a, REQ-DAT-04→T-23c, REQ-DAT-05→T-24b, REQ-ARQ-01→T-24a, REQ-ROB-01→T-08b
- **caso→requisito sin retorno** (23): T-01c→REQ-SEM-01, T-01c→REQ-ACT-02, T-01d→REQ-SEM-01, T-01d→REQ-MOD-04, T-03d→REQ-SEM-03, T-05b→REQ-EVT-03, T-06a→REQ-SEM-02, T-06a→REQ-SEM-04, T-06b→REQ-SEM-02, T-06b→REQ-SEM-04, T-06c→REQ-SEM-03, T-07a→REQ-ACT-01, T-07b→REQ-ACT-02, T-07c→REQ-ACT-02, T-12c→REQ-ACT-01, T-12e→REQ-TMP-02, T-12f→REQ-TMP-02, T-13d→REQ-TMP-02, T-13d→REQ-SEM-04, T-18e→REQ-JER-04, T-18e→REQ-ACT-02, T-23f→REQ-SIM-04, T-23f→REQ-DAT-04
- **caso inexistente** (0): ninguna
- **requisito inexistente** (0): ninguna
