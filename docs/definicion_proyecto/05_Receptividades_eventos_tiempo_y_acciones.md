# 05. Receptividades, eventos, tiempo y acciones

Versión 0.1 · Estado: contratos P especificados; semántica I y casos U identificados.

## Propósito y referencias

Definir expresiones y efectos observables. Dependencias: [03](03_Modelo_conceptual_y_notacion.md), [04](04_Semantica_de_evolucion.md), [09](09_Datos_y_contratos.md), [11](11_Trazabilidad_y_plan_de_pruebas.md). Fuentes: LOC §§4.6–4.10, tablas 1,4–6; ENC §§7–9. Abiertos U-01 a U-06, U-08 y U-09.

## Tipos y sintaxis de producto

P: tipos ejecutables iniciales booleano, entero con signo de 64 bits, decimal exacto de escala declarada (0..9 decimales y hasta 18 cifras significativas), y duración entera en microsegundos. Cada variable tiene rol, ámbito, unidad, dominio y valor inicial. Las entradas requieren inicialización explícita; ausencia de valor bloquea el inicio. No se introduce lógica ternaria. Los valores fuera de dominio, desbordamientos y división por cero no se convierten silenciosamente.

La fuente local indica inicialización falsa/cero para variables memorizadas (LOC §4.8.3). I: el inicio normativo de esas variables se fija en falso/cero. Una instantánea puede contener otros valores; no equivale a inicialización. Un escenario que pretenda arrancar memoria con valores distintos debe identificarse como intervención E, no sustituir ese arranque sin aviso (U-09 para excepciones justificadas).

| Expresión textual propia P | Tipo y semántica | Correspondencia visual |
|---|---|---|
| true, false | Booleano | 1 y 0 en contexto lógico |
| nombre o referencia calificada | Tipo de variable resuelta por ID | Etiqueta visible y ruta si ambigua |
| NOT p; p AND q; p OR q | Booleanos, sin conversión numérica | Negación, conjunción y disyunción; alias gráficos resueltos al mismo significado |
| a = b, !=, <, <=, >, >= | Comparación entre tipos y unidades compatibles | Predicado entre corchetes cuando corresponda |
| a + b, a - b, a * b | Aritmética exacta; sin desbordamiento | Texto de predicado o asignación |
| a / b | Decimal; solo si resultado es representable en tipo destino | D-NUM si requiere redondeo no declarado |
| active(etapa), activePartial(parcial), activeMacro(macro) | Booleano de solo lectura | X, XG, XM con referencia resuelta |
| elapsed(etapa) | Duración de actividad | T con etiqueta; valor inactivo pendiente U-06 |
| rise(p), fall(p) | Evento sobre proposición booleana | Flechas ascendente/descendente |
| delay(t1,p,t2) | Condición temporal booleana | t1 / p / t2 |

Precedencia P, de mayor a menor: agrupación y referencias funcionales; signo unario; multiplicación/división; suma/resta; una comparación; NOT; AND; OR. Las comparaciones encadenadas se rechazan: deben expresarse con AND. Los paréntesis siempre desambiguan. En este paquete p+q no se usa como OR textual: el símbolo gráfico puede admitirse como alias de edición, pero el parser debe conocer el contexto y guardar estructura inequívoca. rise(a OR b) no equivale a rise(a) OR rise(b).

Todas las expresiones son puras: evaluarlas para explicación, monitorización o validación no cambia contadores, memorias ni tiempo. No hay llamadas a funciones externas, scripts ni acceso al sistema. No se admiten conversiones booleano↔número implícitas. Unidades: suma y comparación requieren la misma dimensión; cualquier conversión de unidad debe ser exacta y explícita. Un predicado literal libre puede conservarse sin ejecutarse.

## Eventos

I: un flanco ascendente corresponde al par falso→verdadero y uno descendente al par verdadero→falso. Un nivel verdadero mantenido no produce flancos nuevos. La expresión compuesta se evalúa sobre los dos estados completos, sin estados artificiales entre miembros de un lote simultáneo. Arrancar con a=true inicializa su memoria con true y no inventa rise(a) (I, pendiente U-09).

P: cada estímulo tiene tiempo, ordinal de lote y cambios. Un lote es simultáneo: admite como máximo una escritura por entrada. Dos valores distintos para una entrada en el mismo lote son error D-LOTE. Dos lotes ordenados con el mismo tiempo son eventos distintos; se conserva su orden y el cierre causal entre ellos. El sistema no deduce simultaneidad solo por igualdad de tiempo.

| Caso | Resultado definido o pendiente |
|---|---|
| a:0→1 y b:0→1 en un lote | rise(a), rise(b) y rise(a AND b) verdaderos para ese evento |
| a=1,b=0 pasan simultáneamente a a=0,b=1 | rise(a OR b) falso, fall(a OR b) falso |
| Flanco con transición no validada; validación tras otro evento posterior | El primer flanco no queda almacenado para el segundo; I |
| Dos transiciones ya validadas usan el mismo flanco | Ambas pueden franquear simultáneamente; ningún consumo exclusivo |
| Una transición se valida dentro del recorrido causado por ese mismo flanco | U-03: no se decide por duración de animación ni por cola |
| Acción sobre evento y etapa que se desactiva por ese evento | U-03/U-05: verificar contexto de actividad y lectura |
| Evento de franqueamiento y evento de cambio de actividad | Se registran separados; uno no prueba el otro |

## Tiempo exacto y fronteras

P: unidad canónica µs; tiempo lógico no negativo, máximo 2^63−1 µs. No hay redondeo silencioso: una entrada con precisión menor que 1 µs o fuera de rango se rechaza. La unidad visible puede ser s o ms sin cambiar el valor. El reloj avanza a tiempos del escenario o vencimientos; no se impone periodo de escaneo. Pausar detiene el avance lógico; cambiar velocidad solo modifica presentación.

I: para delay(d,p,0), un tramo continuo p=true iniciado en t0 hace la condición verdadera al alcanzar t0+d, y vuelve a falso al caer p. Un pulso más breve que d no la activa. Las fronteras simultáneas con otros hechos se separan en U-06.

| Forma | Inicio / resultado ordinario | Cancelación y reentrada | Límites |
|---|---|---|---|
| delay(d,p,0) | p sube en t0; falso antes de t0+d; verdadero desde t0+d mientras p siga verdadero | Si cae antes, cancela; próxima subida empieza un intervalo nuevo | d=0 coincide con p en casos sin otros eventos; coincidencias U-06 |
| delay(d1,p,d2) | Subida sostenida d1 activa; caída posterior mantiene hasta caída+d2 | Pulsos previos menores que d1 no activan | Rebote durante retardo de desconexión: U-06 |
| delay(d,active(A),0) | Cuenta actividad continua de A; puede usarse en transición no adyacente | Salir de A cancela; reentrada inicia nuevo intervalo | Regla 5 sin interrupción no reinicia por sí sola; detalle U-04 |
| Acción retardada | active(A) AND delay(d,active(A),0) | Deja de contribuir al salir A | Una etapa virtual no produce un pulso efectivo |
| Acción limitada | active(A) y duración desde activación menor que d | Cesa al salir A o alcanzar d; reentrada reinicia | Intervalo propuesto [t0,t0+d); d=0 sin pulso; I |

Cronograma original sin coincidencias: p sube a 2 s, baja a 8 s; d1=1,5 s, d2=2 s. Condición false antes de 3,5 s, true desde 3,5 s hasta antes de 10 s, false desde 10 s. Si p baja a 3 s, nunca llega a true. Una salida continua asociada a A además requiere A activa: no se mantiene encendida por el retardo si A ya no contribuye.

La salida de una encapsulación desactiva sus etapas; la actividad continuada que sustentaba su retardo termina. No se presupone que toda memoria temporal de condiciones externas al recinto se borre. Forzado a situación actual impide evolución del parcial, pero no se equipara a congelación del reloj; esa interacción permanece U-08. No se acepta una política accidental de «pausar todos los temporizadores».

## Acciones y salidas

I: para una salida booleana continua y, y es la disyunción de las contribuciones active(s) AND condición de cada acción que la determine. Si no contribuye ninguna, y=false. Una contribución falsa no anula otra verdadera. Orden de dibujo o enumeración irrelevante. Una condición continua no debe contener flancos; un evento debe describirse mediante una acción memorizada, no un pulso continuo de duración de fotograma.

I: una acción memorizada impone el valor indicado cuando ocurre su evento y conserva el último valor entre eventos. Activación y desactivación, incluidas las virtuales pertinentes, pueden ser disparadores distintos. El número de actualizaciones depende de eventos reales descritos, no de veces que se pinte la pantalla. Las expresiones numéricas y su régimen de evaluación concurrente requieren decisiones compatibles; U-05 impide adoptar «última escritura gana».

| Combinación sobre una variable | Conducta |
|---|---|
| Varias continuas booleanas | Disyunción de contribuciones, I |
| Memorizadas concurrentes con igual valor constante | Resultado único; conservar todos los autores en la traza, I |
| Memorizadas concurrentes con valores contradictorios | P: detener con D-ESCRITURA-CONFLICTO y conservar candidatos; no escoger |
| Dos incrementos simultáneos sobre el mismo contador | U-05: no sumar dos veces ni colapsar a una actualización sin contrato |
| Una acción continua y otra memorizada sobre la misma salida | I: validación bloqueante D-MODO-SALIDA; no escoger modo por instante |
| Memorizada en etapa virtual | Efecto no eliminado por ser virtual, I |
| Continua en etapa exclusivamente virtual | No genera salida efectiva, I |
| Sin evento para una variable memorizada | Conservar valor, I |
| Acción intenta escribir una entrada o variable de actividad | P: D-ESCRITURA-ROL |

P: ante conflicto dinámico se conserva el último estado completo anterior y el detalle de propuestas; se señala como fallido el contexto actual. No se continúa con un subconjunto arbitrario de asignaciones ni se informa el estado parcial como estable.

## Catálogo de requisitos

| ID | Clase/prioridad | Obligación | Fuente / casos |
|---|---|---|---|
| REQ-EXP-01 | P/alta | El editor debe aplicar tipos, unidades y precedencia anteriores sin conversiones ocultas | ENC §7.1; T-09a,b,c |
| REQ-EXP-02 | P/crítica | Evaluar expresiones debe ser libre de efectos laterales | ENC §7.1; T-09d |
| REQ-EVT-01 | I/crítica | Los flancos deben corresponder a cambios de proposición, sin consumo exclusivo ni retención entre eventos posteriores | LOC §4.6, tabla 4 [15],[16]; T-10a,b,c,e |
| REQ-EVT-02 | P/crítica | El escenario debe distinguir simultaneidad de orden entre lotes con igual tiempo | ENC §7.2; T-10b, T-13a |
| REQ-EVT-03 | U/crítica | Deben resolverse persistencia intrainstante y eventos internos de permanencia activa | U-03,U-04; T-10d, T-11a,b |
| REQ-TMP-01 | P/crítica | El tiempo debe ser exacto y reproducible según unidad y límites anteriores | ENC §8; T-12d, T-24b |
| REQ-TMP-02 | I/crítica | Retardos y acciones temporizadas deben respetar fronteras ordinarias y cancelaciones descritas | LOC tabla 4 [17],[18], tabla 5 [23]–[25]; T-12a,b,c |
| REQ-TMP-03 | U/crítica | Antes de ejecutar coincidencias debe resolverse su oráculo, incluidos rebotes y jerarquías | U-06,U-08; T-13b,c, T-20a |
| REQ-ACT-01 | I/crítica | Las salidas continuas deben aplicar la disyunción indicada y excluir pulsos virtuales | LOC §§4.8.2,4.9.4; T-14a,b,c |
| REQ-ACT-02 | I/crítica | Las memorizadas deben conservar valores y reflejar eventos pertinentes de etapas virtuales | LOC §§4.8.3,4.9.5; T-15a,b |
| REQ-ACT-03 | P/crítica | Conflictos de escritura deben detener con evidencia sin prioridad oculta | ENC §9; LOC §4.10.5; T-16a,b |
| REQ-ACT-04 | I/crítica | Una salida no debe mezclar modos continuo y memorizado | LOC §4.10.5 nota 1; T-16c |
| REQ-ACT-05 | U/crítica | La lectura de valores asignados en un mismo contexto debe cerrarse antes de admitir dependencias mutuas | U-05; T-15c, T-16d |

## Diagnóstico e intervenciones

Monitorizar no ejecuta acciones. Alertas son observaciones P y no modifican temporización ni receptividad. Las entradas manuales se convierten en lotes registrados. Una modificación manual de memoria es intervención E: exige pausa estable, crea una rama de ejecución y marca sus trazas como intervenidas. No forma parte del conjunto de pruebas normativas. No se permite manualmente fabricar eventos internos sin registrar su naturaleza.
