# 08. Simulador, trazas y diagnóstico

Versión 0.1 · Estado: interfaz de ejecución P especificada; núcleo sujeto a I/U.

## Propósito y referencias

Hacer reproducible la observación. Dependencias: [04](04_Semantica_de_evolucion.md), [05](05_Receptividades_eventos_tiempo_y_acciones.md), [06](06_Estructuracion_y_jerarquias.md), [09](09_Datos_y_contratos.md). Fuente de producto: ENC §12. Cuestiones: U-03 a U-09 en comportamiento; U-10 en capacidad. No se permite seleccionar un perfil «conforme» mientras estén abiertas las cuestiones que utiliza.

## Controles y estados de sesión

P: estados de sesión preparada, ejecutando, pausada estable, pausada en recorrido, detenida, finalizada y error. Estable/transitoria describe la semántica; ejecutando/pausada describe el control. No deben confundirse.

| Operación | Precondición | Resultado observable |
|---|---|---|
| Iniciar | Revisión, perfil y escenario válidos, sin U requerida | Nueva ejecución identificada, inicialización registrada y evaluación inicial definida por perfil |
| Pausar | Ejecutando | Suspensión en frontera completa; no partir un conjunto simultáneo |
| Continuar | Pausada y Z íntegro | Retoma mismo contexto, memorias y reloj; no reenvía estímulos consumidos |
| Reiniciar | Sesión existente | Nueva ejecución con escenario inicial; conserva traza anterior |
| Detener | Sesión activa | Cierra registro con motivo; conserva observación y posibilidad de guardar |
| Avanzar un evento externo | Pausa estable | Aplica siguiente lote y su cierre causal; si hay vencimientos anteriores se presentan primero, sin saltarlos |
| Avanzar una evolución simultánea | Pausa en frontera compatible | Un conjunto E completo del recorrido explicativo; no una transición elegida arbitrariamente |
| Avanzar hasta estabilización | Contexto causal abierto | Cierra el contexto o detiene por diagnóstico; no avanza tiempo para resolverlo |
| Avanzar hasta tiempo t | t ≥ τ y pausa | Procesa todos los hechos anteriores y en t; se detiene antes si hay error o interrupción |
| Observar estado histórico | Traza disponible | Muestra datos previos sin ejecutar hacia atrás ni modificar Z actual |
| Reanudar desde historia | Instantánea suficiente compatible | Nueva rama de ejecución con vínculo al origen; no se inventan memorias desde S |

Un punto de interrupción sobre t se refiere al franqueamiento de t dentro del conjunto E: la pausa se produce antes o después del conjunto completo, según la opción registrada. Antes del conjunto no se considera ya franqueada ninguna de sus integrantes. Un punto por variable observa cambios, no añade acciones.

## Escenarios e intervenciones

Un escenario fija revisión, perfil, valores de entrada iniciales, lotes con tiempos/ordinales, horizonte y condición de parada. Las condiciones de parada son observadores puros. El horizonte en t incluye los hechos en t; las ambigüedades semánticas de esos hechos deben estar resueltas antes de ejecutar.

Las entradas manuales quedan convertidas en lotes con marca de tiempo lógico y origen manual. Las escrituras sobre memoria son una extensión de depuración E: solo en pausa estable, con antes/después, autor local, motivo y ejecución derivada. La edición manual del conjunto de etapas se reserva a intervención E con validación jerárquica y queda fuera de recorridos normativos. No se registra un franqueamiento para justificar un salto manual.

Modo ligado al reloj real: opcional E. Cuando el equipo se retrase, conserva orden y tiempos lógicos programados, informa retraso de presentación y no salta eventos. Las entradas interactivas se fijan en el momento lógico de aceptación y quedan registradas; la reproducción usa el registro, no la velocidad original. Aleatoriedad opcional: semilla y método identificados, nunca oráculo normativo.

## Observables mínimos

Para cada transición: precedentes y su actividad, valor de receptividad, validación, pertenencia al conjunto franqueado y posible inhibición por forzado. Una receptividad true con precedente inactivo no se pinta como franqueada. Para cada etapa: actividad efectiva, participación virtual si corresponde, inicialidad y ruta. Para cada salida: modo, valor y contribuciones/autores. Temporizadores: condición base, origen, vencimiento y cancelación. Forzados: origen, destino y objetivo. Diagnósticos: código, gravedad, evidencia y relación causal.

La explicación de una conjunción falsa puede señalar todos sus operandos falsos; la de una expresión compuesta debe reflejar su estructura. No atribuye un «culpable único» si hay varias explicaciones. Evaluar para mostrar estas razones no altera eventos ni memorias.

## Traza

P: cabecera con ID de ejecución, revisión semántica, escenario, perfil, unidad temporal y límites. Cada registro contiene secuencia monótona, tiempo lógico, índice de lote y evolución explicativa, contexto causal, estado previo/posterior o referencia a instantánea, entradas cambiadas, conjunto E, eventos, propuestas y cambios de variables, salidas efectivas, forzados y diagnósticos. El conjunto E puede ordenarse por ID para mostrarlo; ese orden no es causal.

Se registra instantánea completa al iniciar, en cada frontera estable que se guarde explícitamente y cada 100 contextos causales completos. Entre ellas, cambios con referencia al estado anterior. Guardar una pausa dentro de un recorrido requiere Z completo incluido C y φ. Si el perfil no puede exportarlo, se rechaza esa operación con D-INSTANTANEA-FASE y se conserva ejecución; no se guarda una instantánea incompleta.

Traza final incluye número esperado de registros, estado de cierre y digest de integridad de contenido. Un archivo sin cierre válido se marca truncado; puede consultarse su prefijo verificado, pero no demuestra finalización. Reproducir requiere modelo, escenario y perfil; verificar una traza compara observables canónicos. Importar solo una traza no demuestra que su motor haya sido correcto.

## Requisitos

| ID | Clase/prioridad | Obligación | Pruebas |
|---|---|---|---|
| REQ-SIM-01 | P/crítica | Controles deben obedecer fronteras y estados anteriores, sin subdividir simultaneidad | T-23a,b |
| REQ-SIM-02 | P/crítica | Escenarios y entradas manuales deben ser reproducibles y mantener origen y agrupación | T-10b, T-23c |
| REQ-SIM-03 | P/alta | Observación debe distinguir actividad, validación, receptividad y franqueamiento | T-02a,b,c, T-23a |
| REQ-SIM-04 | P/crítica | Instantánea y restauración deben conservar Z y comprobar compatibilidad antes de modificar sesión | T-23c, T-22f |
| REQ-SIM-05 | P/crítica | Traza debe registrar conjuntos simultáneos, causas y pérdida de integridad | T-04a, T-22g |
| REQ-SIM-06 | P/crítica | Observadores e interrupciones no deben modificar comportamiento ni consume-eventos | T-09d, T-23b |
| REQ-SIM-07 | P/crítica | Intervenciones deben separarse de evolución normativa y crear registro auditable | T-23e |
| REQ-SIM-08 | P/alta | Diagnóstico debe preservar evidencia suficiente y recomendar una acción concreta | T-08a,b, T-16a |

## Catálogo de diagnósticos

| Código | Gravedad y efecto | Evidencia / corrección |
|---|---|---|
| D-REF, D-ID | Error de documento; no inicio | ID y campo afectados; reparar referencia o identidad |
| D-TIPO, D-UNIDAD, D-NUM | Error; operación rechazada o ejecución pausada | Expresión, operandos y dominio; corregir tipo o rango |
| D-EXP-PENDIENTE | No ejecutable | Texto sin interpretar; completar expresión |
| D-SEM-PENDIENTE | No ejecutable | U y capacidad usada; cerrar interpretación |
| D-LOTE | Escenario inválido | Entrada duplicada y lotes; declarar simultaneidad o secuencia |
| D-ESCRITURA-CONFLICTO | Ejecución fallida | Autores, valores y contexto; modificar condiciones o diseño |
| D-MODO-SALIDA | Error de documento | Acciones de modos incompatibles; separar determinaciones |
| D-FORZADO-CONFLICTO, D-JERARQUIA-CICLO | Bloqueante | Órdenes y camino; resolver conflicto jerárquico |
| D-LIM-EVOL | Pausa no estabilizada | Presupuesto y último contexto; inspeccionar ciclo o ampliar presupuesto explícitamente |
| D-TRAZA-LIM | Pausa | Espacio/presupuesto agotado; exportar o ampliar límite |
| D-INSTANTANEA-INCOMPATIBLE | Restauración rechazada | Revisiones/perfiles distintos; abrir origen correcto |
| D-INSTANTANEA-FASE | Guardado de estado rechazado | Fase incompleta no exportable; alcanzar frontera compatible |
| D-FORMATO, D-INTEGRIDAD | Apertura rechazada o lectura de prefijo | Versión, digest, referencia o truncamiento |

Un diagnóstico de posible exclusión no demostrada o espera sin estímulos es advertencia, no prueba de defecto normativo. No se promete resolver alcanzabilidad general.
