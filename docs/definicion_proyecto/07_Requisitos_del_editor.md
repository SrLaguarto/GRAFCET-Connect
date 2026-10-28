# 07. Requisitos del editor

Versión 0.1 · Estado: especificado P; sujeto a aceptación del producto.

## Propósito y dependencias

Definir operaciones observables sin copiar una interfaz. Referencias: ENC §11; [modelo](03_Modelo_conceptual_y_notacion.md), [datos](09_Datos_y_contratos.md), [plataformas](10_Arquitectura_conceptual_y_multiplataforma.md). Pendientes: U-10 para plataformas y presupuestos; U-01 para fidelidad normativa de todos los símbolos. Los requisitos de esta sección son P, prioridad alta, salvo donde se indique crítica. Metadatos de ficha según 01.

## Flujos e historias de aceptación

| ID | Como usuario necesito… / obligación | Precondición y operación | Resultado verificable y errores | Casos |
|---|---|---|---|---|
| REQ-EDT-01 | Crear, abrir, cerrar, duplicar y organizar proyectos y parciales | Proyecto nuevo o archivo seleccionado | Nuevo proyecto con ID propio; duplicación sin compartir identidades; cierre con cambios ofrece guardar, descartar o cancelar; fallo de lectura no destruye proyecto abierto | T-21a |
| REQ-EDT-02 | Insertar, conectar y editar propiedades | Borrador editable | Crear etapa, transición, receptividad y acción; conexión solo por operación explícita; borrador inválido marcado y guardable | T-21b,c |
| REQ-EDT-03 | Mover, alinear, distribuir, ampliar y desplazar | Selección válida | Solo cambia presentación; una distribución no renumera ni reconecta; deshacer recupera coordenadas | T-04c, T-21c |
| REQ-EDT-04 | Copiar y pegar fragmentos sin referencias accidentales | Fragmento con relaciones interiores y exteriores | Cada entidad copiada recibe ID nuevo; relaciones internas apuntan a copias; externas requieren mantener vínculo explícito o dejar referencia pendiente; se muestra decisión antes de confirmar | T-21e |
| REQ-EDT-05 | Deshacer y rehacer atómicamente | Operación semántica o gráfica completada | Una acción compuesta se revierte completa, incluida jerarquía; operación fallida no entra en historial; nueva edición descarta rama de rehacer | T-21f |
| REQ-EDT-06 | Renombrar y buscar símbolos, variables y usos | Entidad seleccionada | Vista previa de usos; actualizar etiquetas sin cambiar ID; colisión de nombre en ámbito diagnosticada; búsqueda navega al elemento aunque esté plegado | T-21d |
| REQ-EDT-07 | Gestionar diccionario de variables | Variable nueva o existente | Rol, tipo, dominio, unidad, valor inicial, ámbito y usos visibles; cambio incompatible muestra receptividades/acciones afectadas | T-09b, T-21d |
| REQ-EDT-08 | Navegar entre jerarquías | Macroetapa o encapsulante | Ruta visible; ir y volver conserva selección/contexto; actividad y errores interiores siguen indicados en vista plegada | T-21g |
| REQ-EDT-09 | Corregir errores con evidencia | Validación solicitada o diagnóstico actualizado | Código, severidad, elemento, explicación, dependencia y corrección posible; seleccionar diagnóstico enfoca referencia; no borra el modelo para «reparar» | T-21b, T-09c |
| REQ-EDT-10 | Recuperar trabajo tras cierre inesperado | Cambios desde último guardado | Autoguardado de recuperación separado cada 30 s si hay cambios, con revisión y fecha; al abrir ofrece comparar/recuperar sin sobrescribir versión válida | T-22d |
| REQ-EDT-11 | Exportar representación legible | Vista o modelo elegido | SVG/PDF futuro con leyenda, referencias y revisión; exportación de modelo desplegado evita cortar símbolos; exportar no modifica modelo ni incorpora estado de otra revisión | T-21h |
| REQ-EDT-12 | Trabajar con diagramas extensos | Modelo dentro del presupuesto | Vista general, zoom, filtros y navegación por búsquedas; filtros indican elementos ocultos y nunca excluyen semántica de simulación | T-21g, T-25a |
| REQ-EDT-13 | Operar mediante teclado y percibir estados | Sin ratón | Operaciones esenciales accesibles, foco visible, etiquetas textuales y estados distinguibles sin color | T-26a,b |
| REQ-EDT-14 | Editar sin invalidar silenciosamente la simulación | Ejecución en curso o pausada | Edición semántica crea revisión nueva y exige ejecución nueva; ejecución anterior conserva revisión inmutable. Cambios de vista pueden mantener ejecución | T-23d |

REQ-EDT-04, 05, 06, 10 y 14 tienen prioridad crítica por integridad. El producto puede mostrar cualquier disposición original de paneles que satisfaga estas operaciones; no se prescribe una pantalla de un fabricante.

## Borrado y reparación

Eliminar una entidad debe mostrar las dependencias afectadas. La operación puede eliminar también relaciones dependientes declaradas en la confirmación local o conservar referencias incompletas como borrador; nunca reasigna a otra entidad con etiqueta parecida. El comportamiento elegido se guarda en la transacción y se revierte con un solo deshacer. Borrar una macroetapa con expansión propia incluye su contenido, previa presentación de alcance. No elimina variables externas compartidas sin declaración expresa.

## Estados del documento

| Estado | Guardar | Simular | Edición |
|---|---|---|---|
| Borrador incompleto | Sí, preserva texto y diagnóstico | No; indica causas | Libre |
| Estructuralmente válido, expresión sin interpretar | Sí | No | Libre |
| Validado con capacidades U necesarias | Sí | Bloqueado en esas capacidades; no ejecución silenciosa con aproximaciones | Libre |
| Ejecutable para perfil aprobado | Sí | Sí | Nueva revisión para cambios semánticos |
| Archivo con semántica futura desconocida | Preservar original; sin guardar transformaciones destructivas | No | Lectura o rechazo explicativo |

La validación distingue sintaxis, tipos, referencias, estructura, coherencia jerárquica y capacidad semántica. Una advertencia sobre posible no exclusividad no convierte automáticamente alternativas en exclusivas. Un error dinámico no se presenta como prueba de invalidez de toda una clase de construcciones.

## Accesibilidad de producto

P: contraste mínimo propuesto 4,5:1 para texto ordinario y 3:1 para texto grande/indicadores esenciales; no se afirma auditoría de una norma de accesibilidad. Foco visible en cada operación. Activa, inicial, transitoria y forzada deben tener texto/forma además de color. A 200 % de escalado se conservan controles y navegación. Diagrama dispone de lista estructural equivalente con etiquetas accesibles, relaciones y diagnósticos; una imagen por sí sola no basta.

La exportación debe distinguir estados de simulación de símbolos normativos: una leyenda identifica actividad y marcas de diagnóstico como presentación adicional. Las notas del usuario se conservan, pero no se ejecutan.
