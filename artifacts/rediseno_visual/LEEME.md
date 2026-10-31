# Revisión del rediseño visual

Cambios Qt: propiedades.py (secciones, catorce fichas e iconos), diagrama.py (controles de vista), ventana.py (barra, estilo y alturas), edicion.py (accesos a operaciones existentes y menús), entradas_salidas.py (densidad y estilo), bloques.py (estilo de categorías). Decisión P-IMP-70 en docs/04.

Pruebas adaptadas: test_editor_escritorio.py y test_editor_cadenas.py (nombres/orden de fichas, encabezados, acceso por clave, desplazamiento y menús); test_dibujo_vista.py (dependencias fuera del zoom). Se conservan las comprobaciones de operaciones, arrastre, deshacer, propiedades, jerarquías y simulación. test_rediseno_visual.py añade cuatro pruebas de los accesos nuevos.

Cambios intencionados de acceso: Añadir acción y Nuevo grafcet parcial aquí se retiran del menú contextual; siguen disponibles por paleta. Apertura/cierre crean la barra Y existente. Las catorce fichas requieren desplazamiento en la lista. A 1000×600 el panel de propiedades abierto deja menos espacio al dibujo; puede plegarse.

Validación: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts python -m unittest discover -s tests -t tests: 533 pruebas, OK. Ver pruebas-completas.log. No se han ejecutado generadores de documentación, creado ejecutable ni realizado commits. Validación con ratón físico pendiente del responsable.

## Capturas finales

Ventana principal y paneles revisados en 1366×768 y 1000×600. E/S incluye capturas de 24 canales por lado, sin conectar con la planta.

- [06-final-configuracion-1000x600.png](06-final-configuracion-1000x600.png)
- [06-final-configuracion-1366x768.png](06-final-configuracion-1366x768.png)
- [06-final-editor-1000x600.png](06-final-editor-1000x600.png)
- [06-final-editor-1366x768.png](06-final-editor-1366x768.png)
- [06-final-es-1000x600.png](06-final-es-1000x600.png)
- [06-final-es-1366x768.png](06-final-es-1366x768.png)
- [06-final-es-24canales-1000x600.png](06-final-es-24canales-1000x600.png)
- [06-final-es-24canales-1366x768.png](06-final-es-24canales-1366x768.png)
- [06-final-jerarquias-1000x600.png](06-final-jerarquias-1000x600.png)
- [06-final-jerarquias-1366x768.png](06-final-jerarquias-1366x768.png)
- [06-final-paleta-1000x600.png](06-final-paleta-1000x600.png)
- [06-final-paleta-1366x768.png](06-final-paleta-1366x768.png)

## Pasos anteriores

Se conservan también las capturas 01-paleta, 02-iconos, 03-dependencias, 04-menus y 05-es.
