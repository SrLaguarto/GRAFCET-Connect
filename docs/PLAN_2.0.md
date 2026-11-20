# GRAFCET Connect 2.0: reorganización interna

## Objetivo

Mismo funcionamiento que la 1.1.x, con el código de `escritorio/` ordenado por responsabilidades y el dibujo
incremental. **Sin funciones nuevas ni cambios visibles.** Solo cambia lo de detrás.

## Decisiones del responsable (20-nov-2026)

- **Por etapas.** Cada etapa deja el programa funcionando y la suite completa en verde. No se reescribe desde cero.
- **La 1.x** (rama `propuesta-diseno`) solo recibe fallos graves. Cada arreglo se fusiona después en `v2`.
- **Reparto mixto.**
  - Codex: etapas grandes y mecánicas.
  - Implementador y verificador del proyecto: etapas delicadas (dibujo y simulación).
  - Coordinador: planifica, revisa, valida y hace los commits.
- **Tamaño.** El mayor proyecto real ronda las 50 etapas, con varios GRAFCET parciales, forzados y muchas acciones.
  La referencia principal es ese proyecto real (guía GEMMA, `tests/fixtures/referencia/guia_gemma.grafnet`), y
  como margen se mide también uno generado del doble: 100 etapas con esa riqueza.
- **Sin ejecutable** durante los exámenes. La 2.0 se publica al terminar todas las etapas.

## Reglas

1. **La suite actual es el contrato.**
   - Las pruebas de comportamiento no cambian.
   - Una prueba que llame a un interno renombrado se adapta solo al nombre nuevo, y el informe lo justifica.
2. **Imagen idéntica.** En cada etapa, el banco de imágenes de E0 debe dar las mismas imágenes antes y después:
   ejemplos, fixtures y proyecto de referencia, en edición y en simulación. Toda diferencia se explica o se corrige.
3. **`grafcet/` no se toca.** Si una medida demuestra que el cuello está en el núcleo, el responsable decide
   antes, y solo para rendimiento, sin cambiar la semántica.
4. **`.grafnet` idéntico.** Un archivo guardado con la 2.0 abre en la 1.1.x, y al revés.
5. **`tools/dibujo.js`** sigue dibujando igual que Qt.
6. **Sin dependencias nuevas** de ejecución.
7. **Cada etapa mide** con el banco de E0, antes y después.

## Metas

Proyecto de referencia, Qt offscreen a 1366 × 768, mediana tras calentamiento.

| Operación | Meta |
| --- | ---: |
| Añadir una acción, mover una etapa, deshacer | < 50 ms |
| Un paso de simulación que cambia la situación | < 20 ms |
| Abrir el proyecto | < 2 s |

## Arquitectura de llegada

```
escritorio/
  geometria/  sin Qt: posiciones, cajas de acciones y comentarios, choques, huecos, equidistancia
              y ajuste de los enlaces (alrededor de grafcet.routing)
  escena/     un objeto gráfico por elemento; aplica solo lo que cambia del modelo visual;
              el pintado de la simulación cambia colores y marcas, sin rehacer la escena
  edicion/    Edicion se queda como fachada; detrás: selección, arrastre, portapapeles,
              acciones y grupos, diagnósticos y órdenes de deshacer
  ventana/    Ventana se queda como fachada; detrás: archivos, simulación, E/S (Modbus y
              directa), vista y modos, menús
```

Paneles, Propiedades, Planos y el resto se quedan donde están. Solo se agrupan si sale de forma natural.

Las fachadas mantienen la interfaz que usan las pruebas y el resto del programa (`prensar`, `soltar`, `cambia`…).
La caché de rutas y la reutilización de textos de AD desaparecen cuando la escena es incremental.

## Etapas

| Etapa | Contenido | Quién |
| --- | --- | --- |
| E0 | Banco de medida, banco de imágenes y proyecto de referencia; medidas de partida | Codex |
| E1 | Geometría pura: sacar de `edicion.py` y `diagrama.py` el cálculo de posiciones, cajas, choques, huecos y equidistancia, con pruebas rápidas sin Qt | Codex; verificador |
| E2 | Edición partida: `Edicion` como fachada con sus piezas | Codex |
| E3 | Escena incremental en edición | Implementador y verificador |
| E4 | Simulación incremental | Implementador y verificador |
| E5 | Ventana partida: controladores | Codex |
| E6 | Limpieza: código muerto, pruebas rápidas, documentación de la arquitectura, medida final | Codex y documentador |

Después de cada etapa:

1. Suite completa en verde.
2. Banco de imágenes idéntico.
3. Medidas comparadas.
4. Revisión del coordinador y commit en `v2`.
5. El responsable puede probar desde el código.

## Riesgos

- **Detalles finos sin prueba.** Muchos P-IMP corrigen síntomas de dibujo. Se mitiga con el banco de imágenes
  y con la prueba del responsable en cada etapa de dibujo (E1, E3 y E4).
- **Ramas que se separan.** Se mitiga con la 1.x congelada y cada arreglo fusionado en `v2` en el momento.
