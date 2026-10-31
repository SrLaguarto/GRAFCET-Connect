# Revisión visual: segunda propuesta

Esta propuesta toma la composición de la referencia: superficies blancas, fondo menta suave, encabezados de sección, iconos de línea y categorías horizontales en el editor de bloques.

- Más espacio al GRAFCET: sin selección, Propiedades ocupa una franja compacta. Con selección toma el alto necesario. Si se mueve el divisor manualmente, se respeta ese reparto.
- Paleta en una columna, como la referencia, con cuatro secciones y catorce fichas. Filas de 34 px y encabezados diferenciados; el desplazamiento mantiene todos los elementos accesibles.
- Barra con iconos propios de línea y etiquetas breves. Los textos completos de los menús se conservan.
- Categorías de bloques en una franja horizontal. En editores estrechos se desplazan lateralmente; las pruebas comprueban que cada botón puede verse completo. Colores de bloques más próximos al lenguaje menta, conservando categorías y símbolos.
- E/S con tres superficies blancas: sensores, PLC y actuadores. Filas de canal de 18 px y tarjetas de variable de 34 px. Las capturas incluyen 24 canales por lado.
- Panel Variables con título claro y resumen de diagnósticos; se evita reservar una lista vacía. Errores, advertencias y avisos siguen apareciendo completos.

Archivos de implementación: `escritorio/ventana.py`, `propiedades.py`, `bloques.py`, `entradas_salidas.py` y ajuste documental en `diagrama.py`. Se conserva la simplificación de menús de `edicion.py` de la primera pasada. Decisión actualizada en P-IMP-70.

Las pruebas visuales de `test_editor_escritorio.py` y `test_editor_cadenas.py` se adaptan a alturas, encabezados y categorías horizontales. S-EDI122 mantiene las comprobaciones de controles contenidos y añade la accesibilidad de las categorías desplazables. S-VIS05 verifica el reparto automático y que se respete el divisor manual. No se modifican núcleo, semántica, formato ni oráculos `test_t*.py`.

Validación final: **534 pruebas correctas, sin fallos ni omisiones**. Evidencia en [pruebas-completas.log](pruebas-completas.log).

## Capturas

Capturadas y revisadas con Qt offscreen y fuentes de Windows. Todos los PNG de ventana principal tienen exactamente el tamaño de su nombre. Los diálogos y el recorte de la paleta se guardan a su tamaño real dentro de cada escenario.

- [accion-evento-1000x600.png](accion-evento-1000x600.png)
- [accion-evento-1366x768.png](accion-evento-1366x768.png)
- [configuracion-1000x600.png](configuracion-1000x600.png)
- [configuracion-1366x768.png](configuracion-1366x768.png)
- [editor-1000x600.png](editor-1000x600.png)
- [editor-1366x768.png](editor-1366x768.png)
- [es-1000x600.png](es-1000x600.png)
- [es-1366x768.png](es-1366x768.png)
- [es-24canales-1000x600.png](es-24canales-1000x600.png)
- [es-24canales-1366x768.png](es-24canales-1366x768.png)
- [paleta-1000x600.png](paleta-1000x600.png)
- [paleta-1366x768.png](paleta-1366x768.png)
- [propiedades-1000x600.png](propiedades-1000x600.png)
- [propiedades-1366x768.png](propiedades-1366x768.png)

## Reproducción

Desde la raíz del repositorio, `python artifacts/rediseno_visual_v2/capturar.py` genera editor, propiedades, paleta, configuración y E/S. Las capturas adicionales de acción por evento se generan a partir del escenario de S-EDI122. Los ajustes y la recuperación usados son temporales; no se conecta con ninguna planta.

Pruebas: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts python -m unittest discover -s tests -t tests`.

Pendiente: validación estética y de uso con ratón físico por el responsable. No se han regenerado informes del proyecto ni construido un ejecutable; tampoco se han hecho commits.
