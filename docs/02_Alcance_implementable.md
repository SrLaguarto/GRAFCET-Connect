# 02. Alcance implementable sin cuestiones U (propuesta para cerrar U-12)

Documento **generado** por `tools/generar_trazabilidad.py` desde `spec/clasificacion.py`.

U-12 corresponde al responsable del proyecto: esta lista es una **propuesta** de subconjunto aprobable, con sus restricciones, y no modifica el manifiesto del paquete. Ningún elemento de la lista constituye conformidad.

## Criterio

- **P sin U**: implementable y verificable ya con oráculo P.
- **I sin U propia**: implementable como perfil provisional. U-01 impide promoverlo a N, pero el oráculo I es concreto, así que implementarlo no resuelve ninguna U.
- **Depende de U**: solo se implementa la detención diagnosticada. La implementación nunca elige una alternativa; si todas las lecturas posibles dan el mismo observable, el resultado no depende de la U y se acepta.
- **Decidido por el responsable**: la U la cerró el responsable de producto (hoja 08 o comparador). Se implementa su respuesta como lectura por defecto, provisional hasta el contraste normativo (U-01); «detener» sigue siendo seleccionable.
- **Pendiente**: implementable, pero fuera de esta iteración (interfaz, plataforma, ejecución jerárquica).

## Recuento

| Categoría | Nº | Requisitos |
|---|---|---|
| Implementado (P), verificable ya | 41 | REQ-ACT-03, REQ-ALC-03, REQ-ARQ-01, REQ-DAT-01, REQ-DAT-02, REQ-DAT-03, REQ-DAT-04, REQ-DAT-05, REQ-DAT-06, REQ-DAT-07, REQ-DAT-08, REQ-EDT-02, REQ-EDT-04, REQ-EDT-05, REQ-EDT-06, REQ-EDT-07, REQ-EDT-09, REQ-EDT-10, REQ-EDT-14, REQ-EVT-02, REQ-EXP-01, REQ-EXP-02, REQ-MOD-01, REQ-MOD-03, REQ-MOD-05, REQ-MOD-06, REQ-NOR-01, REQ-NOR-02, REQ-ROB-01, REQ-ROB-02, REQ-SEM-07, REQ-SEM-08, REQ-SIM-01, REQ-SIM-02, REQ-SIM-03, REQ-SIM-04, REQ-SIM-05, REQ-SIM-06, REQ-SIM-07, REQ-SIM-08, REQ-TMP-01 |
| Implementado como provisional (I; U-01) | 11 | REQ-ACT-01, REQ-ACT-02, REQ-ACT-04, REQ-EVT-01, REQ-MOD-02, REQ-MOD-07, REQ-SEM-02, REQ-SEM-03, REQ-SEM-04, REQ-SEM-06, REQ-TMP-02 |
| Parcial | 11 | REQ-ALC-01, REQ-EDT-01, REQ-EDT-03, REQ-EVT-03, REQ-JER-01, REQ-JER-03, REQ-PLT-02, REQ-PLT-03, REQ-PLT-04, REQ-SEM-01, REQ-TMP-03 |
| Implementado según decisión del responsable (U cerrada; contraste U-01 pendiente) | 4 | REQ-ACT-05, REQ-MOD-04, REQ-SEM-05, REQ-SEM-09 |
| Bloqueado por U (bloqueo implementado) | 1 | REQ-JER-06 |
| Pendiente de iteración (estructura hecha) | 3 | REQ-JER-02, REQ-JER-04, REQ-JER-05 |
| Pendiente de interfaz | 5 | REQ-EDT-08, REQ-EDT-11, REQ-EDT-12, REQ-EDT-13, REQ-JER-07 |
| Pendiente de plataforma (U-10) | 1 | REQ-PLT-01 |
| Revisión documental | 5 | REQ-ALC-02, REQ-CR-01, REQ-CR-02, REQ-CR-03, REQ-CR-04 |

## Restricciones de la propuesta

1. Perfil `grafcet-impl-provisional`: ninguna capacidad «aprobada»; las I son provisionales.
2. Formato 0.1 implementado como provisional hasta que se ratifique U-11.
3. La duración de una etapa inicial cuenta desde τ=0 según T-12a/T-12c (tensión H-02). Si el revisor normativo extiende U-09 a este caso, la capacidad `temporal.duracion-etapa-inicial` pasa a no soportada.
4. La coincidencia de lote y vencimiento sigue la respuesta del responsable (comparador 4.1 A y 4.3 A, P-IMP-22; cierra H-17). Los vencimientos simultáneos que dependen del orden siguen bloqueados (U-06).
5. La ejecución jerárquica (forzado, macroetapas, encapsulación) es la siguiente iteración. Su estructura ya se edita, guarda y valida (discriminante de U-12).

Responsables según el paquete: decisiones P → responsable de producto; I/U → revisor normativo; evidencia → segunda IA y revisor de pruebas.

