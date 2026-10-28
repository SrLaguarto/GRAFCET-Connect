# 12. Decisiones, pendientes y traspaso

Versión 0.1 · 24 de octubre de 2026 · Dictamen: PREPARADO PARCIALMENTE.

## Propósito y estado real

Entregar una base independiente a la segunda IA, con fronteras claras entre lo especificado y lo que necesita evidencia. Se han redactado doce documentos, revisado el encargo y el material local autorizado, verificado metadatos oficiales y diseñado pruebas originales. No se ha creado una aplicación, prototipo, script de producto ni pruebas ejecutables. No se ha ejecutado el catálogo contra un simulador.

Dependencias: todos los documentos del manifiesto. Referencias: ENC §§17–20 y fuentes de [02](02_Fuentes_normativas_y_clean_room.md). Las cuestiones de este documento son el registro canónico U. No se permite cerrar un U mediante un valor por defecto de implementación.

## Manifiesto y orden de lectura

| Archivo | Versión | Estado / función |
|---|---|---|
| [01_Alcance_y_objetivos.md](01_Alcance_y_objetivos.md) | 0.1 | Especificado; frontera y convenciones |
| [02_Fuentes_normativas_y_clean_room.md](02_Fuentes_normativas_y_clean_room.md) | 0.1 | Inventario revisado; contraste normativo pendiente |
| [03_Modelo_conceptual_y_notacion.md](03_Modelo_conceptual_y_notacion.md) | 0.1 | Conceptos P/I; variantes pendientes |
| [04_Semantica_de_evolucion.md](04_Semantica_de_evolucion.md) | 0.1 | Cinco reglas I; causalidad avanzada U |
| [05_Receptividades_eventos_tiempo_y_acciones.md](05_Receptividades_eventos_tiempo_y_acciones.md) | 0.1 | P e I concretos; coincidencias y asignaciones U |
| [06_Estructuracion_y_jerarquias.md](06_Estructuracion_y_jerarquias.md) | 0.1 | Jerarquías I; interacciones U |
| [07_Requisitos_del_editor.md](07_Requisitos_del_editor.md) | 0.1 | P especificado, aceptable por partes |
| [08_Simulador_trazas_y_diagnostico.md](08_Simulador_trazas_y_diagnostico.md) | 0.1 | P especificado; ejecución condicionada |
| [09_Datos_y_contratos.md](09_Datos_y_contratos.md) | 0.1 | Formato conceptual P; ratificación pendiente |
| [10_Arquitectura_conceptual_y_multiplataforma.md](10_Arquitectura_conceptual_y_multiplataforma.md) | 0.1 | Contratos P; presupuestos propuestos |
| [11_Trazabilidad_y_plan_de_pruebas.md](11_Trazabilidad_y_plan_de_pruebas.md) | 0.1 | Casos diseñados I/P/B; no ejecutados |
| [12_Decisiones_pendientes_y_traspaso.md](12_Decisiones_pendientes_y_traspaso.md) | 0.1 | Dictamen y control del traspaso |

Orden recomendado: 12 → 01 → 02 → 03 → 04 → 05 → 06 → 11 → 09 → 08 → 07 → 10. Leer los U antes de decidir arquitectura del motor. Los archivos son autosuficientes como paquete; no requieren acceder a carpetas originales para comprender las decisiones P. Las referencias normativas necesitan consulta autorizada para cerrar N.

## Consolidación de decisiones

| Clase | Decisiones y alcance | Estado |
|---|---|---|
| N | Ninguna regla semántica se declara N en 0.1. Edición y equivalencia son hechos bibliográficos verificados, no certificación | U-01 impide promoción automática de I |
| I | Alternancia, reglas colectivas, acciones continuas/memorizadas, transitorios, formas temporales ordinarias, forzado básico, entrada/salida de macro y reentrada de recintos | Evidencia LOC localizada; contraste pendiente |
| P | Identidad estable; presentación separada; tipos exactos; lotes ordenados; µs; guardado atómico; revisión inmutable; diagnósticos; contratos y límites | Especificadas, pendientes de aceptación del responsable |
| E | Depuración de memoria/situación, modo de reloj real, aleatoriedad opcional | Aisladas, fuera de pruebas normativas; no obligatorias |
| U | Registro siguiente | No resueltas; bloquear capacidad afectada y declaración de conformidad |

Se elige bloquear o pausar ante ambigüedad y conservar evidencia; esta decisión P no determina cuál es la respuesta normativa. No se limita definitivamente el objetivo avanzado: la versión 0.1 prepara su cierre sin fingir que se alcanzó.

## Registro de cuestiones

### U-01. Integridad, edición y correcciones

- Tipo: acceso/evidencia insuficiente. Prioridad crítica.
- Pregunta: ¿qué reglas y correcciones de IEC 60848:2013 y su adopción se han contrastado con una fuente íntegra autorizada?
- Evidencia: fichas IEC/AENOR verificadas; LOC aportado, con páginas preliminares y bibliografía omitidas; SEK usado como índice. El usuario declaró propios el PDF y las imágenes y autorizó su análisis. Esa autorización está resuelta.
- Falta: contraste de contenido íntegro, correcciones aplicables y naturaleza normativa/informativa de cada detalle. No se requiere redistribuir una copia de la norma.
- Alternativas: confirmar regla en texto autorizado, obtener aclaración autorizada o mantener I/U. Un índice no sustituye el contraste.
- Discriminante: una frase de LOC puede parecer mandato mientras que en el original es nota o recomendación.
- Impacto: todos los requisitos I, cierre de N y declaración global; no bloquea edición/persistencia P.
- Responsable: revisor normativo con acceso permitido. Cierre: ficha por requisito con edición, cláusula/símbolo, naturaleza, conclusión original, fecha y prueba revisada.

### U-02. Terminología y referencias locales dudosas

- Tipo: traducción y contradicción aparente. Prioridad alta.
- Evidencia: LOC §§4.7,7.3,7.4 y referencias de §6.3 usan expresiones o números que requieren contraste; «distribución» se usa para actualización memorizada; encapsulante/encapsulada se alternan de modo confuso.
- Pregunta: ¿qué sujeto y relación expresa cada frase ambigua, especialmente en forzado y encapsulación?
- Alternativas: error editorial, traducción literal o interpretación incorrecta del análisis.
- Discriminante: si un destino forzado se considera superior al origen se invierte el grafo jerárquico.
- Impacto: REQ-JER-01..06, notación y glosario; T-17..20.
- Responsable: revisor normativo. Cierre: terminología contrastada y corrección explícita de fichas, sin alterar el texto de origen ni inventar erratas oficiales.

### U-03. Alcance causal de eventos

- Tipo: interpretación no concluyente. Crítica.
- Evidencia: LOC §§4.6,4.7,4.9, tabla 4 [15],[16], tabla 6 [29].
- Pregunta: ¿qué transiciones y acciones pueden usar un evento cuando su validación o actividad aparece durante el recorrido causado por ese evento? ¿Cómo representar y evaluar eventos de franqueamiento?
- Alternativas: disponibilidad solo en situación anterior o disponibilidad en ciertas evoluciones virtuales; no deben mezclarse con cola retenida entre instantes.
- Discriminante: A→B/rise(p) y B→C/rise(p); con A activa y una subida de p, ¿termina en B o C? Acción de evento en B también distingue lecturas.
- Impacto: REQ-EVT-03, REQ-SEM-09, T-10d,T-11b; snapshots dentro del recorrido.
- Responsable: revisor de semántica. Cierre: contrato causal con ejemplos positivos/límite, localizador y oráculo aprobado.

### U-04. Permanencia activa y eventos internos

- Tipo: interpretación no concluyente. Crítica.
- Evidencia: LOC §§4.5.6,4.7,4.9. El resultado de actividad está claro; todos sus eventos y efectos no lo están.
- Pregunta: ¿qué acciones/eventos ocurren cuando la misma etapa pertenece a los conjuntos de activación y desactivación de una evolución simultánea? ¿Se conserva su duración y el contenido encapsulado?
- Alternativas: permanencia sin eventos de actividad, o existencia de determinados eventos asociados a franqueamientos sin caída de actividad; no se acepta falsa salida/reentrada.
- Discriminante: T-05b con contadores y variante temporizada/encapsulante.
- Impacto: SEM-05, EVT-03, TMP-02, JER-06.
- Responsable: revisor normativo. Cierre: tabla de eventos diferenciados y pruebas de memoria, tiempo y contenido jerárquico.

### U-05. Lecturas y escrituras en un contexto causal

- Tipo: límite entre norma e interpretación informática. Crítica.
- Evidencia: LOC §§4.8.3,4.9.5,4.10.5 y nota 3; la fuente no define por completo cálculo numérico interno.
- Pregunta: ¿qué valores leen expresiones de acciones simultáneas y sucesivas? ¿Cuándo afectan esas asignaciones a receptividades y a nuevas acciones del mismo instante?
- Alternativas: lectura de estado previo compartido, actualización causal en fronteras definidas, o rechazo de dependencia no especificada. Cualquier decisión P necesita demostrar que no sustituye regla normativa.
- Discriminantes: x:=y e y:=x con (2,5); dos incrementos n:=n+1; una asignación n:=1 seguida de receptividad n=1 en etapa virtual.
- Impacto: REQ-ACT-05, SEM-09; T-15c,T-16d y traza de efectos parciales.
- Responsable: revisor semántico y responsable de producto. Cierre: delimitar ámbito fuera de norma, fijar contrato de lectura y conflicto, aprobar oráculos y versionar perfil.

### U-06. Fronteras temporales y rebotes

- Tipo: interpretación de casos límite. Crítica.
- Evidencia: LOC tabla 4 [17],[18] y tabla 5 [23]–[25]; formas ordinarias localizadas.
- Pregunta: ¿cómo se resuelven caída exactamente al vencer un retardo, nueva subida durante retardo de caída, varios vencimientos simultáneos y condiciones inicialmente verdaderas? ¿Qué valor observable tiene T de una etapa inactiva?
- Alternativas: cancelación o vencimiento, rearme o conservación del plazo, valor cero o no aplicable para duración inactiva. No fijar por orden de cola.
- Discriminantes: T-13b,c; p true desde 0 con caída exactamente en d; dos retados que cambian condiciones mutuas.
- Impacto: TMP-02,03; instantáneas temporales y acciones retardadas/limitadas.
- Responsable: revisor normativo; P numéricas del documento 05 ya propuestas. Cierre: cronogramas por frontera, tabla de cancelación/rearme e integración causal con U-03,U-05.

### U-07. Construcciones fuente, vacías y persistentes

- Tipo: validez y evolución no cerradas. Crítica para esas construcciones.
- Evidencia: LOC §6.3; una transición fuente carece de precedentes y la sumidero de siguientes; existe referencia a uso de eventos.
- Pregunta: ¿cómo evitar confundir una fuente de nivel mantenido con repetición infinita de eventos? ¿Es válida una transición sin ambos lados? ¿Cómo cerrar inicio vacío?
- Alternativas: restricción de ejecución para ciertos modelos, evolución estable con imposición persistente o divergencia; no declarar toda fuente inválida.
- Discriminante: fuente vacía→A/true junto a A→B/p, p=true; repetición de acciones de A. Variante fuente por flanco.
- Impacto: MOD-04, SEM-01/02/07, T-01d,T-10e.
- Responsable: revisor normativo. Cierre: validez de variantes, efecto persistente y criterios de estabilidad con oráculos completos.

### U-08. Interacciones jerárquicas

- Tipo: interpretación y contradicción aparente. Crítica.
- Evidencia: LOC §7 y tablas 9–11; prioridad de forzado, actividad de encapsulación y salida de expansión están descritas por separado.
- Pregunta: ¿cómo se combinan forzado, encapsulación y macroetapas en coincidencias, retiro/reentrada, temporizadores y eventos? ¿Qué conexiones exteriores y estados residuales son válidos?
- Alternativas: construcción inválida, restricción jerárquica predominante con efecto especificado, o comportamiento no definido. Ninguna se elige por orden de recorrido.
- Discriminantes: T-18d,T-20a,c; forzar hijo activo con padre inactivo; desactivar padre al vencer timer hijo; macro con rama residual; current capturado en contextos diferentes.
- Impacto: JER-06, TMP-03, EVT-03, acciones de entrada/salida y snapshots.
- Responsable: revisor normativo. Cierre: matriz de compatibilidad y prioridad justificada, validez de conexiones, pruebas de entrada/salida/reentrada y no recursión.

### U-09. Inicialización semántica

- Tipo: interpretación pendiente. Crítica.
- Evidencia: LOC §§4.5.2,4.8.3, tabla 1 [3], tabla 10 [5],[41], tabla 11 [42].
- Pregunta: ¿qué eventos memorizados se producen al iniciar, cómo se estabilizan iniciales inestables y cómo se inicializa una condición temporal ya verdadera? ¿Cómo se combinan iniciales dentro de expansiones?
- Alternativas: situación inicial como condición elegida con memoria base, o eventos de entrada iniciales explícitos donde esté justificado; no inventar rise de entrada por leer true.
- Discriminante: etapa inicial con acción al activar n:=1 y memoria inicial 0; transición inicial true; timer sobre entrada inicialmente true.
- Impacto: SEM-01, ACT-02, TMP-02; T-01c,d,T-10a y pruebas iniciales adicionales.
- Responsable: revisor normativo. Cierre: tabla completa de inicio, reinicio e instantánea y sus eventos.

### U-10. Sistemas soportados y rendimiento

- Tipo: decisión de producto no ratificada, no normativa. Alta.
- Evidencia: ENC §14 y propuestas de 10; no hay producto medido.
- Pregunta: ¿qué versiones de Windows/macOS/Linux, arquitecturas y equipo de referencia se comprometen?
- Alternativas: soporte limitado a combinaciones verificadas o matriz más amplia con coste de prueba; no promesa genérica de todos los sistemas.
- Discriminante: modelo de referencia en equipo declarado frente a equipo mínimo más lento.
- Impacto: PLT-01..04, T-24,T-25; no afecta fórmulas semánticas.
- Responsable: responsable de producto y futura IA técnica. Cierre: matriz firmada, equipo y presupuestos aceptados; mediciones en fase de implementación.

### U-11. Ratificación de formato e intercambio

- Tipo: decisión de producto propuesta. Alta.
- Evidencia: contrato conceptual completo de 09; no existe interoperabilidad probada.
- Pregunta: ¿se aprueba versión 0.1 del formato como base de implementación y su política de compatibilidad?
- Alternativas: mantener contrato o revisar antes de versionar implementación; no depender de formato privado.
- Discriminante: receptor con versión menor desconocida y campo semántico nuevo; la política actual bloquea ejecución.
- Impacto: DAT-01..08 y casos de persistencia. Responsable: producto/segunda IA. Cierre: diccionario revisado, ejemplos de intercambio y pruebas futuras vinculadas; los campos U de Z deben completarse antes de prometer restauración total.

### U-12. Aceptación del paquete y cobertura final

- Tipo: decisión de aceptación documental. Crítica para traspaso completo.
- Evidencia: doce documentos y revisión R-01/R-02; semántica avanzada abierta.
- Pregunta: ¿qué subconjunto puede aprobarse para empezar implementación mientras se resuelven U normativas?
- Alternativas: componentes independientes de producto, o esperar cierre completo del motor; nunca etiquetar el subconjunto como conformidad total.
- Discriminante: editor puede preservar y diagnosticar macroetapas antes de que su interacción de forzado sea ejecutable.
- Impacto: todos los entregables y planificación de segunda IA.
- Responsable: responsable del proyecto. Cierre: lista explícita de requisitos aprobados, restricciones y responsables; nueva versión del manifiesto.

## Riesgos y mitigación concreta

| Riesgo | Consecuencia | Tratamiento |
|---|---|---|
| Confundir resumen con fuente íntegra | Falsa conformidad | Mantener I/U y cerrar U-01 por requisito |
| Motor basado en recorrido secuencial | Prioridades espurias | T-04 y comparación entre permutaciones |
| Suprimir etapas virtuales | Pérdida de memoria | T-07b,c y traza de eventos |
| Renderizar virtual como efectivo | Pulsos continuos falsos | T-07a y separación de observación |
| Reentrada igual a inicialización | Activación de etapas incorrectas | T-19a con iniciales y marcas diferentes |
| Guardar solo S | Restauración incorrecta | Z completo y T-23c |
| Fijar casos U con hábitos de PLC | Cambio de lenguaje | D-SEM-PENDIENTE, revisión previa de oráculo |
| Presupuestos presentados como medidos | Promesa de rendimiento falsa | U-10 e informe de medición futuro |

## Auditoría de puertas del encargo

La comprobación documental de esta entrega identifica 82 requisitos únicos, 102 casos de prueba y dos revisiones documentales. Los enlaces relativos y las referencias explícitas a IDs de pruebas/requisitos se han comprobado. Se han revisado las tablas para conservar columnas y las codificaciones UTF-8. Estas comprobaciones evalúan el paquete, no ejecutan ni validan un producto GRAFCET.

| Puerta ENC §19.1 | Estado de esta edición |
|---|---|
| 1. Doce documentos completos/coherentes | Doce presentes; especificación parcial declarada, no cierre semántico completo |
| 2. Edición y acceso | Metadatos y autorización local registrados; contraste íntegro pendiente |
| 3. Localizadores y pruebas normativas | LOC localizado, sin promoción a N; U-01 |
| 4. Cinco reglas y simultaneidad | Contratos I y pruebas; eventos avanzados U-03/U-04 |
| 5. Tiempo, eventos, conflictos | Casos ordinarios concretos; fronteras y dependencias U-05/U-06 |
| 6. Jerarquías | Tratadas; interacciones U-08 |
| 7. Separación N/I/P/E/U | Aplicada en requisitos y fuentes |
| 8. Datos y restauración | Contratos P; totalización de Z depende de U |
| 9. Pruebas normales/límites/interacciones | Catálogo de 26 familias; B no cuenta como conformidad |
| 10. Multiplataforma | Criterios definidos; versiones/equipo U-10 |
| 11. Sin cuestiones normativas críticas ocultas | Visibles; siguen abiertas, por tanto no cumple cierre completo |
| 12. Independencia y transferencia | Sin código/activos de productos ni copias de figuras en paquete |
| 13. Exclusión SFC/GRAPH | Respetada; sin implementación ni comparación obligatoria |

## Qué puede utilizar ya la segunda IA

Puede trabajar, una vez aprobado el alcance parcial, en identidades, almacenamiento de borradores, presentación independiente, edición reversible, inventario de variables, diagnósticos y gestión de revisiones. Puede preparar infraestructuras de pruebas y contratos sin elegir respuestas a U. La ejecución de eventos, inicialización y jerarquías afectadas requiere cierre semántico previo. Los casos I sirven para revisar la especificación, no para anunciar conformidad.

## Instrucción reutilizable de traspaso

> Actúa como segunda IA implementadora del paquete GRAFCET versión 0.1. Lee primero este documento y el alcance. Implementa únicamente los requisitos aprobados por el responsable, respetando los contratos y observables del paquete. Conserva libertad técnica y justifica decisiones que afecten a distribución, rendimiento o formatos. No consultes ni copies código, activos, pantallas ni detalles internos de productos de referencia. Trabaja en contexto separado con este paquete y fuentes normativas cuyo acceso esté autorizado; no necesitas el historial completo de investigación.
>
> No sustituyas U por hábitos de PLC, SFC o GRAPH. Registra contradicciones nuevas y devuelve la cuestión con un caso discriminante antes de fijar un comportamiento. No alteres un oráculo para que coincida con tu implementación. Mantén trazabilidad entre requisito, cambio y prueba. Conserva las distinciones entre modelo y presentación, situación y estado completo, actividad y franqueamiento, transitorio y efectivo, forzado normativo e intervención de depuración.
>
> Antes de afirmar conformidad, exige contraste de las fuentes, cierre de semántica crítica y ejecución de las pruebas con evidencia reproducible en los sistemas soportados. Informa capacidades pendientes y desviaciones. No uses afirmaciones de certificación IEC, aprobación UNE ni seguridad funcional. Si solo se aprueba trabajo parcial, publica exactamente su cobertura y mantén bloqueadas las capacidades sin oráculo.

## Próxima revisión necesaria

La siguiente versión debe centrarse primero en U-01/U-02 y el bloque causal U-03–U-06/U-09, después en U-07/U-08. Las decisiones P independientes pueden revisarse en paralelo como materias, sin requerir múltiples agentes. El cierre de cada cuestión debe actualizar requisitos, pruebas, perfil y manifiesto de manera conjunta. No hace falta volver a pedir al usuario permiso para analizar el material local ya autorizado.
