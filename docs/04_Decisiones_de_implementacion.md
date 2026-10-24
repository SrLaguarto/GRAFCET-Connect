# 04. Decisiones de implementación y lecturas del paquete

Todas las decisiones de esta página son **P de implementación (P-IMP)**: rellenan huecos de producto que el paquete deja abiertos. Ninguna cierra una cuestión U. Cada una está pendiente de aceptación del responsable de producto y es reversible sin cambiar el significado normativo de nada.

## Decisiones P-IMP

| ID | Hallazgo | Decisión | Dónde | Cómo revertir |
|---|---|---|---|---|
| P-IMP-01 | H-01 | Códigos nuevos: D-ALTERNANCIA, D-NOMBRE-COLISION, D-JERARQUIA-INICIAL, D-ENTRADA-SIN-VALOR y D-CAPACIDAD-NO-SOPORTADA (este último separa «no implementado» de «bloqueado por U»). Los códigos citados fuera de 08 reciben la gravedad de su contexto | `grafcet/diagnostics.py` | Sustituir por los códigos que se ratifiquen |
| P-IMP-02 | H-06 | El escenario manda en el valor inicial de las entradas durante la ejecución; `initialValue` de una entrada es un valor por defecto de edición | `engine.initial_state` | Exigir igualdad o cambiar la fuente |
| P-IMP-03 | H-12 | Fichero «familia-hex(ID).json». Un ID de documento que no quepa en 255 bytes recibe D-ID. Los IDs de elementos conservan 1..128 | `ids.py`, `persistence.add_document` | Esquema de subdirectorios u otra codificación |
| P-IMP-04 | H-13 | El digest semántico incluye el significado y el **conjunto de IDs** vinculados, no los nombres de los vínculos | `model.semantic_projection` | Incluir nombres (renombrar crearía revisión) |
| P-IMP-05 | H-14 | Colección `draftLinks` para conexiones etapa→etapa o transición→transición: se guardan como borrador, se diagnostican con D-ALTERNANCIA y no son ejecutables | `editor.connect`, `model` | Rechazar la conexión sin guardarla |
| P-IMP-06 | H-15 | Sintaxis textual (ver la sección siguiente) | `expressions.py` | Ajustar el analizador; el significado no cambia |
| P-IMP-07 | H-16 | `minorAddsSemantics:false` para leer una versión menor desconocida; `revisionId` = «rev-» + 24 hexadecimales del digest semántico; traza JSON Lines con línea de cierre; guardado con diario `commit.json`; recuperación en `.recuperacion/` | `persistence.py`, `trace.py`, `model.compute_revision` | Otro identificador de revisión u otro contenedor |
| P-IMP-08 | — | Deshacer y rehacer guardan los documentos anterior y posterior, sin copiarlos otra vez, porque el editor nunca modifica sus documentos en el sitio. Las operaciones de vista solo copian la presentación | `editor._txn` | Historial por diferencias si las ediciones semánticas grandes lo exigen (`07_Medicion_indicativa.md`) |
| P-IMP-09 | — | Límites internos: profundidad JSON 2·64+32 (derivada de la profundidad de expresión 64 del documento 10; con 128 se rechazaba un modelo válido, error detectado por T-25a); 100 000 lotes; hasta 4 vencimientos simultáneos comparados por permutación (más → bloqueo U-06); instantánea cada 100 contextos; espacio de traza comprobado antes de abrir un contexto | `canonical.py`, `scenario.py`, `engine.py` | Ajustar constantes; actualizar perfil y pruebas |
| P-IMP-10 | — | Una entrada manual crea un lote en el τ actual, con el ordinal siguiente a todos los lotes de ese τ, y queda registrada | `engine.Session.manual_input` | Permitir elegir τ ≥ actual |
| P-IMP-11 | H-04 | «Estado declarado de prueba» solo para la batería (ficha común de 11); se marca `origin=declarado-prueba` y no es inicialización normativa | `engine.declared_state` | — |
| P-IMP-12 | — | Las variables de tipo duración no son negativas (0..2^63−1). Las coordenadas son decimales de presentación con 3 decimales | `values.py`, `editor._coord` | — |
| P-IMP-13 | — | Disparadores de activación y desactivación sin condición adicional (`acciones.activacion-condicionada`, no soportada); `sourceRefs` vacío o igual a la propia etapa; una referencia a una transición → U-03 | `model.validate_model` | Admitir condición cuando se cierre U-05 |
| P-IMP-14 | H-21 | Campo opcional `limitUs` en la acción continua para la acción limitada: el diccionario de 09 no tiene dónde guardar esa duración | `model`, `engine.compute_outputs` | Representación que se ratifique en U-11 |

## Sintaxis textual propuesta (P-IMP-06)

| Elemento | Forma | Ejemplo |
|---|---|---|
| Duración | número con punto decimal + `us`/`µs`/`ms`/`s`, en µs exactos; nunca se redondea | `2 s`, `1.5 s`, `1500 ms`, `10 us` |
| Entrada regional | solo en la interfaz: «1,25 s» (es-ES) o «1.25 s» (en-US) → 1250000 µs canónicos | `parse_duration(texto, "es-ES")` |
| Nombre con espacios o reservado | entre acentos graves | `` `depósito lleno` `` |
| Referencia calificada | `Parcial.nombre` cuando el nombre corto es ambiguo | `G1.A` |
| Palabras clave | `NOT AND OR true false`, sensibles a mayúsculas | — |
| Literales numéricos | sin unidad; compatibles con la unidad del otro operando | `L > 5` con L en m |
| Mezcla de tipos | entero con decimal (entre variables), booleano con número → D-TIPO; unidades distintas → D-UNIDAD; producto o cociente de dos magnitudes con unidad → D-UNIDAD (no soportado) | — |
| División | resultado decimal exacto; solo asignable a decimal, y solo si es representable en su escala | `a / b` |
| Disparador de evento | debe ser falso sin eventos: `rise`/`fall`, AND con algún operando de evento, OR de operandos de evento | `rise(p) AND q` |

## Lecturas del paquete aplicadas (no son decisiones nuevas)

Se indican para que el revisor compruebe que la lectura es la que pretendía el paquete.

| ID | Lectura | Fundamento | Prueba |
|---|---|---|---|
| L-01 | Las salidas continuas de la situación efectiva usan la memoria resultante del contexto | 04, tabla de causalidad, fila «Situación efectiva siguiente» | T-07a, T-14a |
| L-02 | Una acción por evento se ejecuta una vez en la primera evolución si su etapa estaba activa en la situación estable anterior y no cambia de actividad en el contexto. En otro caso, D-SEM-PENDIENTE (U-03/U-05) | 05 tabla de eventos; T-15b | T-15b, S-U03 |
| L-03 | En las evoluciones posteriores de un contexto, una receptividad con evento se evalúa con el evento presente y ausente. Si ambas lecturas coinciden, el resultado no depende de U-03 y se acepta; si difieren, se bloquea | 04 «no rellenar con un orden fijo»; T-10c (I) frente a T-10d (B) | T-10c, T-10d, T-10e |
| L-04 | Varios vencimientos en el mismo τ forman una sola frontera (T-13d), pero solo se aceptan si todos los órdenes de aplicación dan el mismo estado | 05; 12 riesgo «comparación entre permutaciones» | T-13d, S-U06 |
| L-05 | La duración de una etapa inicial cuenta desde τ=0 | Oráculos T-12a, T-12c, T-12f, T-13d (tensión H-02) | T-12a, T-12c |
| L-06 | Durante el recorrido, la validación y las lecturas de actividad usan la situación virtual vigente | 04 «situación global coherente»; T-06b | T-06b |
| L-07 | T-12a: S={B} tras el contexto de 2000000 µs y en 2000001 µs | 05 «verdadero desde t0+d» (H-11) | T-12a |
| L-08 | Un propietario contradictorio (referencias redundantes distintas) es D-FORMATO. D-PROPIETARIO queda para la propiedad múltiple | 09 «referencias redundantes … o se rechaza el documento»; T-22b frente a T-18c | T-22b, T-18c, T-19c |
