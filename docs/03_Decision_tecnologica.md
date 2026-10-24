# 03. Decisión tecnológica (propuesta)

Estado: **propuesta de la segunda IA**. Pendiente de aceptación por el responsable de producto. No compromete la matriz de sistemas, versiones ni equipo de referencia: eso sigue siendo U-10.

## 1. Decisión

| Capa | Tecnología propuesta | Estado en esta iteración |
|---|---|---|
| Núcleo: modelo, validación, expresiones, motor, trazas, persistencia, operaciones de edición | **Python ≥ 3.12, solo biblioteca estándar** (sin dependencias de terceros) | Implementado (`grafcet/`) |
| Pruebas y trazabilidad | `unittest` de la biblioteca estándar y scripts propios en `tools/` | Implementado |
| Interfaz de escritorio (editor gráfico, accesibilidad, exportación PDF) | **Qt 6 mediante PySide6 (LGPL, enlace dinámico)** | No iniciado: requiere instalar la dependencia y ratificar U-10 |
| Distribución | Paquete instalable por plataforma (p. ej., PyInstaller o Briefcase) sin servidor | No iniciado: depende de U-10 |

Arquitectura de **puertos y adaptadores**. El núcleo no importa nada de la interfaz ni del sistema operativo; el acceso a ficheros pasa por un único adaptador. Así se cumple REQ-ARQ-01: todo el contrato semántico se verifica sin interfaz, y la interfaz futura usará los mismos contratos y perfiles.

## 2. Justificación frente a los requisitos

| Requisito / contrato | Cómo lo cubre la elección |
|---|---|
| Entero de 64 bits, decimal exacto de hasta 18 cifras, tiempo en µs hasta 2^63−1 sin redondeo (05, REQ-TMP-01, REQ-EXP-01) | `int` de precisión arbitraria con comprobación explícita de rango (D-NUM) y `fractions.Fraction` para aritmética decimal exacta. No se usa coma flotante en ningún dato semántico |
| SHA-256 sobre representación canónica (09, REQ-DAT-05) | `hashlib`. El serializador canónico es propio (claves por punto de código, escapes definidos), porque `json.dumps` no cumple el contrato de escapes |
| NFC, IDs ASCII, Unicode en etiquetas y rutas (09, REQ-PLT-02) | `unicodedata` y `str` Unicode nativo; nombres de fichero hexadecimales propios |
| Guardado atómico y recuperación (REQ-DAT-07, REQ-EDT-10) | `os.replace` (atómico en el mismo volumen en Windows y POSIX), `os.fsync` y diario de confirmación propio |
| Archivos sin ejecución de código (REQ-DAT-06) | El lector JSON rechaza flotantes, NaN, claves duplicadas y profundidad excesiva. Nunca se usa `eval`, `pickle` ni importación dinámica |
| Determinismo entre sistemas (REQ-PLT-01, REQ-SEM-08) | El comportamiento de `int`, `Fraction`, `str` y del orden de claves es idéntico en las tres plataformas. Los conjuntos se ordenan por ID al serializar. Ninguna lógica depende del reloj del sistema ni de la configuración regional |
| Sin conexión y sin servicios de terceros (REQ-ALC-01, REQ-PLT-03) | Biblioteca estándar únicamente; ninguna llamada de red |
| Independencia y procedencia (REQ-CR-02/03/04) | Cero dependencias en el núcleo: ni código ajeno ni licencias que auditar en la parte semántica |
| Editor accesible multiplataforma (REQ-EDT-13, matriz de 10) | Qt 6 expone su accesibilidad a UIA (Windows), NSAccessibility (macOS) y AT-SPI (Linux). Ofrece escalado de alta densidad, navegación por teclado, `QGraphicsView` para diagramas extensos y exportación con `QSvgGenerator`/`QPdfWriter` |
| Rendimiento de los presupuestos de 10 | Las operaciones del núcleo son lineales o casi lineales en el tamaño del modelo. Hay que medirlo (REQ-PLT-04); si algún presupuesto no se alcanza, el núcleo puede portarse a un lenguaje compilado sin cambiar formato ni trazas, porque el contrato son los datos y no el lenguaje |

## 3. Alternativas consideradas

| Alternativa | Ventajas | Motivo para no elegirla ahora |
|---|---|---|
| TypeScript + Tauri 2 (webview del sistema) | Un solo lenguaje; SVG/DOM y ARIA para el editor; binarios pequeños | Los tres webviews (WebView2, WKWebView, WebKitGTK) difieren en dibujo y accesibilidad, y la de Linux es la más débil. Exige disciplina con `BigInt` en todo el núcleo. Además, no hay cadena Node en este equipo |
| TypeScript + Electron | Chromium idéntico en las tres plataformas | Distribución pesada. Buena alternativa si el responsable prefiere una interfaz web |
| C# / .NET 8 + Avalonia | `long`, `decimal` de 28 dígitos y SHA-256 nativos | Accesibilidad en Linux menos madura; no hay SDK en este equipo |
| Rust (núcleo) + interfaz aparte | Máximo rendimiento y determinismo | Mayor coste de desarrollo. Queda como opción de portado del núcleo si las mediciones de U-10 lo exigen |

Factor práctico, declarado para no ocultarlo: Python 3.12 ya está instalado en este equipo, así que el núcleo y sus pruebas se pueden ejecutar ahora con evidencia reproducible sin descargar nada. No es la razón principal: la elección se justifica por las filas de la sección 2.

## 4. Riesgos de la elección

| Riesgo | Mitigación |
|---|---|
| Rendimiento de Python en el modelo de referencia (5 000 etapas) | `tools/medir_presupuestos.py` da una medición indicativa. La aceptación exige el equipo de U-10 |
| Distribución de un intérprete en tres sistemas | Empaquetado congelado por plataforma; se prueba en la fase de U-10 |
| Licencia LGPL de Qt/PySide6 | Enlace dinámico y aviso de licencias. Alternativa: licencia comercial de Qt |

## 5. Lo que no se decide aquí

- Versiones concretas de Windows, macOS y Linux, arquitecturas y equipo de referencia (U-10).
- La ratificación del formato 0.1 (U-11). El formato se implementa como **provisional**: cada documento declara `formatVersion` "0.1".
