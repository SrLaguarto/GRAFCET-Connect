"""Clasificación de los 82 requisitos frente a las cuestiones U y estado de implementación.

Categorías:
  IMPL-P    Implementable sin U e implementado (decisión P; oráculo P ejecutable).
  IMPL-I    Implementado como perfil PROVISIONAL (I): no depende de U-03..U-11 en lo
            implementado, pero U-01 impide promoverlo a N o declararlo conforme.
  PARCIAL   Parte implementada y verificada; el resto depende de U, de la interfaz o de
            una iteración posterior (se indica).
  IMPL-DEC  Requisito U cuya cuestión cerró el responsable (hoja 08): implementado según su decisión;
            sigue siendo provisional hasta el contraste normativo (U-01).
  BLOQ-U    Requisito U: solo se implementa el bloqueo diagnosticado (D-SEM-PENDIENTE).
  PEND-ITER Implementable como I/P, pendiente de la siguiente iteración (estructura hecha).
  PEND-UI   Requiere la interfaz gráfica (no iniciada).
  PEND-PLT  Requiere matriz de sistemas, empaquetado o equipo de referencia (U-10).
  DOC       Revisión documental (R-01/R-02); con apoyo automatizado cuando se indica.
"""

CATEGORIAS = {
    "IMPL-P": "Implementado (P), verificable ya",
    "IMPL-I": "Implementado como provisional (I; U-01)",
    "PARCIAL": "Parcial",
    "IMPL-DEC": "Implementado según decisión del responsable (U cerrada; contraste U-01 pendiente)",
    "BLOQ-U": "Bloqueado por U (bloqueo implementado)",
    "PEND-ITER": "Pendiente de iteración (estructura hecha)",
    "PEND-UI": "Pendiente de interfaz",
    "PEND-PLT": "Pendiente de plataforma (U-10)",
    "DOC": "Revisión documental",
}

# id: (categoría, módulos, nota)
REQ = {
    "REQ-NOR-01": ("IMPL-P", "profile, persistence, declaration", "Base normativa declarada en el manifiesto; ejes de versión separados; no se sustituye silenciosamente"),
    "REQ-NOR-02": ("IMPL-P", "declaration", "La declaración excluye toda materia con U crítica y nunca afirma conformidad; R-01 sigue siendo documental"),
    "REQ-ALC-01": ("PARCIAL", "editor, persistence, engine", "Ciclo principal sin servicios de terceros verificado sin interfaz (T-24d); falta la interfaz"),
    "REQ-ALC-02": ("DOC", "tools/comprobar_paquete.py", "Parte automatizable de R-02: el paquete conserva exactamente los doce Markdown con sus huellas"),
    "REQ-ALC-03": ("IMPL-P", "profile, declaration", "Cada capacidad marcada provisional / no soportada con su motivo"),
    "REQ-CR-01": ("DOC", "tools/paquete.py", "Las fuentes y localizadores se conservan en el paquete; la matriz enlaza cada requisito con su documento"),
    "REQ-CR-02": ("DOC", "—", "Esta implementación se ha hecho solo con el paquete; ver declaración de procedencia en README"),
    "REQ-CR-03": ("DOC", "—", "No se ha detectado contaminación; procedimiento descrito en README"),
    "REQ-CR-04": ("DOC", "tests", "Ningún oráculo procede de otro producto; los oráculos son los del documento 11"),
    "REQ-MOD-01": ("IMPL-P", "model, persistence", "IDs únicos, propietario y referencias existentes; duplicados/huérfanos impiden simular"),
    "REQ-MOD-02": ("IMPL-I", "model, editor", "D-ALTERNANCIA; enlaces etapa→etapa como borrador (P-IMP-05)"),
    "REQ-MOD-03": ("IMPL-P", "editor", "Solo se conecta por operación explícita; la geometría no crea relaciones"),
    "REQ-MOD-04": ("IMPL-DEC", "model, engine", "Sumideros I. U-07 cerrada por el responsable (comparador, 27-10-2026, P-IMP-22): fuente por evento una vez por flanco (6.3 A); sin etapas iniciales, fuente de nivel y transición sin lados no compilan (6.1 A, 6.2 A, 6.4 A)"),
    "REQ-MOD-05": ("IMPL-P", "model, expressions, editor", "Texto libre conservado como descriptivo; D-EXP-PENDIENTE localizado"),
    "REQ-MOD-06": ("IMPL-P", "model, editor, engine", "Renombrar, mover u ordenar no cambia observables ni revisión semántica (H-13)"),
    "REQ-MOD-07": ("IMPL-I", "model, hierarchy", "Propiedad única de expansiones y recintos; recursión rechazada; la estructura se ejecuta (P-IMP-23)"),
    "REQ-SEM-01": ("PARCIAL", "engine", "Situación inicial explícita y su cierre causal en τ=0: acciones al activar las iniciales, evolución inicial y temporizadores desde τ=0 (hoja 08, 1.1–1.4, P-IMP-19). Inicio vacío: no compila (6.1 A, P-IMP-22). Abierto: iniciales dentro de jerarquías (U-08)"),
    "REQ-SEM-02": ("IMPL-I", "engine", "Validación y receptividad; imposición jerárquica pendiente de iteración"),
    "REQ-SEM-03": ("IMPL-I", "engine", "Cambio conjunto de precedentes y siguientes"),
    "REQ-SEM-04": ("IMPL-I", "engine", "Conjunto simultáneo completo; sin prioridad por orden"),
    "REQ-SEM-05": ("IMPL-DEC", "engine", "Actividad I. Efectos decididos por el responsable (comparador, 27-10-2026, P-IMP-22): en permanencia o reactivación no se ejecutan acciones al activar ni al desactivar y la duración sigue (3.1 A, 3.2 A, 3.3 A; cierra H-05)"),
    "REQ-SEM-06": ("IMPL-I", "engine", "Etapas inestables sin pulso continuo; memorizadas conservadas; eventos en el recorrido según la lectura 5.1 (P-IMP-22)"),
    "REQ-SEM-07": ("IMPL-P", "engine", "D-LIM-EVOL recuperable, τ sin avanzar, sin falsa estabilidad (T-08a con su oráculo original desde la respuesta 1.2 A; S-08a)"),
    "REQ-SEM-08": ("IMPL-P", "engine, trace", "Mismos observables con independencia de recorrido, geometría y control; entre sistemas: U-10"),
    "REQ-SEM-09": ("IMPL-DEC", "engine", "U-05 (P-IMP-20) y U-03, U-04, U-06, U-07 (comparador, 27-10-2026, P-IMP-22) cerradas por el responsable; cada lectura sigue siendo seleccionable, «detener» incluida (P-IMP-15, P-IMP-21). Siguen deteniéndose los eventos internos y de franqueamiento (U-03), 0s/p/d2 y los vencimientos que dependen del orden (U-06)"),
    "REQ-EXP-01": ("IMPL-P", "expressions, values", "Tipos exactos, unidades, precedencia; sintaxis de literales P-IMP-06"),
    "REQ-EXP-02": ("IMPL-P", "expressions, engine", "Evaluación pura"),
    "REQ-EVT-01": ("IMPL-I", "engine", "Flancos sobre entradas en la 1.ª evolución; sin retención ni consumo exclusivo"),
    "REQ-EVT-02": ("IMPL-P", "scenario", "Lotes simultáneos frente a lotes ordenados; D-LOTE"),
    "REQ-EVT-03": ("PARCIAL", "model, engine", "Evento en el recorrido: lectura «situación anterior» por defecto; acciones por evento solo si la etapa estaba activa y no sale con él (comparador, 27-10-2026, 5.1–5.3, P-IMP-22; H-23). Eventos internos y de franqueamiento: U-03, bloqueados"),
    "REQ-TMP-01": ("IMPL-P", "timeutil, values", "µs exactos, rango 0..2^63-1, sin redondeo"),
    "REQ-TMP-02": ("IMPL-I", "engine, model", "delay ordinario, limitadas, retardadas; duración de etapa inicial según T-12a/T-12c (H-02); salida y reentrada en el mismo instante sin interrumpir la duración (P-IMP-18); bases compuestas no soportadas (H-09)"),
    "REQ-TMP-03": ("PARCIAL", "engine, model", "Decidido (comparador, 27-10-2026, P-IMP-22): caída en el vencimiento → primero el vencimiento (4.1 A); rebote → sigue verdadera (4.2 A); lote y vencimiento independientes → juntos (4.3 A; cierra H-17); 0s/p no compila (4.4 B). Siguen en U-06: 0s/p/d2 y vencimientos simultáneos que dependen del orden"),
    "REQ-ACT-01": ("IMPL-I", "engine", "Disyunción sobre situación efectiva; una salida continua leída en una expresión vale según la situación del momento (comparador, 8.2 C; cierra H-10)"),
    "REQ-ACT-02": ("IMPL-I", "engine", "Memorizadas por activación, desactivación y evento, también virtuales"),
    "REQ-ACT-03": ("IMPL-P", "model, engine", "D-ESCRITURA-CONFLICTO con autores y valores, sin prioridad oculta; un conflicto seguro impide compilar (P-IMP-16) y el resto se detiene en ejecución"),
    "REQ-ACT-04": ("IMPL-I", "model", "D-MODO-SALIDA en validación"),
    "REQ-ACT-05": ("IMPL-DEC", "engine, model", "Hoja 08, 2.1 C, 2.2 B, 2.3 A, 2.4 A y 2.5 A (P-IMP-20): conflicto si dos escriben a la vez, dependencia cruzada no compila, lo asignado se ve en el mismo instante y vale la última asignación"),
    "REQ-JER-01": ("PARCIAL", "engine, model", "Partición sin orden y XG de parciales sin hijos; anidados: H-08"),
    "REQ-JER-02": ("IMPL-I", "hierarchy, engine", "Forzado explícito, actual (captura), vacío e inicial; el destino no evoluciona mientras está vigente; la retirada libera desde la situación resultante (documento 06, P-IMP-23). Momento, temporizadores, recintos y acciones: U-08 (7.2–7.4, 7.8)"),
    "REQ-JER-03": ("IMPL-P", "model, hierarchy", "Ciclos D-JERARQUIA-CICLO; conflicto posible avisado al validar y detenido al ejecutar (D-FORZADO-CONFLICTO) sin prioridad por ID"),
    "REQ-JER-04": ("IMPL-I", "model, hierarchy, engine", "Relación expandida: llegar activa la entrada, salir exige la salida; XM por la expansión; reentrada sin borrar memorias (P-IMP-23). Ramas residuales: U-08 (7.5). Iniciales en la expansión: se admiten (7.7 A, P-IMP-24)"),
    "REQ-JER-05": ("IMPL-I", "model, hierarchy", "Al arrancar, iniciales; al reentrar, enlaces de activación; al salir, se desactivan todos los descendientes (P-IMP-23). Encapsulante en permanencia: el contenido se mantiene (comparador, 3.4 A)"),
    "REQ-JER-06": ("IMPL-DEC", "hierarchy", "Cerradas por el responsable: 7.2 B, 7.3 A, 7.4 C, 7.5 A, 7.6 B, 7.7 A y 7.8 A (P-IMP-24 a P-IMP-26). Vaciar por forzado un recinto con su encapsulante activa no se preguntó y se detiene (U-08)"),
    "REQ-JER-07": ("PEND-UI", "—", "Plegado y navegación pertenecen a la vista"),
    "REQ-EDT-01": ("PARCIAL", "editor, persistence", "Crear, abrir, guardar y duplicar sin interfaz; diálogo de cierre con cambios pendiente de interfaz"),
    "REQ-EDT-02": ("IMPL-P", "editor", "Insertar, conectar, editar; borrador inválido guardable"),
    "REQ-EDT-03": ("PARCIAL", "editor", "Mover, alinear, distribuir y deshacer; zoom y desplazamiento pendientes de interfaz"),
    "REQ-EDT-04": ("IMPL-P", "editor", "Copiar/pegar con IDs nuevos y decisión explícita de referencias externas"),
    "REQ-EDT-05": ("IMPL-P", "editor", "Transacciones atómicas; fallo fuera del historial; rehacer descartado"),
    "REQ-EDT-06": ("IMPL-P", "editor", "Renombrar sin cambiar ID, usos actualizados, colisión diagnosticada, búsqueda con ruta"),
    "REQ-EDT-07": ("IMPL-P", "editor", "Diccionario de variables y usos afectados por un cambio"),
    "REQ-EDT-08": ("PEND-UI", "—", "Navegación jerárquica"),
    "REQ-EDT-09": ("IMPL-P", "diagnostics", "Código, gravedad, elemento, evidencia y corrección; foco en interfaz pendiente"),
    "REQ-EDT-10": ("IMPL-P", "persistence", "Recuperación separada cada 30 s si hay cambios, sin sobrescritura"),
    "REQ-EDT-11": ("PEND-UI", "—", "Exportación SVG/PDF no implementada en esta iteración"),
    "REQ-EDT-12": ("PEND-UI", "—", "Diagramas extensos: vista general, zoom y filtros"),
    "REQ-EDT-13": ("PEND-UI", "—", "Teclado y accesibilidad"),
    "REQ-EDT-14": ("IMPL-P", "editor, engine", "Edición semántica = revisión nueva; la ejecución conserva la suya"),
    "REQ-SIM-01": ("IMPL-P", "engine", "Estados de sesión, pausas en frontera completa, microavance, puntos antes/después"),
    "REQ-SIM-02": ("IMPL-P", "scenario, engine", "Escenarios y entradas manuales registradas con origen y ordinal"),
    "REQ-SIM-03": ("IMPL-P", "engine", "Observación de actividad, validación, receptividad y franqueamiento"),
    "REQ-SIM-04": ("IMPL-P", "engine", "Instantánea con Z completo y compatibilidad exacta; dentro de recorrido D-INSTANTANEA-FASE"),
    "REQ-SIM-05": ("IMPL-P", "trace", "Traza con conjuntos E, causas, cierre y digest"),
    "REQ-SIM-06": ("IMPL-P", "engine", "Observar y pausar no modifican comportamiento"),
    "REQ-SIM-07": ("IMPL-P", "engine", "Intervención E en pausa estable, rama auditable"),
    "REQ-SIM-08": ("IMPL-P", "diagnostics, engine", "Evidencia y corrección recomendada en cada diagnóstico"),
    "REQ-DAT-01": ("IMPL-P", "model, persistence, ids", "Identidades, referencias y propiedad; nombres hexadecimales (H-12)"),
    "REQ-DAT-02": ("IMPL-P", "persistence", "Ida y vuelta conserva significado, notas y vista (formato 0.1 provisional, U-11)"),
    "REQ-DAT-03": ("IMPL-P", "persistence", "Versión mayor/menor, desconocidos y migración con copia e informe"),
    "REQ-DAT-04": ("IMPL-P", "engine", "Instantánea íntegra y compatibilidad exacta; campos U no aplicables declarados"),
    "REQ-DAT-05": ("IMPL-P", "canonical, timeutil", "Representación canónica y SHA-256 independientes de región"),
    "REQ-DAT-06": ("IMPL-P", "canonical, persistence, expressions", "Sin código ejecutable, sin rutas fuera de raíz, límites previos"),
    "REQ-DAT-07": ("IMPL-P", "persistence", "Guardado atómico con diario; recuperación del último válido"),
    "REQ-DAT-08": ("IMPL-P", "model, trace", "Divergencia texto-significado y trazas truncadas"),
    "REQ-ARQ-01": ("IMPL-P", "todo el núcleo", "Todo el contrato se verifica sin interfaz (esta batería)"),
    "REQ-PLT-01": ("PEND-PLT", "trace", "Trazas canónicas deterministas en Windows; comparación en macOS/Linux pendiente (U-10)"),
    "REQ-PLT-02": ("PARCIAL", "timeutil, persistence", "Región, Unicode, rutas y mayúsculas verificados en Windows; otros sistemas U-10"),
    "REQ-PLT-03": ("PARCIAL", "todo el núcleo", "Sin conexión verificado; instalación y actualización pendientes de empaquetado"),
    "REQ-PLT-04": ("PARCIAL", "model, persistence, tools/medir_presupuestos.py", "Límites aplicados; medición indicativa, no ratificada (U-10)"),
    "REQ-ROB-01": ("IMPL-P", "model, engine, persistence", "Límites de datos y de evolución diagnosticados sin alterar significado"),
    "REQ-ROB-02": ("IMPL-P", "persistence, canonical", "Archivos fallidos preservan la última revisión válida y no ejecutan cargas"),
}

# Casos con tratamiento distinto de «se ejecuta su oráculo». (tipo, explicación)
#   bloqueo-U        el caso es B o lo toca una U: se verifica la detención con la U correcta
#   parcial          se ejecuta la parte determinada; el resto queda bloqueado o pendiente
#   decision         caso U del documento 11 (oráculo B) cuya cuestión cerró el responsable en la hoja 08: la
#                    prueba comprueba la alternativa elegida, no un oráculo del paquete
#   no-impl-bloqueo  capacidad no implementada en esta iteración: se verifica que no se ejecuta
#   no-ejecutado     no hay prueba en esta iteración (interfaz, plataforma, medición)
CASOS = {
    "T-01c": ("oraculo", "restaurar y reiniciar; las acciones al activar las iniciales ya se ejecutan (1.1 A)"),
    "T-01d": ("decision", "comparador, 27-10-2026, 6.1 A: sin etapas iniciales no compila; no se inventa etapa inicial. Con «detener», U-07"),
    "T-05b": ("decision", "comparador, 27-10-2026, 3.1 A: la permanencia no ejecuta acciones (no se asumen dos cambios de actividad); p sigue a 1 y u vuelve a franquear en la evolución siguiente. Con «detener», U-04"),
    "T-08a": ("oraculo", "oráculo original ejecutable desde la respuesta 1.2 A de la hoja 08 (cierra H-03)"),
    "T-10d": ("decision", "comparador, 27-10-2026, 5.1: lectura «situación anterior», de las alternativas del caso (B o C) queda en B. Con «detener», U-03"),
    "T-10e": ("decision", "parte I: E={t,u} con el mismo evento; repetición decidida (comparador, 27-10-2026, 6.3 A): una vez por flanco. Con «detener», U-07"),
    "T-11a": ("decision", "E={t,u} en la primera evolución; la permanencia de B no ejecuta acciones (comparador, 27-10-2026, 3.1 A). Con «detener», U-04"),
    "T-11b": ("bloqueo-U", "U-03"),
    "T-12a": ("oraculo", "duración de etapa inicial según el oráculo (H-02); lectura de «B a 2000001» (H-11)"),
    "T-12c": ("oraculo", "duración de etapa inicial según el oráculo (H-02)"),
    "T-13b": ("decision", "comparador, 27-10-2026, 4.1 A: primero el vencimiento, franquea (también con p verdadera desde el arranque, 1.3 A). Con «detener», U-06"),
    "T-13c": ("decision", "comparador, 27-10-2026, 4.2 A: la nueva subida anula la desconexión; verdadera a 5 s sin nuevo plazo. Con «detener», U-06"),
    "T-14c": ("oraculo", "segunda parte = T-07a"),
    "T-15c": ("decision", "decisión 2.2 B de la hoja 08: dependencia cruzada, no compila; en ejecución se detiene. "
              "El error no está entre las lecturas (5,2), (5,5) y (2,2) que lista el caso"),
    "T-16d": ("decision", "decisión 2.1 C de la hoja 08: de las alternativas del caso (n=1, n=2 o conflicto), conflicto"),
    "T-17a": ("oraculo", "forzado explícito, vacío e inicial (P-IMP-23)"),
    "T-17b": ("parcial", "captura, mantenimiento y retirada verificados (I); los efectos coincidentes quedan decididos (7.2 B, 7.8 A) pero el caso no los ejercita"),
    "T-17c": ("oraculo", "conflicto avisado al validar y detenido al ejecutar, sin prioridad"),
    "T-18a": ("oraculo", "entrada, salida y XM (P-IMP-23)"),
    "T-18b": ("oraculo", "recorrido virtual de la expansión y reentrada (P-IMP-23)"),
    "T-18c": ("oraculo", "estructura: propiedad, anidamiento y recursión"),
    "T-18d": ("decision", "comparador 27-10-2026, 7.5 A: se desactivan todas las etapas de la expansión. Con «detener», U-08"),
    "T-18e": ("parcial", "parte I verificada: E en cada llegada, n=1 y n=2 sin reinicio de memoria (P-IMP-23); el caso pide confirmar U-08 antes de cerrar"),
    "T-19a": ("oraculo", "inicio por iniciales, salida y reentrada por enlace de activación (P-IMP-23)"),
    "T-19b": ("oraculo", "activación anidada y desactivación de descendientes (P-IMP-23)"),
    "T-20a": ("decision", "chat 27-10-2026, 7.6 B: primero actúa lo interior y después se desactiva H. Con «detener», U-08"),
    "T-20c": ("decision", "comparador 27-10-2026, 7.4 C: el forzado se ignora con la encapsulante inactiva. Vaciar un recinto activo no se preguntó y sigue detenido (U-08)"),
    "T-21a": ("parcial", "sin interfaz: el diálogo de cierre con cambios queda pendiente"),
    "T-21g": ("no-ejecutado", "requiere interfaz gráfica"),
    "T-21h": ("no-ejecutado", "exportación SVG/PDF no implementada en esta iteración"),
    "T-24a": ("parcial", "determinismo verificado en Windows; comparación entre sistemas pendiente de U-10"),
    "T-24c": ("parcial", "verificado en Windows (NTFS, insensible a mayúsculas); otros sistemas U-10"),
    "T-24d": ("parcial", "núcleo sin acceso de red; la exportación no existe aún"),
    "T-24e": ("no-ejecutado", "instalación, actualización y reversión: empaquetado pendiente de U-10"),
    "T-25a": ("parcial", "límites y rechazo controlado verificados; medición de tiempos pendiente de U-10"),
    "T-25d": ("no-ejecutado", "requiere equipo de referencia (U-10); medición indicativa en tools/medir_presupuestos.py"),
    "T-26a": ("no-ejecutado", "requiere interfaz gráfica"),
    "T-26b": ("no-ejecutado", "requiere interfaz gráfica"),
}
