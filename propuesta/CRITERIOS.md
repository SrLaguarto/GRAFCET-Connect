# Criterios de la propuesta de diseño — GRAFCET Connect

Cada criterio se puntúa de 0 a 10 en **los cuatro tamaños** (pantalla completa 1920×1080, pantalla partida
960×1040, 1/4 de pantalla 960×520 y 1366×768). La nota del criterio es la **peor** de los cuatro tamaños.
Aprobado: ningún criterio por debajo de 8, media ≥ 8,5 y ningún defecto bloqueante abierto.

| # | Criterio | Qué se mira |
|---|---|---|
| C1 | Jerarquía visual | Lo primero que se ve es el dibujo; luego, el estado (edición/simulación, conexión); luego, las herramientas. Un solo acento por zona. |
| C2 | Legibilidad | Texto ≥ 9 pt efectivos, sin recortes («Cent…todo»), sin solapes, sin elipsis en etiquetas clave. Lectura desde el fondo del aula (proyector). |
| C3 | Coherencia | Un sistema de tokens (color, radio, espaciado, tipografía) aplicado igual en editor, simulación, PLANOS y E/S externas. Iconos del mismo trazo. |
| C4 | Accesibilidad | Contraste WCAG AA (4,5:1 texto, 3:1 controles y bordes de foco); foco de teclado visible en todo control; todo se alcanza con teclado; el estado no se comunica solo por color. |
| C5 | Densidad y respuesta al tamaño | A pantalla partida y a 1/4 el dibujo conserva el protagonismo, los paneles se pliegan o compactan sin cortar controles y sin barras de desplazamiento horizontales inútiles. Sin tocar nada al cambiar de tamaño. |
| C6 | Uso táctil | Objetivos ≥ 32 px lógicos (ideal 40), separación ≥ 4 px; nada depende solo de pasar el ratón; dos dedos y pellizco siguen funcionando. |
| C7 | Estado de simulación | Edición frente a simulación inconfundible a 3 m: etapas activas, entradas pulsadas/enclavadas, temporizadores. |
| C8 | Originalidad y acabado | Identidad propia, sin parecerse a un producto concreto; detalle cuidado (alineaciones, ritmo de 4/8 px, estados hover/pulsado/deshabilitado). |
| C9 | Uso real en clase | Profesorado proyectando y alumnado en portátil con el enunciado al lado: tareas típicas (abrir ejemplo, dibujar, Play, pulsar entradas, ver traza, conectar E/S) con menos pasos o igual. |

## Restricciones (incumplir cualquiera = defecto bloqueante)

- R1. Ni la semántica GRAFCET ni el comportamiento del simulador cambian. GRAFCET (IEC 60848) no es SFC.
- R2. Se respetan las decisiones de `docs/04_Decisiones_de_implementacion.md`; lo que se aparte va aparte como propuesta, con su motivo.
- R3. La suite (`python -m unittest discover -s tests -t tests`) da el mismo resultado que en `main`.
- R4. Interfaz en castellano, tono técnico claro, sin nombres de productos de terceros ni declaración de conformidad (como mucho «Basado en IEC 60848»).
- R5. Es una app Qt de escritorio: cada cambio se traduce a widget, fichero y estilo concretos.
