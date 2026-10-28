# 04. Semántica de evolución

Versión 0.1 · Estado: interpretación provisional I; causalidad avanzada parcialmente bloqueada.

## Propósito y dependencias

Fijar los observables exigidos sin prescribir un algoritmo. Definiciones: [03](03_Modelo_conceptual_y_notacion.md). Eventos, tiempo y acciones: [05](05_Receptividades_eventos_tiempo_y_acciones.md). Jerarquías: [06](06_Estructuracion_y_jerarquias.md). Casos: [11](11_Trazabilidad_y_plan_de_pruebas.md). Fuente: LOC §§4.5–4.10. Abiertos: U-01, U-03, U-04, U-05, U-07 y U-08. Aplican las fichas comunes de 01.

## Estado abstracto suficiente

Un estado Z queda descrito por (revisión semántica, S, V, M, H, Θ, J, F, τ, Q, φ, C). S es situación; V valores de entrada y variables; M memoria de asignaciones; H historia necesaria de expresiones de evento; Θ condiciones temporales y vencimientos; J pertenencia y actividad jerárquica; F órdenes de forzado y situaciones capturadas; τ tiempo lógico; Q estímulos pendientes y su agrupación; φ fase de observación; C contexto causal en curso. No exige una estructura de programación concreta.

Un documento guarda definiciones; una instantánea guarda Z completo. Volver a un dibujo anterior no restaura Z. Inicializar aplica la situación inicial del modelo; reiniciar crea una ejecución nueva; restaurar continúa una ejecución compatible conservando memorias. El reloj de presentación no forma parte de la semántica.

## Cinco reglas y relación colectiva

Para la parte ordinaria de un modelo, Pre(t) y Post(t) son conjuntos de etapas. Una transición está validada si Pre(t) está incluido en S. Es franqueable si además su receptividad es verdadera en el contexto causal considerado. Esta caracterización debe adaptarse a macroetapas y a forzados, nunca ignorarlos.

Sea E el conjunto completo de transiciones simultáneamente franqueables en una situación coherente, D la unión de sus Pre y A la unión de sus Post. La relación colectiva de actividad es:

**S′ = (S ∖ D) ∪ A.**

La unión final conserva las etapas que aparecen a la vez en D y A. No representa por sí sola eventos internos, acciones, tiempo, expansiones ni encapsulación. No es un algoritmo ni una autorización para ejecutar todas las acciones después de esta fórmula.

| ID | Clase/prioridad | Contrato de regla | Localizador | Positiva / límite |
|---|---|---|---|---|
| REQ-SEM-01 | I/crítica | La situación inicial debe ser la elegida explícitamente, incluidas sus relaciones jerárquicas; no se elige la primera etapa del archivo | LOC §4.5.2 | T-01a / T-01b |
| REQ-SEM-02 | I/crítica | Debe franquearse una transición cuando concurran validación y receptividad, salvo imposición jerárquica aplicable; una sola condición no basta | LOC §4.5.3 | T-02c / T-02a,b |
| REQ-SEM-03 | I/crítica | Un franqueamiento debe modificar conjuntamente precedentes y siguientes | LOC §4.5.4 | T-03a / T-03b,c |
| REQ-SEM-04 | I/crítica | El conjunto simultáneo debe incluir todas las franqueables, incluidas las que comparten precedentes | LOC §4.5.5 | T-04a / T-04b,c |
| REQ-SEM-05 | I/crítica | La etapa simultáneamente activada y desactivada debe permanecer activa; no se inventa una baja intermedia | LOC §4.5.6 | T-05a / T-05b |
| REQ-SEM-06 | I/crítica | Las situaciones transitorias deben distinguirse de las efectivas y conservar sus efectos memorizados pertinentes | LOC §§4.9.1–4.9.5 | T-07a,b,c |
| REQ-SEM-07 | P/crítica | Todo límite de evolución debe detener con diagnóstico, sin avanzar tiempo ni publicar falsa estabilidad | ENC §6.3 | T-08a,b |
| REQ-SEM-08 | P/crítica | El mismo modelo, contexto causal y escenario deben producir iguales observables, con independencia de recorrido, geometría y velocidad | ENC §§6,16.4 | T-04c, T-23b, T-24a |
| REQ-SEM-09 | U/crítica | Antes de cerrar el motor debe resolverse el alcance de eventos y escrituras entre evoluciones transitorias | LOC §§4.6–4.9; U-03 a U-05 | T-10d, T-11b, T-15c |

Las pruebas I tienen oráculo provisional: son precisas, pero no están cerradas como evidencia de conformidad. La situación inicial vacía no se reemplaza automáticamente por una etapa arbitraria. Su validez y evolución con transiciones fuente se revisan en U-07.

## Simultaneidad y selección

Dos transiciones independientes franqueables pertenecen a un mismo conjunto E. Si comparten A como precedente y conducen a B y C con condiciones ambas verdaderas, el resultado incluye B y C; no se escoge la rama situada a la izquierda. Una exclusión exige condiciones lógicas excluyentes explícitas. Se permite que un diseñador exprese prioridad mediante condiciones; no se crea prioridad a partir del orden gráfico.

Una sincronización con Pre={B,C} requiere ambos activos. Alcanzar B antes que C no produce por sí solo el franqueamiento. Una transición con varios siguientes activa el conjunto entero en la misma evolución. Los parciales interdependientes se observan desde una situación global coherente, no desde copias ya modificadas por un recorrido anterior.

## Estabilidad y transitorios

Una situación estable es el resultado efectivo en el que no queda una evolución exigida por el contexto vigente. No basta que S deje de cambiar: un ciclo puede repetir S mientras modifica memoria o vuelve a disparar transiciones. Un recorrido explicativo transitorio muestra situaciones virtuales, sin duración positiva y sin convertir sus acciones continuas en pulsos observables. Las acciones memorizadas vinculadas a activaciones o desactivaciones virtuales no se eliminan por simplificar la traza.

P: «microavance» muestra una frontera de evolución simultánea en el recorrido explicativo. «Hasta estabilización» muestra el resultado efectivo del contexto causal completo. Ambos deben conservar la misma traza semántica y el mismo estado final, cuando estos estén definidos. Una pausa en un microavance no convierte una etapa virtual en una etapa efectivamente activa.

Un grafcet estable esperando una entrada no es error. Un ciclo instantáneo A→B→A con condiciones permanentemente verdaderas no se estabiliza por dejar de dibujar la animación. Un presupuesto agotado indica ejecución inconclusa, no necesariamente demostración matemática de divergencia.

## Tabla de causalidad y observación

Esta tabla fija relaciones observables, no un ciclo de escaneo ni una secuencia interna de implementación.

| Frontera conceptual | Datos que deben ser coherentes | Cambios/eventos | Salidas y vista |
|---|---|---|---|
| Estado estable anterior | Z completo; entrada anterior | Ninguno por observar | Valores efectivos previos |
| Contexto externo | Lote simultáneo anterior/posterior completo | Un cambio compuesto; secuencias explícitas se separan | Registro del estímulo; no estados intermedios inventados dentro del lote |
| Evolución simultánea ordinaria | Una misma situación, valores y eventos aplicables | E como conjunto; relación colectiva S′ | Explicación virtual si falta estabilización; acciones según 05 |
| Entrada/salida de jerarquía | Relaciones de pertenencia y órdenes vigentes | Restricciones de 06; coincidencias U-08 | Mostrar origen jerárquico, no transición ficticia |
| Recorrido transitorio | Causa externa vinculada; historias y memorias pertinentes | Activaciones/desactivaciones virtuales y franqueamientos | No publicar pulsos continuos de etapas virtuales; conservar distribuciones |
| Situación efectiva siguiente | Cierre causal completo | Estado estable identificado | Salidas continuas efectivas y memoria resultante |
| Incidencia | Último Z confiable y contexto parcial | Diagnóstico con valores candidatos | Pausa; resultado no resuelto, nunca estable por omisión |

Quedan por determinar: evento reutilizable en una transición habilitada más tarde dentro del mismo recorrido (U-03), lecturas de asignaciones simultáneas y sucesivas (U-05), coincidencias temporales (U-06) y prioridad entre restricciones jerárquicas (U-08). La segunda IA no debe rellenar estas celdas con un orden fijo de ejecución.

## Regla 5 y eventos

La permanencia activa de B en {A,B}→{B,C}, producida por A→B y B→C simultáneas, está fijada. La activación y desactivación ordinarias observables por diferencia de situaciones son {C} y {A}; no se deriva automáticamente un par de eventos de B. Sin embargo, la norma trata por separado los eventos de franqueamiento y los recorridos virtuales. T-05b distingue estos hechos; el tratamiento completo de acciones vinculadas a B queda U-04.

## Salvaguardas

P: presupuesto inicial de 10 000 evoluciones explicativas por contexto causal, configurable y registrado. Al agotarlo, pausa con D-LIM-EVOL, tiempo inalterado, situación marcada «no estabilizada», últimos registros completos y contexto pendiente recuperable. Si se agota almacenamiento de traza, D-TRAZA-LIM suspende antes de perder evidencia requerida. No se asegura detección estática de todos los ciclos.
