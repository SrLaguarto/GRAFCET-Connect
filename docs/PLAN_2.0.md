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
   Desde E4, la referencia es `artifacts/v2_e3/imagenes_7400f0c/`: la de E0 más las 8 de `Linea larga`, que E0 no tenía,
   generada desde el commit 7400f0c.
3. **`grafcet/` no se toca.** Si una medida demuestra que el cuello está en el núcleo, el responsable decide
   antes, y solo para rendimiento, sin cambiar la semántica.
4. **`.grafnet` idéntico.** Un archivo guardado con la 2.0 abre en la 1.1.x, y al revés.
5. **`tools/dibujo.js`** sigue dibujando igual que Qt.
6. **Sin dependencias nuevas** de ejecución.
7. **Cada etapa mide** con el banco de E0, antes y después.
8. **Antes de pedir al responsable una autorización técnica**, el coordinador comprueba que es viable (lección del paso 9
   de E3: el cálculo de enlaces por parcial no lo era).

## Decisiones del responsable para E3 (20-nov-2026)

Tras el diseño de E3 (`artifacts/v2_e3/DISENO_E3.md`, fuera del repositorio):

- **Núcleo, solo rendimiento y sin cambiar la semántica** (excepción a la regla 3): calcular la huella una vez por
  cambio, no arrancar una `Session` en la `Vista` de edición, no validar dos veces lo mismo y calcular los enlaces por
  parcial.
- **Pruebas SAD1** (`test_ad118`) que comprueban internos que E3 elimina (caché de rutas, número de dibujos,
  reutilización de textos): se sustituyen por pruebas equivalentes de la escena nueva (excepción a la regla 1).
- **E3 incluye**, además de la escena: validar una vez por cambio, no rehacer la `Vista` en cada fotograma del arrastre,
  un refresco por gesto y la lupa incremental. La simulación sigue con el dibujo completo hasta E4.
- **`Linea larga`** (111 etapas, generada) se añade a `tests/fixtures/referencia/` para la prueba de choque.
- **Desapariciones de la 1.x:** el pintado no es transaccional (vacía la escena y, si falla a mitad, queda a medias);
  se arregla en la 1.x sin cambiar imágenes.
- **Enlaces por parcial (paso 9):** no es posible sin cambiar los recorridos, que dependen del dibujo entero. En su
  lugar se aceleró `routing.enlaces` por dentro, con el mismo resultado.
- **Paso 10** (21-nov): huella sellada al abrir y un refresco por gesto.
- **Resultado de E3** (7400f0c), medianas en GEMMA: añadir una acción 31 ms, deshacer 49, rehacer 44, mover una etapa 93,
  paso de simulación 63 (sin cambios hasta E4).

## Decisiones para E4 (21-nov-2026)

Diseño en `artifacts/v2_e4/DISENO_E4.md` (fuera del repositorio).

- **`grafcet/` no se toca:** el motor cuesta ~1 ms por paso. El tiempo está en rehacer la escena entera, en el modelo
  visual y en las tablas de Variables y Temporizadores.
- **P-IMP-171 se mantiene:** el lienzo sigue con repintado completo.
- **El modelo visual se sigue construyendo entero** en cada cambio. No se reconstruye solo lo que cambia: ganaría poco
  (~2 ms de 9,5 por paso en GEMMA) y obligaría a mantener las dependencias de cada elemento. Solo se replantea si un
  proyecto real se nota lento, midiendo antes en esa máquina.
- **Se adelantan de E6 a E4, tras su paso 1:**
  - `test_ad118` y `SCD51`, que dependen de ficheros que solo hay en la carpeta de la 1.x. `test_ad118` ni siquiera
    llega a ejecutarse en la suite: sus 7 pruebas solo se han pasado a mano.
  - El `KeyError` de `_desde_bloques` (`escritorio/acciones.py`): el editor de bloques avisa a una acción que ya no está en
    el modelo. Sale en cada suite, y el único cierre brusco de E3 ocurrió justo después. También está en la 1.x: queda
    pendiente allí (21-nov), como la ayuda emergente. Se hará después, si la 1.x sigue en uso.

## Decisiones para E7 (21-nov-2026)

El responsable decide hacerla. Va después de E6. El cierre que antes estaba en E6 (documentación de la arquitectura,
ejecutable y medida final) pasa a E8, para que recoja también E7.

- **Objetivo:** que el ciclo con el simulador de planta, por conexión directa o por Modbus, no espere nunca al dibujo, y
  sea regular aunque el equipo esté cargado (el simulador de planta y otros programas abiertos).
- **Reparto:**
  - El motor y la E/S solo los toca el hilo de control.
  - La pantalla lee fotos inmutables del estado y le pasa las órdenes del usuario (entradas, Play, Stop, Reiniciar,
    forzados) por una cola.
- **Misma semántica.** Se mantiene lo decidido sobre el intercambio: orden de lectura y escritura, lotes, cuándo se
  escriben las salidas. Lo que no esté decidido se pregunta. `grafcet/` no se toca salvo que el diseño lo justifique y
  el responsable lo decida.
- **Medida antes y después:**
  - intervalo del ciclo (mediana, P95 y máximo);
  - retraso de entrada a salida;
  - con y sin carga, y por las dos conexiones;
  - incluye la resolución del temporizador de Windows (~15,6 ms).
- **Diseño con esfuerzo Máx.** En Python, los hilos se turnan (GIL). Si un hilo no basta para la regularidad que se
  busca, se valora un proceso aparte, y eso lo decide el responsable.
- Tras E7, el responsable prueba otra vez con E/S reales.

## Metas

Proyecto de referencia, Qt offscreen a 1366 × 768, mediana tras calentamiento.

| Operación | Meta |
| --- | ---: |
| Añadir una acción, mover una etapa, deshacer | < 50 ms |
| Un paso de simulación que cambia la situación | < 20 ms |
| Abrir el proyecto | < 2 s |

«Mover una etapa» se mide por gesto: pulsar, mover y soltar, tres dibujos. Al cerrar la 2.0, el responsable decide si
la meta es por gesto o por fotograma (al cerrar E3, en GEMMA: unos 31 ms por fotograma y 93 por gesto).

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
  (E7)        hilo de control: el motor y la E/S con su propio reloj; publica fotos del estado
              y recibe las órdenes de la pantalla por una cola (el nombre y el sitio, en el diseño)
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
| E5 | Ventana partida: controladores | Implementador y verificador (el responsable lo cambió el 21-nov; antes, Codex) |
| E6 | Limpieza: código muerto (con una herramienta propia que se pueda repetir), una sola de las dos memorias de validación (la de la edición, del paso 7 de E3, y la del núcleo, del paso 9), comprobación opcional y permanente de los documentos sellados y compatibilidad del `.grafnet` entre la 1.x y la 2.0 | Implementador y verificador (antes, Codex y documentador) |
| E7 | Ciclo de E/S independiente: el motor y la E/S en un hilo de control propio, con su reloj; la pantalla dibuja fotos del estado y le pasa las órdenes del usuario | Implementador y verificador |
| E8 | Cierre: segunda pasada de código muerto, documentación de la arquitectura y sus reglas en `CLAUDE.md`, resultados de pruebas y trazabilidad regenerados, ejecutable de prueba, medida final, prueba final del responsable con E/S reales y decisión sobre la meta de «mover una etapa» | Implementador, documentador y verificador |

Después de cada etapa:

1. Suite completa en verde.
2. Banco de imágenes idéntico.
3. Medidas comparadas.
4. Revisión del coordinador y commit en `v2`.
5. El responsable puede probar desde el código.
6. Tras E4, E5, E7 y E8, además, el responsable prueba a mano con E/S reales: una escena larga del simulador de planta
   (muchas cintas, cilindros y etapas temporizadas) y su proyecto, por conexión directa y por Modbus, comparando
   con la 1.1.x. La escena y su proyecto quedan fuera del repositorio.

## Riesgos

- **Detalles finos sin prueba.** Muchos P-IMP corrigen síntomas de dibujo. Se mitiga con el banco de imágenes
  y con la prueba del responsable en cada etapa de dibujo (E1, E3 y E4).
- **Ramas que se separan.** Se mitiga con la 1.x congelada y cada arreglo fusionado en `v2` en el momento.
- **Cierres bruscos de PySide** (un objeto de Qt borrado mientras Python aún lo usa). Hubo uno aislado en una suite de E3
  y no se ha reproducido. E4 mantiene vivos los objetos de la escena entre pasos de simulación, así que la suite completa
  se pasa siempre con `-X faulthandler`.
- **Hilos (E7).** Un dato que tocan a la vez el hilo de control y la pantalla da fallos intermitentes, los más difíciles
  de reproducir. Se mitiga con estas medidas:
  - el motor tiene un solo dueño;
  - la pantalla solo lee fotos inmutables;
  - las órdenes van por una cola;
  - hay pruebas de estrés y de choque con una conexión simulada.
