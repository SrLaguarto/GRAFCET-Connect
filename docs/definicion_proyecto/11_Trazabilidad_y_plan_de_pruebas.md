# 11. Trazabilidad y plan de pruebas

Versión 0.1 · Estado: pruebas diseñadas; ninguna prueba de software ejecutada.

## Propósito y convenciones

Relacionar fuente, requisito y oráculo. Fuentes según [02](02_Fuentes_normativas_y_clean_room.md); definiciones de [03](03_Modelo_conceptual_y_notacion.md), semántica de [04](04_Semantica_de_evolucion.md), [05](05_Receptividades_eventos_tiempo_y_acciones.md) y [06](06_Estructuracion_y_jerarquias.md); decisiones y U en [12](12_Decisiones_pendientes_y_traspaso.md). ENC §§15–16 exige esta matriz. Abiertos: todas las U relevantes; no se mide cobertura por cantidad de títulos.

Estado de oráculo: I = concreto provisional, pendiente de contraste; P = concreto de producto, pendiente de futura ejecución; B = bloqueado por U, se ofrecen alternativas discriminantes, ninguna aceptada. N no se usa en esta edición por U-01. Una fila puede tener una parte P verificable (diagnóstico) y una parte semántica B: no se confunden.

Ficha común de caso: modelo mínimo declarado en la fila; las entidades no nombradas no existen; etapas simples salvo indicación; entradas booleanas inicialmente false salvo valor indicado; sin acciones, temporizadores ni jerarquías salvo indicación. Tiempo inicial 0; estímulo ordinario a 1 s salvo otra marca. No hay estímulos implícitos. {…} denota conjunto; A→B / p significa transición con Pre={A}, Post={B}, receptividad p, y nombre indicado. Si faltan salidas/eventos/diagnósticos en un caso ordinario, se esperan conjuntos vacíos, no «cualquier resultado». Estado previo puede ser una instantánea de prueba declarada; no obliga a afirmar que ese estado es inicial normativo. Comparación exige todos los datos de la fila y los invariantes aplicables, sin prioridades de orden dentro de conjuntos.

Las filas de pruebas documentales/editor tienen como entrada un documento y una operación, no un estímulo de simulación. Su resultado debe comprobarse mediante diferencias de datos y operaciones observables; no se exige inventar eventos GRAFCET.

## Matriz de fundamento normativo y cobertura

Localizadores de LOC leídos en el archivo aportado; no se presentan como verificación de copia íntegra oficial. «Contenido normativo» describe la naturaleza aparente del apartado; la clase del requisito sigue siendo I/U. Los detalles de fuente, idioma y acceso están en 02.

| Localizador / naturaleza | Materia | Requisitos | Diseño | Casos / cobertura actual |
|---|---|---|---|---|
| IEC-CAT; UNE-CAT / catálogo | Edición y equivalencia | REQ-NOR-01,02 | 01,02 | T-22e, R-01; metadatos verificados |
| LOC §§3,4.3 / definiciones | Entidades y roles | REQ-MOD-01,05, REQ-EXP-01 | 03,05 | T-09, T-21; parcial I/P |
| LOC §4.4 / normativo | Alternancia | REQ-MOD-02 | 03 | T-21b; provisional I |
| LOC §4.5.2 / normativo | Situación inicial | REQ-SEM-01 | 04 | T-01; I, U-09 |
| LOC §4.5.3 / normativo | Validación y receptividad | REQ-SEM-02 | 04 | T-02; I |
| LOC §4.5.4 / normativo | Cambio conjunto | REQ-SEM-03 | 04 | T-03; I |
| LOC §4.5.5 / normativo | Simultaneidad | REQ-SEM-04 | 04 | T-04,T-06; I |
| LOC §4.5.6 / normativo | Permanencia activa | REQ-SEM-05 | 04 | T-05; I para actividad, B para eventos |
| LOC §§4.6,4.7 / normativo; tabla 4 [15],[16] | Eventos externos/internos | REQ-EVT-01,03, REQ-SEM-09 | 05 | T-10,T-11; parcial I/U |
| LOC §§4.8.2,4.9.4; tabla 5 [20]–[25] | Continuas y tiempo | REQ-ACT-01, REQ-TMP-02 | 05 | T-07,T-12,T-14; I y fronteras U |
| LOC §§4.8.3,4.9.5; tabla 6 [26]–[29] | Memoria y transitorios | REQ-ACT-02,05, REQ-SEM-06 | 04,05 | T-07,T-15; I/U |
| LOC §4.10.5 y nota 1 / regla y nota separadas | Conflictos y modos | REQ-ACT-03,04 | 05 | T-16; I/P; nota no elevada a N |
| LOC tabla 1 [1]–[6] | Etapas y variantes | REQ-MOD-07, REQ-SEM-01 | 03,06 | T-01,T-18,T-19; parcial |
| LOC tablas 2–3 | Transición, barras, enlaces | REQ-MOD-03,06 | 03,07 | T-03,T-04,T-21; I/P |
| LOC tabla 4 [13],[14],[19] | Condiciones/predicados | REQ-EXP-01, REQ-MOD-05 | 05 | T-09; parcial |
| LOC tabla 4 [17],[18]; tabla 5 [23]–[25] | Temporización | REQ-TMP-02,03 | 05 | T-12,T-13; I/U |
| LOC tabla 7 / representación | Comentarios | REQ-EDT-11, REQ-DAT-02 | 03,07,09 | T-21h,T-22a; parcial |
| LOC §§6.2.1–6.2.8 | Secuencias, selección, saltos, paralelismo | REQ-SEM-02,03,04 | 03,04 | T-03,T-04,T-06; parcial |
| LOC §§6.3.1–6.3.4 | Fuentes y sumideros | REQ-MOD-04 | 03,04 | T-03c,T-10e; U-07 en variantes |
| LOC §7.2; tabla 8 | Partición y actividad | REQ-JER-01 | 06 | T-20b; I |
| LOC §7.3; tabla 9 | Forzado | REQ-JER-02,03,06 | 06 | T-17,T-20; parcial I/U |
| LOC §7.4; tabla 10 | Encapsulación | REQ-JER-05,06 | 06 | T-19,T-20; parcial I/U |
| LOC §7.5; tabla 11 | Macroetapas | REQ-JER-04,06 | 06 | T-18,T-20; parcial I/U |
| LOC anexos A,B / informativos | Ejemplos industriales | Sin requisitos derivados de sus instalaciones | 02 | No reutilizados; ejemplos propios |
| LOC anexo C / informativo | Otros lenguajes | REQ-ALC-02 | 01 | No aplicable al desarrollo pedido; no equivalencias |

La cobertura completa requerirá contrastar obligación por obligación, incluidas variantes y notas pertinentes; esta tabla no afirma que se haya cerrado todo §5 por listar sus tablas.

## T-01 a T-08: evolución

| Caso | Requisitos / fuente de matriz | Modelo, inicio y estímulo | Oráculo y criterio exacto | Estado |
|---|---|---|---|---|
| T-01a | SEM-01 | A y C iniciales; B ordinaria; sin transiciones. Iniciar | S={A,C}; B inactiva; sin franqueamientos | I |
| T-01b | SEM-01 | Mismo modelo con orden de archivo B,C,A | Igual T-01a; ninguna selección de «primera» | I |
| T-01c | SEM-01, ACT-02 | A inicial, memoria n; restaurar snapshot n=7 y después reiniciar | Restaurar conserva 7; reiniciar n=0; traza nueva. Activaciones iniciales U-09 | P/I parcial |
| T-01d | SEM-01, MOD-04 | Sin iniciales y sin fuente; después variante con transición fuente | No inventar etapa inicial; comportamiento de la variante queda U-07 | B |
| T-02a | SEM-02 | t:A→B / p; S=vacío; p pasa a true | E=vacío; S sigue vacío; receptividad true, validación false | I |
| T-02b | SEM-02 | Mismo t; S={A}, p=false; observar | E=vacío; S={A}; validación true, receptividad false | I |
| T-02c | SEM-02 | Mismo t; S={A}; p:0→1 | E={t}; S={B}; sin posibilidad de diferir hasta otro escaneo | I |
| T-03a | SEM-03 | t:{A}→{B,C}/p; S={A}; p:0→1 | Un E={t}; S′={B,C}; no estado efectivo con solo B o solo C | I |
| T-03b | SEM-03 | t:{A,B}→{C,D}/p; S={A,B}; p:0→1 | S′={C,D}; A y B salen conjuntamente | I |
| T-03c | SEM-03, MOD-04 | t:{A}→vacío/p; S={A}; p:0→1 | E={t}; S′=vacío; una etapa sumidero B sin salidas permanece si ya activa | I |
| T-03d | SEM-03 | S={A}; t:A→C/p; u:A→B/q; v:B→C/r; p,q,r=false; B continua y; p sube@1 | B no activa ni contribuye; E={t}; C activa; y=false | I |
| T-04a | SEM-04 | t:A→B/p; u:C→D/p; S={A,C}; p:0→1 | E={t,u}; S′={B,D}; un conjunto simultáneo | I |
| T-04b | SEM-04 | t:A→B/p; u:A→C/q; S={A}; lote p=q=true | E={t,u}; S′={B,C}; no exclusión automática | I |
| T-04c | SEM-08, MOD-06 | Repetir T-04b con coordenadas, etiquetas, orden y reparto de parciales equivalentes modificados | Mismos conjuntos de IDs y valores; etiquetas mapeadas no participan en comparación | P |
| T-05a | SEM-05 | t:A→B/p; u:B→C/p; S={A,B}; p:0→1; C sumidero | Primera evolución E={t,u}; B permanece activa en frontera colectiva; S′={B,C}. Cierre posterior se evalúa aparte | I |
| T-05b | SEM-05, EVT-03 | T-05a con acciones n:=n+1 al activar B y m:=m+1 al desactivar B | No asumir dos cambios de actividad por el primer E; resultado completo de memorias U-04 | B |
| T-06a | SEM-02,04 | t:{B,C}→{D}/p; S={B}; p=true; sin otros hechos | E=vacío, D inactiva; falta C | I |
| T-06b | SEM-02,04 | t:{B,C}→D/r; S={B,E}; u:E→C/q; r=true,q=false; q:0→1 | Recorrido u seguido t; S final {D}; B espera hasta C; τ no cambia en recorrido | I |
| T-06c | SEM-03 | A→{B,C}/p; B→D/q; C→E/r; {D,E}→F/s. Inicial A; p@1,q@2,r@3,s@4 verdaderos | Situaciones {B,C},{D,C},{D,E},{F}; sin sincronizar al llegar solo D | I |
| T-07a | SEM-06, ACT-01 | t:A→B/p; u:B→C/true; S={A}; B continua y; p:0→1 | Recorrido t,u; S efectiva final {C}; y=false antes/después; ningún pulso efectivo | I |
| T-07b | SEM-06, ACT-02 | T-07a, B memorizada z:=true al activar; z inicial false | z final true; virtualidad de B conservada en evidencia | I |
| T-07c | SEM-06, ACT-02 | T-07a, B memorizada z:=true al desactivar; z=false | z final true; evento virtual de salida no eliminado | I |
| T-08a | SEM-07, ROB-01 | A→B/true; B→A/true; presupuesto 20 para prueba | D-LIM-EVOL; τ=0; no resultado estable; evidencia de recorrido y límite | P |
| T-08b | SEM-07 | A→B/p; A inicial; p=false; horizonte 10 s | Espera estable sin D-LIM-EVOL; no confundir ausencia de evolución con divergencia | P |

Los prefijos abreviados de esta tabla y las siguientes corresponden a REQ-: por ejemplo SEM-01 significa REQ-SEM-01. No crean nuevos identificadores.

## T-09 a T-16: expresiones, eventos, tiempo y acciones

| Caso | Requisitos | Modelo/estado y estímulo | Oráculo exacto o alternativa pendiente | Estado |
|---|---|---|---|---|
| T-09a | EXP-01 | a=true,b=false,c=false; expresión a OR b AND c | true; (a OR b) AND c=false; textos conservan significado distinto | P |
| T-09b | EXP-01, EDT-07 | Comparar longitud en m con temperatura en °C; escribir true en entero | D-UNIDAD / D-TIPO; no inicio ni conversión | P |
| T-09c | MOD-05, DAT-08 | Receptividad «depósito preparado» sin meaning; luego texto p con meaning NOT p | D-EXP-PENDIENTE; luego D-EXP-DIVERGENTE; guardar conserva datos | P |
| T-09d | EXP-02, SIM-06 | Estado fijo n=4; observar condición n>3 cien veces | n=4, mismo Z, ningún evento ni avance temporal | P |
| T-10a | EVT-01 | A→B/rise(p), A inicial, p inicial true; después p=false@1 y true@2 | No flanco al arrancar; fall@1 sin t; rise@2 con E={t}, S={B} | I |
| T-10b | EVT-01,02 | p=1,q=0; observar rise(p OR q); lote p=0,q=1@1 | Ningún flanco de p OR q. Variante dos lotes p=0 y q=1@1: fall y rise ordenados | I/P |
| T-10c | EVT-01 | t:A→B/rise(p); u:C→A/q; S={C}; p,q=false; p sube@1, q sube@2 | No t@1; u@2 deja A activa; no t@2 por el flanco antiguo; se requiere nuevo descenso/subida de p | I |
| T-10d | EVT-03, SEM-09 | t:A→B/rise(p); u:B→C/rise(p); S={A}; p sube | Alternativas B o C; U-03 decide alcance del flanco, no el software | B |
| T-10e | EVT-01, MOD-04 | Fuente t:vacío→A/rise(p), fuente u:vacío→B/rise(p); p sube | Ambas reciben el mismo evento y E incluye t,u; repetición en contexto U-07 debe cerrarse | I/B parcial |
| T-11a | EVT-03 | T-05b, observar cambio de actividad y franqueamientos separadamente | E contiene t,u en primera evolución; no equivaler evento de u a caída de B; detalles U-04 | B |
| T-11b | EVT-03, SEM-09 | A→B/p; B→C/true; acción dependiente de evento de franqueamiento de primera transición | Determinar contexto de evaluación/representación del evento; U-03/U-05 | B |
| T-12a | TMP-02 | A estable desde 0; t:A→B/delay(2 s,active(A),0) | A a 1999999 µs; t a 2000000; B a 2000001; sin cuantización por escaneo | I |
| T-12b | TMP-02 | delay(2 s,p,0), p sube@1, cae@2, sube@3 | Nunca true en primer pulso; false hasta 5 s, true en 5 s si p sostenida | I |
| T-12c | TMP-02, ACT-01 | A inicial con continua y limitada 2 s; sin salidas de A | y=true en 0 y 1999999 µs, false en 2000000. Variante duración cero: siempre false | I |
| T-12d | TMP-01 | Introducir 0,1 µs; tiempo negativo; tiempo 2^63 µs | Cada uno rechazado con rango/precisión; 1 µs aceptado exactamente | P |
| T-12e | TMP-02 | delay(1,5 s,p,2 s); p sube@2, cae@8 | false antes 3,5; true en 3,5 y hasta antes 10; false en 10 s | I |
| T-12f | TMP-02 | A inicial; A→B/p, B→A/q; continua y en A retardada 3 s; p sube@2, baja@2,5; q sube@4 y baja@4,5 | Primer tramo no activa y; reentrada inicia duración nueva; y=true desde 7 s si A permanece activa | I |
| T-13a | EVT-02 | Dos escrituras p=false y p=true en un lote @1 | D-LOTE; variante lotes ordinal 0 y 1 aceptada y conservada como secuencia | P |
| T-13b | TMP-03 | t:A→B/delay(2 s,p,0); A activa,p=true desde 0; p cae exactamente@2 | Franquea o cancela según regla por verificar; U-06; ningún orden accidental | B |
| T-13c | TMP-03 | delay(1 s,p,2 s); p sube@0, cae@3, sube@4 | U-06: cancelar caída pendiente o mantenerla; observar valor@5 y nuevo plazo | B |
| T-13d | TMP-02, SEM-04 | S={A,C} activas desde 0; t:A→B/delay(2 s,active(A),0); u:C→D/delay(2 s,active(C),0); sin otros hechos | E={t,u} a 2000000 µs, S′={B,D}; ambos vencimientos pertenecen a la misma frontera | I |
| T-14a | ACT-01 | A y B activas; A contribuye y con p=false, B con q=true | y=true; retirar B deja y=false; no «última acción gana» | I |
| T-14b | ACT-01 | A activa contribuye y con p; p:0→1→0 en lotes @1,@2 | y:false→true→false, sin memoria después de @2 | I |
| T-14c | ACT-01 | Acción continua condicionada por rise(p); luego variante etapa virtual T-07a | Primera inválida D-TIPO-EVENTO; segunda sin pulso efectivo | I |
| T-15a | ACT-02 | A→B/p; B→C/q; B z:=true al activar; z=false; p@1,q@2 | z=true desde @1 y permanece al salir B@2 | I |
| T-15b | ACT-02 | A permanece activa; acción sobre rise(p) asigna n:=n+1; p sube@1, baja@2, sube@3 | n=1 tras @1 y @2; n=2 tras @3; no repeticiones por renderizado | I |
| T-15c | ACT-05, SEM-09 | Acciones simultáneas x:=y e y:=x; x=2,y=5 | (5,2) frente a (5,5)/(2,2) distinguen lecturas; U-05 impide elegir | B |
| T-16a | ACT-03 | Dos acciones simultáneas z:=1 y z:=2 | D-ESCRITURA-CONFLICTO con ambos autores/valores; no z final arbitrario | P |
| T-16b | ACT-03 | Dos acciones simultáneas z:=2 | z=2 y ambos autores en registro; contraste semántico pendiente | I |
| T-16c | ACT-04 | Misma salida y en continua de A y memorizada de B | D-MODO-SALIDA al validar aunque etapas no coincidan en escenario | I |
| T-16d | ACT-05 | n=0; dos acciones simultáneas n:=n+1 | U-05: n=1, n=2 o conflicto; no resolver con orden de archivo | B |

## T-17 a T-20: jerarquías

| Caso | Requisitos | Modelo/estado y estímulo | Oráculo | Estado |
|---|---|---|---|---|
| T-17a | JER-02 | Superior H activa; orden explícita inferior G={B}; inferior inicialmente A, t:B→C/p; p=true | G mantiene {B}, t no franquea mientras H activa; repetir con empty produce vacío y initial produce inicial de G | I |
| T-17b | JER-02 | Orden current entra con G={A,B}; entradas cambian y después se retira | Durante orden {A,B} constante; retirada libera desde esa situación, no desde anterior inventada; efectos coincidentes U-08 | I/B parcial |
| T-17c | JER-03 | H1 y H2 imponen G={A} y G={B} simultáneamente | D-FORZADO-CONFLICTO con orígenes y conjuntos; no prioridad visual | P |
| T-17d | JER-03 | Forzado G1→G2 y G2→G1; variante G1→G1 | D-JERARQUIA-CICLO con camino; no inicio | P |
| T-18a | JER-04 | A→M/p; expansión E→K/q, K→S/r; M→B/s; s=true | p activa E; q activa K sin salida externa; r activa S y habilita salida a B; XM no sustituye S | I |
| T-18b | JER-04 | Expansión E→S/true; llegada a M por p; salida a B/true | Recorrido virtual de expansión; B efectivo; acciones según T-07; reentrada por nuevo ciclo activa E | I |
| T-18c | JER-04, MOD-07 | Dos macros comparten expansión; variante M contiene macro N con expansión propia | Primera D-PROPIETARIO; segunda conserva identidad y navegación. Recursión M→N→M rechazada | P/I |
| T-18d | JER-06 | Expansión con rama K aún activa cuando S habilita salida externa | U-08: no borrar K por analogía con llamada; documentar validez y efectos | B |
| T-18e | JER-04, ACT-02 | A→M/p; expansión E→S/q; M→A/r; E asigna n:=n+1 al activar; n=0; p@1 y baja@1,5; q@2 y baja@2,5; r@3 y baja@3,5; p@4 | E se activa en ambas llegadas; n=1 tras primera y n=2 tras segunda; no reinicialización de memoria por reentrada. Confirmar U-08 antes de cerrar | I/B parcial |
| T-19a | JER-05 | H inicial; recinto R con I inicial y K de activación; arranque, salida de H@1 y reentrada@2 | Inicio {H,I}; salida R vacío; reentrada {H,K}; no restaurar I | I |
| T-19b | JER-05 | H contiene R1 con K y R2 con L marcadas; K encapsula R3 con N marcada | Entrada H activa K,L,N según anidamiento; salida H desactiva todos los descendientes | I |
| T-19c | JER-05, MOD-07 | Mismo recinto con dos encapsulantes; variante hijo inicial con cadena superior no inicial | Primer error de propietario; segundo diagnóstico de coherencia inicial; no completar padre sin aviso | I/P |
| T-20a | JER-06, TMP-03 | H contiene A; A vence a 2 s; H se desactiva exactamente a 2 s | U-08/U-06: registrar alternativas de evento/acción antes de oráculo definitivo | B |
| T-20b | JER-01 | Parciales G1,G2 con transiciones independientes T-04a; cambiar orden y vista de parciales | Misma E y S; actividad XG derivada de sus miembros | I/P |
| T-20c | JER-06 | H inactiva; orden externa pretende activar A dentro de H; variante forzar vacío con H activa | U-08: conflicto con invariantes de recinto; no admitir resultado contradictorio silencioso | B |

## T-21 a T-26: producto

| Caso | Requisitos | Entrada/operación | Resultado y criterio de aprobación | Estado |
|---|---|---|---|---|
| T-21a | ALC-01, EDT-01 | Crear proyecto, parcial, guardar, cerrar, reabrir y duplicar | Original conserva IDs y datos; duplicado tiene IDs nuevos sin referencias al original | P |
| T-21b | MOD-01,02, EDT-02,09 | Conectar A directamente con B; referencia a ID inexistente; identidad duplicada | Diagnósticos separados con elemento; borrador guardable y simulación bloqueada | P/I |
| T-21c | MOD-03, EDT-02,03 | Cruzar dos líneas y mover/alinear nodos | Sin cambios en Pre/Post; deshacer recupera presentación | P |
| T-21d | MOD-06, EDT-06,07 | Renombrar variable p a marcha y etapa A a Inicio | Referencias por ID conservadas, usos actualizados, traza equivalente; colisión informa sin cambiar ID | P |
| T-21e | EDT-04, DAT-01 | Copiar A,t,B con referencia externa a variable global p | IDs nuevos internos; p mantenida solo como vínculo explicitado; alternativa pendiente bloquea inicio | P |
| T-21f | EDT-05 | Borrar encapsulante y contenido con dependencias; deshacer/rehacer | Restauración exacta de todos los IDs y relaciones en un paso; fallo de operación no deja eliminación parcial | P |
| T-21g | EDT-08,12, JER-07 | Plegar jerarquía con hijo activo y error interior; buscar hijo | Resumen indica actividad/error; navegación revela hijo sin alterar Z | P |
| T-21h | EDT-11 | Exportar modelo con enlace interrumpido y comentario Unicode | Símbolos y textos legibles, destino identificable, revisión indicada, sin cambio semántico | P |
| T-22a | DAT-02 | Guardar y abrir modelo con jerarquía, texto descriptivo, notas y vista | Igual significado y datos admitidos; comparación canónica semántica igual | P |
| T-22b | DAT-01, MOD-01 | Archivo con referencia rota, propietario contradictorio o clave duplicada | D-REF/D-ID/D-FORMATO; ningún reemplazo por etiqueta coincidente | P |
| T-22c | DAT-03 | Formato mayor desconocido; campo semántico desconocido; extensión descriptiva desconocida | Los dos primeros no ejecutables ni sobrescritos; extensión descriptiva preservada opaca | P |
| T-22d | DAT-07, EDT-10, ROB-02 | Interrumpir guardado de revisión nueva a mitad; abrir recuperación | Versión anterior íntegra o nueva íntegra, nunca mezcla; recuperación separada, sin sobrescritura silenciosa | P |
| T-22e | NOR-01, DAT-03 | Migrar formato; cambiar edición normativa; aplicación nueva | Copia e informe en migración; edición no cambia automáticamente; tres versiones independientes | P |
| T-22f | DAT-04, SIM-04 | Restaurar instantánea con otra revisión o perfil; luego origen exacto | Primera rechazada sin mutar sesión; segunda reproduce valores, eventos y plazos | P |
| T-22g | DAT-08, SIM-05 | Truncar última línea/registro o alterar digest; conservar prefijo válido | D-INTEGRIDAD, traza marcada truncada; no afirmación de ejecución completa | P |
| T-23a | SIM-01,03 | Pausa antes de E={t,u}; avanzar evolución simultánea | Ambos franquean en misma frontera; estados de validación/receptividad diferenciados | P |
| T-23b | SIM-01,06, ARQ-01, SEM-08 | Mismo escenario continuo, por microavances y con puntos de interrupción | Misma traza semántica y Z final; solo difiere presentación de pausas | P |
| T-23c | SIM-02,04 | A con retardo de 5 s; snapshot estable@2; continuar/restaurar | Vence@5 lógico en ambas ejecuciones; entrada manual registrada se reproduce igual | P |
| T-23d | EDT-14 | Cambiar receptividad durante ejecución y después mover etapa | Semántica genera revisión nueva y no altera ejecución anterior; movimiento mantiene revisión ejecutada | P |
| T-23e | SIM-07 | En pausa estable n=2, depuración lo cambia a 9 | Nueva rama, antes=2/después=9, intervención explícita; no transición ficticia | P |
| T-23f | SIM-04, DAT-04 | T-07b pausado en frontera explicativa entre t y u; guardar estado y restaurar en perfil que admita esa fase | Igual C, φ, memoria, eventos y tiempo al continuar; z final true, sin repetir acción ya registrada. Si fase no exportable, D-INSTANTANEA-FASE y ningún archivo declarado exacto | P |
| T-24a | PLT-01, DAT-05 | Catálogo cerrado idéntico en tres sistemas admitidos | Iguales conjuntos, tiempos, valores y diagnósticos semánticos; sin comparar duración real | P |
| T-24b | PLT-02, TMP-01 | Región es-ES/en-US; duración 1,25 s introducida por interfaz local | Archivo almacena 1250000 µs; mismo resultado, sin coma decimal canónica | P |
| T-24c | PLT-02 | Ruta «Ensayo ñ», etiquetas Unicode y IDs A/a | Abre/guarda sin pérdida ni confusión por mayúsculas del sistema | P |
| T-24d | PLT-03, ALC-01 | Desconectar red tras instalación; ciclo crear/guardar/simular/exportar | Todas operaciones básicas disponibles y reproducibles | P |
| T-24e | PLT-03 | Instalar, actualizar y revertir versión admitida | Proyectos previos conservados; incompatible se informa, no se migra silenciosamente | P |
| T-25a | PLT-04, ROB-01 | Modelos en cada límite de 10 y uno por encima; caso combinado | Dentro: medir; fuera: rechazo controlado antes de pérdida; sin promesa de tiempos hasta equipo U-10 | P |
| T-25b | DAT-06, ROB-02 | Campo con script, operador desconocido, referencia fuera de raíz | No ejecuta ni accede; diagnóstico y documento anterior intacto | P |
| T-25c | DAT-06, ROB-02 | Profundidad 65, referencias cíclicas de expresión y documento corrupto | Rechazo finito con motivo; no bloqueo indefinido de interfaz | P |
| T-25d | PLT-04 | 100 operaciones de vista y cinco cargas/validaciones del modelo de referencia | Informe p95, mediana, máximo y memoria, equipo/versiones; comparar objetivos de 10 | P |
| T-26a | EDT-13 | Solo teclado: crear etapa/transición, conectar, editar, validar, ejecutar, pausar y guardar | Todas operaciones alcanzables; foco visible; sin trampas de foco | P |
| T-26b | EDT-13 | Vista sin color, 200 % y acceso mediante lista estructural | Activa/inicial/transitoria/forzada distinguibles; etiquetas/relaciones disponibles; sin controles inaccesibles | P |

## Invariantes y pruebas de propiedades

1. Integridad: toda referencia resuelve a una identidad del tipo y ámbito correcto; ninguna etapa duplicada en S.
2. Presentación: permutar coordenadas, orden de colecciones y etiquetas con referencias conservadas mantiene trazas, excepto campos puramente descriptivos.
3. Simultaneidad: una permutación de miembros de E no produce situaciones efectivas intermedias.
4. Reproducción: misma revisión, perfil, Z inicial y lotes implica misma secuencia canónica de observables definidos.
5. Observación: activar monitores, ampliar o pausar no modifica valores ni causa eventos.
6. Persistencia: ida y vuelta preserva significado; snapshot+continuación equivale a continuar desde Z cuando el perfil está cerrado.
7. Jerarquía: no hay hijos activos bajo encapsulante inactiva ni propiedad múltiple; las excepciones por forzado requieren resolución, no violación silenciosa.
8. Tiempo: dentro de evolución transitoria τ no aumenta para estabilizar; ordenar eventos realmente secuenciales sí puede cambiar resultado y no es un metamorfismo válido.

## Revisión bidireccional de requisitos de producto

Cada fila de requisitos de 01–10 incluye pruebas; cada fila de caso anterior señala sus requisitos. Los requisitos CR-01 a CR-04 y ALC-02,03/NOR-02 se revisan documentalmente, no mediante un motor.

| Revisión | Entrada | Criterio / requisitos |
|---|---|---|
| R-01 | Los doce documentos, ENC y fuentes registradas | Cada requisito tiene clase, fuente, prueba y estado; U críticas visibles; ningún oráculo basado en producto ajeno; NOR-02, ALC-03, CR-01, CR-04 |
| R-02 | Paquete de transferencia y procedencia | Exactamente doce Markdown; sin código de aplicación, scripts, ejecutables, activos ni copias de fuentes; ALC-02, CR-02, CR-03 |

## Resultado de revisión documental

La revisión confirma separación entre requisitos P y semántica I/U, cobertura de las 26 familias y existencia de casos discriminantes para pendientes críticos. No confirma cumplimiento de las 13 puertas de aceptación del encargo: faltan contraste normativo completo, resolución de U y mediciones. Los modelos mínimos se expresan como datos/tablas originales; no son pruebas ejecutables. La futura implementación deberá aportar archivos de caso, resultados y trazas, conservar diferencias y registrar cualquier cambio de oráculo antes de aceptarlo.
