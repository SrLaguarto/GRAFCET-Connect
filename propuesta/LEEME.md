# Propuesta de diseño de GRAFCET Connect

Esta carpeta recoge la propuesta de rediseño de la interfaz de escritorio (aspecto, organización y usabilidad). No cambia la semántica, el simulador ni `grafcet/`. Basado en IEC 60848; no se declara conformidad.

## Cómo ver el cambio

```
git diff main..propuesta-diseno
```

## Qué contiene

- `CAMBIOS.md`: lo aplicado en las rondas 1 a 5, con la cifra medida por cada punto.
- `PROPUESTAS_PENDIENTES.md`: lo que no está implementado, con su motivo; al final, los defectos abiertos tras el veredicto (F1 a F11).
- `CRITERIOS.md`: los nueve criterios (C1 a C9) y las restricciones (R1 a R5).
- `VEREDICTO_ARBITRO.md`: el veredicto final del árbitro, con notas por criterio.
- `capturas/antes/`: capturas de `main` en seis tamaños (completa 1920×1080, partida 960×1040, cuarto 960×520, 1366 1366×768, estrecha 640×800, mínima 640×520) y seis escenas (editor, simulación, propiedades, E/S, PLANOS, foco).
- `capturas/despues/`: las mismas escenas en la propuesta, más nombres-edicion y nombres-simulacion (nombres largos de aula).
- `capturas/maquetas/`: cuatro maquetas de propuestas pendientes (P1, P2, P3, P7).
- `herramientas/`: scripts de medición y comprobación. Se ejecutan desde la raíz del repositorio:

| Script | Para qué |
|---|---|
| `medir.py` | Franjas, alturas, letra, anchos, teclado, contraste, zoom, tablas, nombres largos |
| `capturar.py` | Regenera las capturas de `capturas/despues/` |
| `foco.py` | Anillo de foco con teclado y ausencia de anillo con ratón |
| `pulsacion.py` | Entradas mantenidas, Espacio, Ctrl+clic y línea de detalle |
| `nombres_largos.py` | Que los nombres largos se distingan y se lean en cada lista |
| `contrastes.py` | Contraste de los tokens de color |
| `maquetas.py` | Regenera `capturas/maquetas/` |
| `correr_pruebas.py` | Suite por módulos, sin escribir en `tests/` |

Ejemplo: `python propuesta/herramientas/medir.py --tamanos 1366 minima`

## Resumen

**Notas del árbitro por ronda** (media de los nueve criterios, 0 a 10):

| Ronda | Nota |
|---|---|
| 1 | 4,4 |
| 2 | 5,6 |
| 3 | 6,6 |
| 4 | 7,2 |
| Final (ronda 5) | 8,06 |

Veredicto final: **no aprobado**, por poco. No hay defectos bloqueantes. C9 (uso real en clase) queda en 7,5, por debajo del mínimo de 8; la media necesita 8,5.

**Qué cambia y por qué:**

- **Nombres largos.** Los nombres de aula se leen enteros, partidos por los guiones bajos en dos o tres líneas, en Variables, Entradas, «Salidas y variables», «Temporizadores» y las listas de E/S.
- **Estado a la vista.** El estado de la simulación se muestra en chips, franjas y líneas de detalle, sin depender del ratón.
- **Ventana con Propiedades.** Con el panel abierto la ventana baja a media pantalla (683, 640 y 960 px de ancho) y vuelve al tamaño anterior.
- **Zoom.** Con Propiedades abierto, el control de zoom va en la cabecera y deja de tapar el dibujo.
- **Foco de teclado.** Todas las paradas del editor, la simulación y E/S tienen anillo con Tab; un clic no lo deja.
- **Tamaño de la letra.** A partir de 1600×900 la interfaz sube de escala; por debajo se mantiene la escala normal.
- **Entradas.** Clic para pulsar, Ctrl+clic para enclavar y clic derecho para cambiar el tipo. Se retira la pulsación mantenida que abría un menú (D1).
- **Acabado.** Cabeceras enteras, sin cortes con sitio de sobra, y coherencia de colores y tipografía.

**Pruebas (suite por módulos):**

- Rama `propuesta-diseno`: 1079 ejecutadas, 1 fallo (`SEDI266`, que también falla en `main`), 0 errores, 7 omitidas.
- `main`: 1079 ejecutadas, 2 fallos (`SRCT01` por tiempo, `SEDI266`), 1 error (`SPKG`, por el entorno).
- `SPAG18` se cuelga en ambas por falta del paquete `pypdfium2`.

**Pendiente de decisión del responsable:**

- Propuestas que el árbitro recomienda aceptar: P4 (pestañas plegadas de 32 px), P7 («Modo aula» a mano), P8 (verde de «verdadero» en `#18771a`), P11 (tope del 55 % para Propiedades en ventanas bajas), P12 (abreviaturas de «Papel» y «Tipo»), la asignación por clic de P3, y P10 al menos para el panel derecho.
- P9 (borde de la etapa activa en `#157a35`): probar en un proyector real antes de decidir.
- P2 no se acepta tal cual; la parte de «Estado» de P13 se acepta citando P-IMP-30; la parte de «Modo» se resuelve con F1.
- Defectos abiertos por corregir: F1 primero (mostrar «salida continua» o «memorizada» bajo el nombre), después F2 y el resto de la lista de F1 a F11 en `PROPUESTAS_PENDIENTES.md`.
