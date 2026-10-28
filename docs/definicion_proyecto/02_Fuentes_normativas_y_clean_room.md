# 02. Fuentes normativas y separación de materiales

Versión 0.1 · 24 de octubre de 2026 · Estado: inventario revisado; verificación normativa parcial.

## Propósito

Registrar lo consultado y su autoridad. Dependencias: [alcance](01_Alcance_y_objetivos.md), [matriz](11_Trazabilidad_y_plan_de_pruebas.md), [pendientes](12_Decisiones_pendientes_y_traspaso.md). Este documento es la definición canónica de los IDs de fuente.

## Inventario y evidencia

| ID | Fuente, idioma y acceso | Consulta y autoridad | Restricción y uso |
|---|---|---|---|
| ENC | Encargo_IA_analista_GRAFCET_IEC_60848.md; español; aportado por usuario | Leído completo por secciones; requisitos del proyecto, no norma | Se sintetiza en requisitos originales |
| IEC-CAT | [Ficha IEC](https://webstore.iec.ch/en/publication/3684); inglés; pública | Verificada: edición 3.0, publicación 2013-02-27; alcance de lenguaje de especificación | Solo metadatos; no prueba de reglas concretas |
| UNE-CAT | [Ficha AENOR](https://tienda.aenor.com/p/norma-une-en-60848-2022-n0069711); español; pública | Verificada: 2022-05-25; idéntica a IEC/EN 60848:2013; sustituye adopción 2013 | La página publica restricción de uso de contenidos protegidos en IA; no se ha comprado ni descargado una norma desde ella |
| SEK-IDX | [Vista previa SEK](https://elstandard.se/documents/preview/1245201); inglés; pública | Consultado índice de edición 3.0; apoyo a localizadores | No acredita lectura completa ni licencia del documento local |
| LOC | Resumen de norma UNE Grafcet.pdf; español; carpeta aportada | 58 páginas PDF. Texto revisado; revisión visual focalizada en transitorios, temporización y jerarquías | Usuario declara materiales propios y autoriza análisis, en esta conversación. No se incluye el PDF ni sus figuras en transferencia |
| IMG | Imagenes UNE GRAFCET; 116 PNG en el directorio principal | Inventario de nombres; inspección focalizada en encapsulación y macroetapas | Misma autorización del usuario; no se redistribuyen ni se emplean como activos de aplicación |
| AUX | Subcarpeta Claude outputs | Inventariada por existencia/extensión; contenidos no utilizados | No se presupone corrección, licencia ni pertenencia al encargo; no se transfiere |

Fecha de consulta de todas las fichas: 2026-10-24. La fecha de estabilidad que aparece en el catálogo IEC no se interpreta como certificación ni garantiza inexistencia de correcciones. La revisión de correcciones aplicables permanece U-01.

La carpeta completa contiene 1 MD, 5 PDF, 116 PNG, 2 PPTX y 6 archivos MBZ. Solo ENC, LOC y las imágenes indicadas son fuentes locales de análisis; no se ha abierto código ni material interno de productos de referencia.

## Naturaleza del PDF local

Aunque su nombre indica «Resumen», sus páginas conservan encabezados UNE-EN 60848:2022, números de cláusula y paginación impresa. El archivo comienza con el índice y omite páginas preliminares; termina en el anexo C y no incluye la bibliografía anunciada. La autorización del usuario para analizarlo queda registrada. No se deduce de ella que se haya contrastado una copia íntegra oficial, ni se reconstruye una licencia de terceros.

Se utiliza LOC como fuente aportada de apoyo con localizador exacto. Se asigna I a conclusiones claras y U a ambigüedades. El salto a N requiere la comprobación de U-01; no bastará cambiar la etiqueta en bloque. Las pruebas deberán revisarse junto con cada afirmación.

## Mapa de localización local

| Materia | Localizador LOC | Página del PDF / impresa |
|---|---|---|
| Conceptos y contexto | §§1–4.3 | 4–10 / 11–17 |
| Sintaxis y cinco reglas | §§4.4–4.5.6 | 11–12 / 18–19 |
| Eventos y modos de salida | §§4.6–4.8 | 12–14 / 19–21 |
| Transitorios y conflictos | §§4.9–4.10 | 14–17 / 21–24 |
| Símbolos de etapas, transiciones, enlaces | §5, tablas 1–3 | 18–21 / 25–28 |
| Receptividades, flancos, tiempo | §5, tabla 4 | 22–25 / 29–32 |
| Acciones y comentarios | §5, tablas 5–7 | 26–33 / 33–40 |
| Estructuras básicas y particulares | §6 | 33–39 / 40–46 |
| División y forzado | §§7.2–7.3, tablas 8–9 | 40–42 / 47–49 |
| Encapsulación | §7.4, tabla 10 | 43–46 / 50–53 |
| Macroetapas | §7.5, tabla 11 | 47–48 / 54–55 |
| Ejemplos informativos | Anexos A–B | 49–56 / 56–63 |
| Relación con otros lenguajes | Anexo C, informativo | 57–58 / 64–65; fuera del desarrollo solicitado |

Los nombres Pxx de las imágenes parecen corresponder a páginas del PDF local, no a páginas impresas de la norma. No se utilizan como localizadores normativos autónomos. Las notas y ejemplos se identifican como informativos; no se convierten en mandatos por aparecer junto a una tabla.

## Observaciones de calidad de fuente

Se detectan referencias internas que no coinciden con la numeración visible, traducciones poco claras («distribución», «etapa encapsulada» usada donde el contexto parece requerir «encapsulante») y una frase jerárquica del forzado que aparenta invertir sujeto y objeto. Se registran U-02 y U-08; no se corrigen silenciosamente ni se propagan como requisitos N.

La regla de permanencia activa no basta para resolver todos los eventos de una etapa alcanzada por activación y desactivación simultáneas. La descripción temporal no cierra por sí sola todos los casos de rebote y coincidencia. Esas insuficiencias se concretan en el documento 12.

## Requisitos de procedencia

Aplican los metadatos comunes del documento 01.

| ID | Clase/prioridad | Obligación | Dependencia/fuente | Prueba |
|---|---|---|---|---|
| REQ-CR-01 | P/crítica | Cada conclusión normativa debe conservar fuente, localizador, naturaleza, evidencia y nivel de incertidumbre | ENC §§1,4,15 | R-01 |
| REQ-CR-02 | P/crítica | La segunda IA debe recibir únicamente este paquete y acceso autorizado a referencias, sin historial de investigación ni fuentes excluidas | ENC §2.2 | R-02 |
| REQ-CR-03 | P/crítica | Una contaminación detectada debe registrarse por alcance, suspender su uso y provocar revisión de requisitos derivados | ENC §2.2 | R-02 |
| REQ-CR-04 | P/alta | Ninguna prueba debe usar el comportamiento de otro producto como oráculo normativo | ENC §16 | R-01 |

## Separación de roles

El espacio de investigación conserva fuentes locales y revisión de procedencia. El paquete de transferencia consiste en los doce Markdown originales. La segunda IA debe trabajar en un contexto nuevo, con acceso al paquete y a fuentes cuya consulta esté permitida. No se afirma aislamiento absoluto del entrenamiento del modelo. Tampoco se considera que dos papeles dentro del mismo chat demuestren separación de contextos.

Ante material excluido: registrar nombre y naturaleza sin reproducir contenido, identificar los requisitos afectados, detener su utilización, reconstruir desde fuentes permitidas y someterlos a revisión. No se han utilizado implementaciones, repositorios o capturas de productos en esta edición.

## Pendientes

U-01: integridad, correcciones y contraste autorizado de la edición. U-02: terminología y referencias dudosas. U-08: interacciones jerárquicas. El usuario ya autorizó el análisis de sus materiales; no se vuelve a solicitar esa autorización. El cierre pendiente es técnico y documental, no una repetición de aquella pregunta.
