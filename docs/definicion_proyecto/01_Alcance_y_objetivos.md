# 01. Alcance y objetivos

Versión 0.1 · 24 de octubre de 2026 · Estado: preparado parcialmente.

## Propósito y lectura

Especificar un editor y simulador GRAFCET independiente, destinado a describir, examinar y explicar comportamientos secuenciales. Este paquete contiene requisitos y pruebas de aceptación declarativas; no contiene una implementación. La base objetivo es IEC 60848:2013, edición 3.0, con adopción española UNE-EN 60848:2022. Identidad y equivalencia verificadas en las fichas oficiales; la conformidad completa del producto no se declara.

Dependencias: [fuentes y autorización](02_Fuentes_normativas_y_clean_room.md), [conceptos](03_Modelo_conceptual_y_notacion.md), [estado de traspaso](12_Decisiones_pendientes_y_traspaso.md). Referencia de requisitos de origen: ENC, §§0–4 y 18–20, definido en el documento 02. Cuestiones abiertas: U-01 a U-12 del documento 12.

## Usuarios y resultados

| Usuario | Necesidad | Resultado observable |
|---|---|---|
| Diseñador | Expresar secuencias, alternativas, paralelismo y jerarquías | Modelo editable y validación con localización de problemas |
| Docente o estudiante | Comprender por qué evoluciona un grafcet | Situaciones, transiciones y causas visibles; transitorios diferenciados |
| Revisor | Contrastar un comportamiento esperado | Escenario reproducible, traza y comparación con un oráculo independiente |
| Implementador posterior | Construir sin copiar otro producto | Contratos, prioridades, pruebas y límites explícitos |

El caso principal comprende crear un proyecto, declarar variables, dibujar y validar, definir un escenario, iniciar, observar una evolución, pausar, guardar y reproducir. Un borrador incompleto puede guardarse; no adquiere por ello capacidad de simulación.

## Frontera del producto

Incluye edición, validación, interpretación, simulación lógica, observación, persistencia abierta, exportación legible y funcionamiento sin conexión en Windows, macOS y Linux. Incluye grafcets parciales, forzado normativo, macroetapas y encapsulación en el objetivo de cobertura; sus pendientes no se convierten en exclusiones definitivas.

Quedan fuera SFC y GRAPH, generación de programas PLC, conexión a equipos reales, simulación física de instalaciones, ingeniería inversa, formatos privados y clonación de productos. No se especifica una garantía de seguridad funcional. Una futura integración solo podrá intercambiar entradas y observables a través de contratos públicos, sin modificar el significado del modelo.

No se exige apariencia, comportamiento ni compatibilidad de FluidLab u otra herramienta. No se selecciona lenguaje de programación, biblioteca ni plataforma técnica.

## Convenciones de requisitos

Las clases son N (norma comprobada), I (interpretación respaldada, pendiente de contraste), P (decisión de producto), E (extensión) y U (no resuelto). En esta edición no se eleva a N una regla obtenida únicamente del material local: sus localizadores se han leído, pero falta acreditar integridad y contraste con la edición normativa completa. Los requisitos I son propuestas precisas para revisión, no autorización para afirmar conformidad.

Prioridades: crítica (afecta significado, integridad o independencia), alta (función necesaria), media (facilidad de uso). Estado de P: especificado, pendiente de aceptación del producto. Estado de I: provisional, pendiente de contraste normativo. U: bloqueado en la materia indicada. Responsable P: responsable del producto; I/U normativos: revisor de norma con acceso autorizado; implementación y evidencia futura: segunda IA y revisor de pruebas.

Cada tabla de requisitos debe leerse con esta ficha común: precondición = documento o ejecución identificados y dentro del dominio declarado; entradas = operación y datos nombrados en la fila; resultado = enunciado y tabla canónica referenciada; error = rechazo diagnosticado sin cambio parcial, salvo pausa de ejecución expresamente descrita; límites = documento 10; dependencias = documentos enlazados y U citados; evidencia futura = datos antes/después, diagnóstico y traza del caso vinculado. Una fila que modifica estos valores lo indica expresamente. Esta herencia evita repetir metadatos sin eliminar campos de la ficha.

Los IDs son estables. Una revisión no reutiliza un ID retirado para otra obligación. Las tablas de comportamiento de cada documento forman parte de los requisitos que las referencian. Todas las pruebas están diseñadas, nunca ejecutadas contra un producto en esta fase.

## Requisitos de alcance

| ID | Clase/prioridad | Enunciado verificable y límites | Fuente | Aceptación |
|---|---|---|---|---|
| REQ-NOR-01 | P/crítica | El proyecto debe declarar edición, perfil semántico y cobertura; no debe sustituir 2013 silenciosamente | ENC §1 | T-22e |
| REQ-NOR-02 | P/crítica | La declaración de conformidad debe excluir toda materia con U crítico pendiente e identificarla | ENC §§17,19 | Revisión R-01 |
| REQ-ALC-01 | P/alta | El usuario debe poder completar el caso principal sin servicios de terceros | ENC §3 | T-21a, T-24d |
| REQ-ALC-02 | P/crítica | La transferencia debe contener solo los doce Markdown originales y referencias; ninguna implementación ni figura de origen | ENC §§2,18 | R-02 |
| REQ-ALC-03 | P/alta | Toda capacidad del objetivo debe estar marcada como especificada, provisional o pendiente; no debe ocultarse como exclusión | ENC §1.3 | R-01 |

## Glosario de lectura

Las definiciones canónicas están en el documento 03. En este paquete «franqueamiento» y «disparo» designan el mismo hecho; «validada» y «habilitada» describen la condición estructural. «Receptividad» es la condición de transición. Se usa «acción memorizada»; «distribución», presente en la fuente local, no significa reparto entre consumidores. «Microavance» y «avance hasta estabilización» son controles P, no vocabulario atribuido a IEC.

Una situación identifica etapas activas. Un estado de ejecución incluye además memorias, valores y tiempo. Un proyecto no es una instantánea. Una instantánea no es una nueva situación inicial normativa. La jerarquía de comportamiento no es el nivel de zoom.

## Puertas de aceptación

1. Revisión documental: doce archivos, referencias resueltas, requisitos vinculados a pruebas y U visibles.
2. Revisión normativa: acceso y edición acreditados; cláusulas, tablas, notas y correcciones contrastadas; semántica crítica cerrada.
3. Revisión de transferencia: fuentes permitidas, ejemplos originales, ausencia de código y activos ajenos.
4. Aceptación futura: ejecución de pruebas de semántica, persistencia, editor, robustez y portabilidad con evidencia reproducible.

La presente edición permite preparar los componentes independientes de las U. No autoriza cerrar el motor como conforme ni afirmar que las pruebas futuras han pasado.
