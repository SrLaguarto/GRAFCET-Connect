# 09. Datos y contratos

Versión 0.1 · Estado: formato conceptual P especificado; semántica dependiente I/U.

## Propósito y referencias

Permitir intercambio abierto y restauración sin pérdida. Dependencias: [03](03_Modelo_conceptual_y_notacion.md), [05](05_Receptividades_eventos_tiempo_y_acciones.md), [08](08_Simulador_trazas_y_diagnostico.md), [10](10_Arquitectura_conceptual_y_multiplataforma.md). Fuente: ENC §13. No se entrega esquema ejecutable ni código. U-11 afecta a la ratificación del formato; U-03–U-09 condicionan campos semánticos de ejecución.

## Convenciones canónicas

P: documentos basados en JSON UTF-8, cada uno identificado por familia y versión. No se exige archivo contenedor comprimido. Un proyecto puede guardarse como carpeta con manifiesto y documentos relativos; ninguna referencia necesita rutas absolutas ni una cuenta externa. El manifiesto es el punto de apertura. Nombres de ficheros internos representan los bytes ASCII del ID mediante dígitos hexadecimales minúsculos, precedidos por el nombre de familia y seguidos de extensión JSON; las etiquetas Unicode se guardan como datos. Por ejemplo, IDs A y a dan componentes 41 y 61: no colisionan en sistemas de archivos que ignoran mayúsculas. La ruta se declara en el manifiesto y se comprueba que corresponde al ID.

IDs: cadenas ASCII de 1..128 caracteres de letras, dígitos, guion, punto y guion bajo, sensibles a mayúsculas; únicos dentro del proyecto. Etiquetas: Unicode, 1..256 caracteres, comparación de unicidad en ámbito mediante normalización NFC, sensible a mayúsculas. Los IDs no derivan de etiquetas, orden ni coordenadas. Un renombrado nunca cambia ID.

Booleanos nativos true/false. Enteros semánticos y tiempo se serializan como cadenas decimales canónicas para evitar pérdida entre runtimes: sin signo +, ceros iniciales ni -0. Decimales como cadena con punto, escala declarada y sin notación exponencial; el valor canónico elimina ceros fraccionales finales sin alterar escala del tipo. No se admiten NaN ni infinito. Coordenadas son decimales de presentación, sin efecto semántico. Conjuntos sin duplicados y ordenados por ID al comparar; listas de eventos conservan orden. Claves duplicadas son error. La ausencia de un campo no equivale a null o a cero.

## Familias y campos

Todos los documentos tienen family, formatVersion (mayor.menor), id y extensions opcional. Campo obligatorio omitido causa D-FORMATO. Las referencias mencionadas abajo se resuelven por ID y, entre documentos, por referencia relativa declarada.

| Familia | Campos obligatorios y dominio | Cardinalidad / restricciones |
|---|---|---|
| Proyecto | title, normativeBase, modelRefs, scenarioRefs, presentationRefs, capabilityProfile | ≥1 modelo; normativeBase contiene IEC 60848:2013, edición 3.0 y adopción declarada; listas sin repetidos |
| Modelo | revisionId, partials, steps, transitions, variables, expressions, actions, forces, hierarchy | hierarchy contiene macros, expansions y enclosures con los campos del diccionario; colecciones vacías admitidas en borrador; revisión inmutable para ejecución |
| Presentación | modelId, views, elementLayouts, notes | Cada layout apunta a ID existente; cambios no cambian revisionId semántica |
| Escenario | modelRevision, semanticProfile, initialInputs, batches, stopCondition, timeUnit | timeUnit=us; toda entrada inicializada; lotes ordenados por (tiempo, ordinal) |
| Instantánea | modelRevision, semanticProfile, scenarioId, runId, state, integrity | state incluye todos los componentes de Z; no bastan valores visibles |
| Traza | header, records, closure | closure con estado, cantidad y digest; ausencia implica truncada |
| Catálogo de pruebas | testId, requirementIds, modelData, initialState, stimuli, oracle, status | oracle concreto o bloqueado con U; nunca omisión que signifique «cualquier resultado» |

El perfil de capacidades contiene IDs de capacidades, versión de su semántica y estado (aprobada/provisional/no soportada). Los U usados se enumeran. Un importador no cambia provisional a aprobada. Versiones de formato, aplicación, perfil y norma son ejes diferentes.

## Diccionario del modelo

| Entidad | Campos | Validez |
|---|---|---|
| Partial | id, label, ownerRef opcional, stepRefs, transitionRefs | Pertenencia coherente y única |
| Step | id, label, partialRef, kind, initial, actionRefs | kind=ordinary/enclosing/entry/exit; E/S asociados a expansión; macro es entidad aparte |
| Transition | id, partialRef, label opcional, preRefs, postRefs, conditionRef | pre/post conjuntos; vacíos tratados según fuentes/sumideros; conditionRef único |
| Variable | id, name, scopeRef, role, type, unit, domain, initialValue | Role=input/internal/output; activity es derivada, no variable escribible |
| Expression | id, mode, text, meaning opcional, resultType opcional, bindings | mode=executable o descriptive; ejecutable exige significado completo |
| Meaning | operator, operands, literal o reference | Árbol finito de operadores enumerados en 05; no código arbitrario |
| Action | id, stepRef, mode, targetRef, conditionRef o trigger, valueRef | Continua: objetivo booleano y condición; memorizada: trigger y valor; no campos de ambos modos |
| Trigger | kind, sourceRefs, expressionRef opcional | activation/deactivation/event; referencia a franqueamiento solo con perfil que cierre representación U-03 |
| Force | id, sourceStepRef, targetPartialRef, targetKind, targetSteps | targetKind=explicit/current/empty/initial; targetSteps solo para explicit |
| Macro | id, label, partialRef, expansionRef | Una expansión por macro y propietario único |
| Expansion | id, ownerMacroRef, partialRef, entryRef, exitRef | E y S existentes y distintos; restricciones avanzadas U-08 |
| Enclosure | id, ownerStepRef, partialRef, activationRefs | Un propietario; referencias locales; inicialidad separada |

Los enlaces ordinarios se representan canónicamente por preRefs/postRefs; las rutas de presentación referencian el par transición-etapa y su dirección. No se almacena una segunda lista semántica independiente que pueda contradecirlos. Propiedad de expansiones y recintos se valida como una relación única; referencias redundantes tienen que coincidir o se rechaza el documento.

Texto y significado: en expresión ejecutable, meaning y bindings son autoritativos, y text debe producir el mismo significado bajo la versión de sintaxis indicada. Si difieren, no se elige silenciosamente ninguno: D-EXP-DIVERGENTE y apertura como borrador preservando ambos. En una expresión descriptive solo text tiene contenido; no es ejecutable. Un comentario nunca es fuente de significado.

## Estado, escenario y registro

| Objeto | Campos mínimos |
|---|---|
| Batch | id, timeUs, ordinalAtTime, changes (variableRef,value), origin |
| StopCondition | horizonUs opcional, predicateRef opcional, maxContexts; al menos un límite finito |
| State | activeStepRefs, values, storedValues, eventHistory, temporalStates, hierarchyState, activeForces, logicalTimeUs, pendingBatches, phase, causalContext |
| TemporalState | expressionRef, baseValue, intervalStart, effectiveValue, deadlines, cancellationState |
| ForceState | forceRef, activationContext, capturedTarget si current |
| CausalContext | id, priorStableStateRef, currentBatchRef, eventBeforeAfter, virtualEvolutionIndex, pendingEffects, completeness |
| Record | sequence, timeUs, batchOrdinal, evolutionIndex, contextRef, kind, beforeRef, delta o fullState, clearedTransitions, events, assignments, diagnostics |
| Closure | completionState, recordCount, finalStateRef, semanticDigest |

Un campo temporal no aplicable se representa mediante estado explícito «inactive», no un instante cero inventado. Los campos que dependan de U no pueden omitirse al crear una instantánea que se diga exacta: ese perfil no habilita restauración hasta cerrar la cuestión.

## Ejemplo original como datos tabulados

| Registro | Valores |
|---|---|
| Modelo | id=demo; revisionId=r1; parcial=g |
| Etapas | a inicial; b no inicial; ambas en g |
| Transición | t; pre={a}; post={b}; condición referencia entrada start |
| Variable | start; input; booleano; inicial false |
| Lote | l1; timeUs=2000000; ordinal=0; start=true |
| Oráculo I | Antes S={a}; E={t}; después S={b}; tiempo=2000000; sin acciones |
| Cambio de vista | a pasa de (10,20) a (50,80); revisionId permanece r1 |

## Versiones, migración e integridad

Versión mayor desconocida: no ejecutar ni sobrescribir. Versión menor desconocida: solo permitir lectura completa si declara no añadir significado y el lector puede preservar campos; en otro caso, rechazo explícito. Un campo desconocido dentro del significado ejecutable bloquea simulación. Extensiones usan un espacio de nombres y declaran si afectan a semántica; las no reconocidas semánticas bloquean, las descriptivas se conservan opacas, sin ejecutarse.

Migrar crea copia con versión nueva, conserva original y produce informe de cambios y requisitos afectados. No hay migración automática entre ediciones normativas o perfiles. Una migración que cambia significado requiere modelo nuevo, revisión y aprobación del responsable; no se presenta como ida y vuelta sin pérdida.

P: guardado completo o anterior válido; escritura interrumpida no deja un proyecto válido mezclado de dos revisiones. La verificación de integridad usa digest SHA-256 de una representación canónica: claves ordenadas por valor de punto de código Unicode, cadenas UTF-8 con normalización solo de nombres donde se declara, números como arriba, conjuntos ordenados y listas preservadas. La representación no contiene BOM ni espacios externos a cadenas. En cadenas se escapan comillas y barra inversa; caracteres U+0000 a U+001F se representan mediante escape Unicode de cuatro dígitos hexadecimales minúsculos; los demás caracteres Unicode válidos se emiten directamente. Se rechazan sustitutos Unicode aislados. Booleanos y null usan sus formas JSON minúsculas. Los únicos números JSON nativos admitidos son enteros de metadatos entre 0 y 2^31−1; el resto se representa mediante cadenas tipadas como se indicó. Esta regla evita divergencias de serialización.

El digest semántico incluye normativa declarada, perfil y todas las relaciones y expresiones ejecutables; excluye presentación, notas, etiquetas puramente visibles y metadatos de fecha. Para expresiones ejecutables incluye significado y vínculos, no el texto redundante. Para expresiones descriptivas incluye el texto porque es la especificación conservada. El digest de contenido de archivo incluye todos los campos excepto su propio campo de digest. El campo integrity declara qué proyección se ha firmado; nunca se compara digest semántico con digest de archivo. Una revisión semántica vincula un único contenido, aunque las etiquetas y vistas puedan tener revisiones de presentación separadas. Esta descripción fija el contrato; no obliga a una biblioteca.

No se siguen referencias fuera de la raíz del proyecto, rutas absolutas, enlaces a ejecutables ni recursos de red para interpretar modelos. Referencias con componentes de ascenso o destinos resueltos fuera de raíz son D-RUTA. Se rechazan scripts y operadores no enumerados. Tamaños y profundidades se comprueban antes de aceptar el archivo.

## Requisitos de datos

| ID | Clase/prioridad | Obligación | Pruebas |
|---|---|---|---|
| REQ-DAT-01 | P/crítica | Identidades, referencias y propiedad deben validar sin ambigüedad | T-22b, T-21e |
| REQ-DAT-02 | P/crítica | Ida y vuelta debe conservar significado, notas y vista dentro del formato admitido | T-22a |
| REQ-DAT-03 | P/crítica | Versiones, desconocidos y migraciones deben seguir política anterior sin pérdida silenciosa | T-22c,e |
| REQ-DAT-04 | P/crítica | Instantánea debe requerir compatibilidad exacta y totalidad de Z | T-22f, T-23c |
| REQ-DAT-05 | P/crítica | La comparación semántica debe ser canónica y ajena a configuración regional | T-24a,b |
| REQ-DAT-06 | P/crítica | Archivos no deben ejecutar código ni resolver contenido fuera de raíz | T-25b,c |
| REQ-DAT-07 | P/crítica | Guardado debe ser atómico en resultado observable y recuperar último estado válido | T-22d |
| REQ-DAT-08 | P/crítica | Debe detectarse divergencia texto-significado y trazas truncadas | T-09c, T-22g |

## Contratos conceptuales

Validar recibe revisión y perfil; devuelve diagnósticos y capacidades necesarias sin modificar documento. Iniciar recibe modelo validado y escenario; devuelve Z inicial o errores. Aplicar estímulo recibe Z y lote; devuelve contexto y evolución definida o error; no acepta lotes anteriores a τ. Observar recibe Z y filtro; devuelve proyección sin efectos. Obtener instantánea recibe Z; devuelve estado íntegro o fase no exportable. Restaurar recibe instantánea y origen compatible; devuelve Z equivalente sin reinicializar variables. Guardar recibe documento completo; devuelve identidad de revisión persistida o fallo conservando la anterior. Los contratos no imponen cómo se implementan esas responsabilidades.
