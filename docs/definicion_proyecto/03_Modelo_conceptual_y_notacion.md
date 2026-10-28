# 03. Modelo conceptual y notación

Versión 0.1 · Estado: conceptos especificados; notación e interpretación I pendientes de contraste.

## Propósito y referencias

Definir identidad, estructura y validez. Dependencias: [fuentes](02_Fuentes_normativas_y_clean_room.md), [evolución](04_Semantica_de_evolucion.md), [jerarquías](06_Estructuracion_y_jerarquias.md), [datos](09_Datos_y_contratos.md). Fuentes: LOC §§3–7 y ENC §5. Abiertos: U-01, U-02, U-07, U-08.

## Diccionario canónico

| Concepto | Definición de trabajo y atributos | Identidad, cardinalidad y observables |
|---|---|---|
| Proyecto | Contenedor de modelos, escenarios y presentación | ID estable; uno o más modelos; revisión independiente por modelo |
| Modelo / grafcet global | Especificación lógica completa de un sistema delimitado | Un conjunto de parciales y variables; ningún orden de enumeración expresa prioridad |
| Grafcet parcial | Agrupación de uno o más componentes conectados | ID y etiqueta; propiedad de sus elementos; actividad derivada de sus etapas |
| Etapa | Elemento binario de la situación | ID, etiqueta, parcial, indicador inicial; 0..n acciones; 0..n conexiones por lado |
| Etapa inicial | Etapa incluida en la situación inicial elegida | Atributo del modelo; no se cambia al pausar, detener ni cargar instantánea |
| Situación S | Conjunto de identidades de etapas activas | Pertenencia, no número de fichas; sin duplicados |
| Actividad X(s) | Verdadero si s pertenece a S | Derivada, solo lectura; no variable editable por una acción |
| Duración T(s) | Tiempo asociado a actividad continuada de s | Inicio y cancelación según documento 05; no es un temporizador de PLC |
| Transición | Relación entre conjuntos de precedentes y siguientes | ID, etiqueta opcional, receptividad exactamente una; aridades variables |
| Receptividad | Condición booleana asociada a una transición | Expresión ejecutable o texto de especificación pendiente |
| Enlace orientado | Relación etapa→transición o transición→etapa | Extremos por ID; ruta visual separada |
| Evento | Cambio contextualizado, con valores anteriores/posteriores y causa | Identidad causal; no ficha consumible de una cola de mensajes |
| Acción | Relación de etapa/evento con salida o variable interna | Modo, objetivo, condición o disparador, expresión de valor |
| Orden de forzado | Imposición jerárquica de situación sobre otro parcial | Origen, destino y forma de situación; no acción sobre variable |
| Macroetapa | Referencia a expansión con entrada y salida | Propietario único de expansión; actividad derivada; no etapa ordinaria |
| Encapsulante | Etapa que contiene uno o varios recintos | Cada recinto pertenece a una encapsulante; activación de entrada explícita |
| Vista | Presentación de un mismo modelo | Coordenadas, zoom, pliegues y filtros; nunca cambia S |
| Escenario | Datos de inicialización y estímulos ordenados/agrupados | Vinculado a revisión y configuración; no modifica el documento |
| Estado de ejecución | Situación más valores, memorias, reloj y fase | Restaurable solo con compatibilidad semántica exacta |

«Conectado» se refiere a conexión estructural entre elementos ignorando el sentido para pertenencia al componente; no exige alcanzabilidad dirigida de cada etapa desde todas las otras. Esta precisión es I con LOC §7.2.1 y requiere contraste U-02. No se aplica la nota de falta de sentido tecnológico de un grafcet desconectado para prohibir un parcial compuesto de varios conectados.

## Representación gráfica original descrita

| Elemento | Representación requerida como interpretación I de LOC | Fuente |
|---|---|---|
| Etapa / inicial | Contorno rectangular con etiqueta / doble contorno | Tabla 1 [1],[3] |
| Actividad | Indicador adicional distinguible; punto explicativo y texto accesible | Tabla 1 [1], nota; presentación P |
| Transición | Trazo transversal al enlace; receptividad próxima, designación separada | Tabla 2 [7],[8] |
| Varios precedentes o siguientes de una transición | Doble barra de sincronización que agrupa enlaces de esa transición | Tabla 2 [9] |
| Alternativas | Varias transiciones diferentes conectadas a la misma etapa o grupo | §6.2.3 |
| Enlace ascendente | Dirección visible mediante flecha; descendente puede usar convención habitual | Tabla 3 [10],[11] |
| Enlace interrumpido | Referencia visible a destino y página/vista; enlace semántico único | Tabla 3 [12] |
| Acción continua | Rectángulo asociado a etapa; objetivo y condición si la hay | Tabla 5 [20]–[25] |
| Memorizada | Rectángulo con indicación explícita de evento de activación, desactivación o evento condicionado | Tabla 6 [26]–[29] |
| Forzado | Rectángulo doble con destino y situación impuesta | Tabla 9 [37] |
| Macroetapa | Rectángulo con divisiones horizontales superior e inferior; enlace a expansión | Tabla 11 [6] |
| Encapsulante | Contorno con marcas internas de encapsulación; doble contorno si inicial | Tabla 10 [4],[5] |
| Entrada a recinto | Marca de activación independiente de etapa inicial | Tabla 10 [41] |
| Comentario | Texto entre comillas, asociado por ID | Tabla 7 [30] |

Dimensiones, fuente, grosor y paleta son decisiones P. La geometría exacta de las marcas de encapsulación debe contrastarse en U-01 antes de aceptación visual; no se proporciona un activo copiado. El editor debe conservar el símbolo global reconocible y no sustituirlo únicamente por un icono propio.

## Invariantes y requisitos

| ID | Clase/prioridad | Obligación y rechazo | Fuente/dependencias | Casos |
|---|---|---|---|---|
| REQ-MOD-01 | P/crítica | Todo elemento debe tener ID único, propietario y referencias existentes; duplicados o huérfanos impiden simulación | ENC §13 | T-21b, T-22b |
| REQ-MOD-02 | I/crítica | Los enlaces deben respetar alternancia; etapa→etapa y transición→transición se diagnostican | LOC §4.4 | T-21b |
| REQ-MOD-03 | P/crítica | Cruzar líneas no debe conectar elementos; conectar requiere relación explícita | ENC §5; LOC tabla 3 | T-21c |
| REQ-MOD-04 | I/alta | Deben representarse fuentes y sumideros sin inventar precedentes/siguientes | LOC §§6.3.1–6.3.4; U-07 | T-03c, T-10e |
| REQ-MOD-05 | P/alta | Texto libre sin significado ejecutable debe conservarse como borrador y bloquear el inicio indicando su ubicación | ENC §5 | T-09c |
| REQ-MOD-06 | P/crítica | Renombrado, desplazamiento y orden de archivo no deben cambiar comportamiento si se conservan referencias | ENC §§5,16.4 | T-04c, T-21d |
| REQ-MOD-07 | I/alta | Macroetapas y recintos deben conservar pertenencia única y referencias jerárquicas consistentes | LOC §7; documento 06 | T-18c, T-19c |

Un enlace duplicado entre los mismos extremos es error de datos, no duplicación de actividad. Una misma etapa puede ser precedente y siguiente de una transición: no se prohíbe por esa circunstancia; se aplica regla 5. Una transición fuente tiene cero precedentes; una sumidero cero siguientes. La transición sin ambos lados se conserva como borrador con U-07 y no se declara normativamente inválida sin contraste.

## Ámbitos y nombres

Los nombres visibles pueden repetirse en distintos ámbitos; un nombre corto dentro de un ámbito debe resolver a una sola entidad. La representación textual usa referencias calificadas cuando existe ambigüedad. El ID, no la etiqueta, mantiene el vínculo. La búsqueda no elimina distinciones por mayúsculas; la política de identificadores se fija en el documento 09.

Variables: entrada (escrita por escenario), interna (por acciones) y salida (por su modo de determinación). Actividad de etapa, parcial y macroetapa son lecturas derivadas. No se permite escribir una entrada mediante acción ni manipular una actividad derivada con una asignación ordinaria. La depuración es intervención separada.

## Ejemplo estructural original

Un parcial G contiene A inicial, B y C. t1 tiene precedentes {A}, siguientes {B,C} y receptividad inicio. t2 tiene precedentes {B,C}, siguientes {A} y receptividad fin. La primera relación es una divergencia simultánea; la segunda sincroniza ambas ramas. Dibujar B encima de C o invertir su orden de almacenamiento no cambia estas relaciones. Las transiciones alternativas serían dos entidades distintas, no dos salidas de t1.
