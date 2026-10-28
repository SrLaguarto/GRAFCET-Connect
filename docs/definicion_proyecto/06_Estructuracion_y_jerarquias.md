# 06. Estructuración y jerarquías

Versión 0.1 · Estado: interpretación I parcial; interacciones críticas U-08.

## Propósito

Separar partición, forzado, expansión y encapsulación. Dependencias: [03](03_Modelo_conceptual_y_notacion.md), [04](04_Semantica_de_evolucion.md), [05](05_Receptividades_eventos_tiempo_y_acciones.md), [11](11_Trazabilidad_y_plan_de_pruebas.md). Fuentes: LOC §7, tablas 8–11; ENC §10. Abiertos U-01, U-02, U-04, U-05, U-08.

## Parciales

Cada elemento pertenece a un parcial identificado. La actividad XG se deriva de la existencia de alguna etapa activa en su contenido. La partición no impone orden de ejecución. Las referencias de lectura entre parciales son explícitas, calificadas y de solo lectura para las actividades. Una transición no adquiere prioridad por estar en un parcial «principal» salvo una relación de forzado prevista y visible.

I: un parcial puede contener varios componentes conectados. P: la estructura de propiedad es acíclica y permite localizar cada elemento mediante ruta; no se permite compartir la misma instancia de etapa entre dos propietarios. La duplicación crea otra identidad y mantiene separada su actividad.

## Forzado normativo

I, LOC tabla 9: una orden vinculada a una etapa de un parcial superior impone una situación a un parcial inferior mientras su origen está activo, con prioridad sobre la evolución ordinaria de ese destino. No equivale a escribir X(s) desde el depurador. La situación del parcial forzado no evoluciona ordinariamente mientras la orden está vigente.

| Forma | Captura/objetivo | Mientras está vigente | Retirada y límite |
|---|---|---|---|
| Explícita | Conjunto de IDs de etapas del destino | Mantiene ese conjunto | Se permite evolución desde la situación resultante; eventos/tiempo U-08 |
| Actual | Captura la situación al entrar en vigor | Mantiene la captura, no la recalcula tras cada intento de evolución | No recupera automáticamente una situación anterior al forzado |
| Vacía | Conjunto vacío | Sin etapas activas en destino | No reinicializa por defecto al retirarse |
| Inicial | Situación inicial especificada del destino | Mantiene esa situación | No equivale a reiniciar toda la simulación o sus memorias |

La retirada elimina la restricción; no prescribe un evento sintético de flanco. Deben registrarse orden, origen, destino, conjunto impuesto, momento de activación y retirada. No se atribuye al forzado «congelar todo el sistema»: puede cambiar el entorno y otras partes evolucionan.

P: el validador rechaza autorreferencia y ciclos de la relación superior→inferior como D-JERARQUIA-CICLO. Su fundamento I es la relación jerárquica; el detalle exacto debe contrastarse U-08. Dos órdenes activas con igual destino y objetivo distinto detienen con D-FORZADO-CONFLICTO; no se ordenan por ID. Objetivos iguales pueden coalescer conservando todos los orígenes; la retirada de uno no elimina los demás. Esta última regla es P provisional de representación de restricciones, pendiente de U-08 si intervienen capturas distintas.

## Macroetapas

I, LOC tabla 11: una macroetapa M tiene una expansión única que no comparte con otra macroetapa. La expansión tiene una etapa de entrada E y una de salida S. El franqueamiento de una transición precedente de M activa E. La actividad de alguna etapa interna determina XM; esa actividad no basta para validar las transiciones posteriores de M: se requiere S activa. El franqueamiento posterior desactiva S como precedente de la relación expandida.

| Hecho | Resultado | Cautela |
|---|---|---|
| Llegada externa a M | Activa E | No «llamada a función» ni ejecución aislada de los demás parciales |
| Interior en etapa intermedia | XM=true; sucesoras externas no habilitadas por XM solamente | Se muestra ruta interior |
| S activa | Permite habilitar sucesoras externas | Sus restantes precedentes y receptividades siguen siendo necesarios |
| Nueva llegada después de finalización | Nueva activación de E | No borra memoria interna sin regla; U-08 para estados residuales |
| Recorrido inmediato E→…→S | Recorrido virtual en el mismo contexto si procede | Acciones continuas/memorizadas según 05 |
| Expansión con etapas iniciales | Puede participar en inicio | No prohibirla por analogía con subrutina; coherencia U-09 |
| Expansión con macroetapa interna | Anidamiento permitido como objetivo | Sin recursión de propiedad; profundidad P en 10 |

No se presupone que al salir se borren todas las otras etapas internas de una expansión mal sincronizada. Si quedan ramas activas, se presenta diagnóstico de estructura/comportamiento y se revisa U-08. Una salida externa conectada directamente a una etapa interior distinta de E/S no se acepta como conexión ejecutable hasta cerrar la regla de validez. Se conserva el borrador y se identifica el problema, sin declarar que es prohibición normativa ya verificada.

## Encapsulación

I, LOC §7.4: cada recinto pertenece a una sola encapsulante; una encapsulante puede contener varios recintos. Cuando la encapsulante está inactiva, su contenido debe estar inactivo. Cuando está activa, cada recinto contiene al menos una etapa activa. Los recintos de una misma encapsulante evolucionan en paralelo, sujetos a sus relaciones explícitas.

Inicial y enlace de activación son propiedades distintas. En el arranque rigen las etapas iniciales coherentes con sus encapsulantes iniciales. En una activación posterior rigen las etapas marcadas con enlace de activación; no se restaura la última situación ni se eligen siempre las iniciales. La desactivación de la encapsulante desactiva todo su contenido, también descendientes encapsulados.

Ejemplo original: H inicial encapsula R. R contiene I inicial, J y K marcada para activación. En el arranque H e I están activos. Una salida de H deja R vacío. Una activación posterior de H activa K, no I ni la última etapa alcanzada antes de salir. Si H contiene además R2 con L marcada, reentrar activa simultáneamente K y L. Esta diferencia es esencial para T-19a,b.

Las memorias de variables no se borran por plegar o desactivar un recinto; su actualización depende de las acciones y eventos. Las duraciones de etapas que dejan de estar activas no siguen acumulando actividad. El detalle de eventos de salida forzada y coincidencias entre nivel superior e inferior permanece U-08.

## Interacciones y restricciones pendientes

| Interacción | Comportamiento que no debe suponerse | Resolución requerida |
|---|---|---|
| Forzar un recinto mientras su encapsulante está inactiva | Activar hijos en violación de la relación de encapsulación | U-08: validez y orden de restricciones |
| Forzar vacía una encapsulación con padre activo | Aceptar que no quede ninguna etapa sin revisar el invariante | U-08: rechazo o interpretación normativa |
| Desactivar padre y vencer temporizador hijo simultáneamente | Decidir por orden de recorrido | T-20a con oráculo pendiente |
| Salida de macroetapa con ramas internas activas | Borrar las ramas por conveniencia | T-18d, U-08 |
| Dos forzados a situación actual capturados en momentos distintos | Suponer que significan el mismo conjunto | Comparar capturas y diagnosticar conflicto |
| Activación/desactivación simultánea de encapsulante | Vaciar y reinicializar automáticamente su interior | U-04/U-08; preservar distinción de permanencia |

## Requisitos

| ID | Clase/prioridad | Obligación | Fuente / aceptación |
|---|---|---|---|
| REQ-JER-01 | I/crítica | La partición debe conservar actividad y evolución global sin orden de parciales | LOC §7.2; T-04c, T-20b |
| REQ-JER-02 | I/crítica | El forzado debe expresar las cuatro formas y mantener su imposición mientras proceda | LOC §7.3, tabla 9; T-17a,b |
| REQ-JER-03 | P/crítica | Conflictos o ciclos de forzado deben diagnosticarse sin arbitraje oculto | ENC §10.1; T-17c,d |
| REQ-JER-04 | I/crítica | Macroetapa y expansión deben respetar entrada, salida, actividad y propiedad indicadas | LOC §7.5; T-18a,b,c |
| REQ-JER-05 | I/crítica | Encapsulación debe distinguir inicio de reentrada y desactivar descendientes al salir | LOC §7.4; T-19a,b,c |
| REQ-JER-06 | U/crítica | Las interacciones de forzado, jerarquía, tiempo y eventos deben cerrarse antes de habilitarlas | U-08; T-18d, T-20a,c |
| REQ-JER-07 | P/alta | Plegar, desplegar y navegar debe conservar el modelo y ejecución | ENC §10.4; T-21g, T-24a |

## Niveles y vistas

P: nivel funcional, tecnológico u operativo es metadato metodológico, no jerarquía normativa «1/2/3». La profundidad estructural pertenece al modelo. El nivel de detalle visible pertenece a la vista. Una descripción refinada distinta requiere otro modelo y una correspondencia explícita de entradas, salidas y observables; no se promete equivalencia automática. La vista plegada debe indicar si hay actividad, diagnóstico o forzado interior, sin convertir ese resumen en una variable nueva de ejecución.
