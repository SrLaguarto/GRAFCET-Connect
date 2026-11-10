# Veredicto final del árbitro: propuesta de diseño de GRAFCET Connect

- **Fecha:** 9 de noviembre de 2026.
- **Commit evaluado:** `3980534` de la rama `propuesta-diseno` (ronda 5). Lo comparo con `main` (`9a812b6`) y con la ronda 4 (`6690b5c`).
- **Veredicto: NO APROBADO.** No hay ningún defecto bloqueante. Falla porque C9 se queda en 7,5 (el mínimo es 8) y la media es 8,1 (hace falta 8,5).

## Cómo he evaluado

- **Pruebas.** Todas son mías y corren con Qt `offscreen` y las fuentes de Windows. Cuando hacía falta comparar, las he corrido también contra `main` y contra la ronda 4, que saqué con `git archive` sin tocar el repositorio.
- **Nombres de aula reales.** Al ejemplo «temporizada» le añado 15 entradas y 9 salidas, 29 variables en total:
  - entradas: `pulsador_marcha`, `pulsador_paro`, `seta_emergencia`, `selector_manual`, `selector_automatico`, `sensor_pieza_cinta`, `detector_inductivo_metal`, `detector_capacitivo_plastico`, `final_carrera_cilindro_A/B/C_avance/retroceso` y `presostato_linea_aire`;
  - salidas: `motor_cinta_transportadora`, `piloto_marcha`, `piloto_averia` y `electrovalvula_cilindro_A/B/C_avance/retroceso`.
- **Capturas.** He regenerado sobre HEAD las 36 capturas de `propuesta/capturas/despues/` y coinciden píxel a píxel con las del repositorio (0 píxeles distintos). Por tanto, las capturas del repositorio son las del código evaluado. Para los casos dudosos he hecho capturas propias.
- **Lo que no he comprobado.** No he pasado la suite (R3): la comprueba el verificador.
- **Tiempos.** El verificador corría a la vez que yo medía, así que los tiempos absolutos salen inflados. Los comparo siempre con la ronda 4 medida en las mismas condiciones.

## Notas (0–10; la nota del criterio es la peor de los cuatro tamaños obligatorios)

| # | Completa 1920×1080 | Partida 960×1040 | Cuarto 960×520 | 1366×768 | Estrecha / mínima (anotación) | **Final** | Justificación |
|---|---|---|---|---|---|---|---|
| C1 Jerarquía | 8,5 | 8,5 | 8,5 | 8,5 | 7,5 / 7 | **8,5** | El dibujo manda y el estado se ve: chip, franja y Stop en verde. Con Propiedades abierto y una transición elegida, el zoom va en la cabecera a todos los tamaños: con palabras a 1440 y a 1920 (dibujo de 524 px a 1920), solo con iconos a 1366 y menos. Ya no flota sobre el dibujo. Con 640 px de ancho el título se queda en «S…» (anotación). |
| C2 Legibilidad | 9 | 8 | 8 | 8,5 | 7,5 / 7,5 | **8** | Los nombres de aula se leen enteros y distintos en Variables, Entradas y las tablas de estado: se parten por «_» en 2 o 3 líneas y no queda ninguna «…». La letra nunca baja de 12 px. Quedan dos cosas en la vista de E/S. Las etiquetas de los canales miden 71 px en partida y 65 px en cuarto, y se cortan a media palabra («…lsador_paro», «…automati…», «sensor_pie…»), aunque son distintas entre sí. Y el combo de plantillas de PLANOS sale como «A4 vertica…eterminada» en cuarto (F5). |
| C3 Coherencia | 9 | 8,5 | 8,5 | 9 | 8,5 / 8,5 | **8,5** | Los tokens y los títulos con cuadrado son los mismos en todas las vistas. Ya se ve el hueco entre el cuadrado y el texto en «□ Sensores». Las abreviaturas siguen un mismo patrón («Entr.», «Bool.», «cont.», «Contrib.»). La vista de E/S recorta de otra manera, con «…» y el final, pero está justificado por las filas de 16 px. |
| C4 Accesibilidad | 8 | 8 | 8 | 8 | 8 / 8 | **8** | Con Tab, el anillo cambia los píxeles en todas las paradas: 18 en edición a 1366 y a 1920 (14 en cuarto), 16 en simulación y 7 en E/S. Un clic no deja anillo. Las entradas enclavadas llevan candado y las pulsadas, punto lleno. En PLANOS, en cambio, «+ Añadir hoja», el lienzo de la hoja y sus áreas de desplazamiento reciben el foco sin que se vea (igual en `main` y en la ronda 4: F3). El verde 1,92:1 está documentado (P8 y P9). |
| C5 Densidad y tamaño | 8,5 | 8,5 | 8 | 8,5 | 8 / 7,5 | **8** | N2 está resuelto. Redimensionar en caliente da lo mismo que arrancar a ese tamaño, y no hay barras inútiles. En cuarto, Variables lleva dos barras verticales anidadas (la de la tabla y la del panel). En `main`, en cambio, los botones tapaban la tabla. Cruzar 1600×900 cuesta un 25–35 % más que en la ronda 4 en las mismas condiciones (F7). Desde 1920×1080, pedir menos de 769 px de ancho exige dos peticiones (F6, anotación). |
| C6 Panel táctil | 8 | 8 | 8 | 8 | 8 / 8 | **8** | Ningún control visible mide menos de 32 px, salvo las pestañas plegadas (P4). Entre entradas quedan 4 px. El menú contextual se abre igual que en `main`. Al pasar el puntero, el nombre entero sale en la línea de detalle. Con el panel derecho desplazado, el chevron de plegar (32×32) queda encima de la primera entrada visible, y un clic ahí pliega el panel (en `main`, igual con 24×24: F4). |
| C7 Estado de simulación | 8,5 | 8 | 8 | 8 | 8 / 7,5 | **8** | El estado se ve bien: etapas en verde, «= 1» con punto o candado, y en los temporizadores el «contando» sigue a la vista, bajo el nombre y con su color. Las salidas tienen dos problemas. Por debajo de 1680 px de ancho, «Modo» desaparece sin dejar rastro (F1). Y con prácticas de 10 entradas o más, «Salidas y variables» queda bajo el pliegue (F2). El proyector de 1366 sigue en la escala normal (P7, documentado). |
| C8 Originalidad y acabado | 8 | 8 | 8 | 8 | 7,5 / 7,5 | **8** | La identidad es propia: franja-enlace, cuadrado de etapa y Bahnschrift en los títulos. N5–N7 están resueltos. Quedan detalles: el chevron encima de las entradas (F4) y nombres en 3 líneas a 1920, donde la columna mide 97 px por llevar las cuatro columnas (a 1366 caben en 2). «Contribuyen» sale en 3 líneas («a.E1.» / «motor.» / «0») cuando el panel lleva barra. El título queda en «Secuen…» a 683 con Propiedades (F9). |
| C9 Uso real en clase | 8,5 | 8 | 7,5 | 8 | 7,5 / 7 | **7,5** | Mejora mucho, por cuatro cosas: el alumnado lee y distingue sus entradas y salidas, ve el valor sin barra horizontal, la ventana con Propiedades cabe en media pantalla de 1366 y la fórmula mide 223 px. Pero ha desaparecido algo que `main` enseñaba: si una salida es continua o memorizada (F1). Se puede resolver sin tocar ninguna restricción. En cuarto se suma lo propio del tamaño: Propiedades deja 91 px de dibujo (documentado, P1/P11), las etiquetas de E/S se cortan y hay que desplazar el panel para ver las salidas. |

**Media:** (8,5 + 8 + 8,5 + 8 + 8 + 8 + 8 + 8 + 7,5) / 9 = 8,06 ≈ **8,1**.

**Veredicto: NO APROBADO.** C9 está por debajo de 8 y la media no llega a 8,5. No queda ningún bloqueante abierto.

## Restricciones

| R | Resultado | Evidencia propia |
|---|---|---|
| R1 Semántica y simulador | **Cumple** | `git diff main -- grafcet tools tests conexion docs` sale vacío. Lo que sigue lo he comprobado a 1366×768 y a 960×1040, en una entrada de una línea («marcha») y en otra de dos («final_carrera_cilindro_A_avance»): <ul><li>Mantener pulsado 1,5 s da 1 y `down` en todas las muestras, sin ningún menú, y vuelve a 0 al soltar.</li><li>Espacio tras el clic da 1 y luego 0.</li><li>Ctrl+clic enclava, y soltar Ctrl lo libera.</li><li>El menú contextual tiene las mismas cuatro opciones que en `main`.</li><li>Si «marcha» está mantenida al pasar de 1920 a 1366, sigue a 1.</li></ul> |
| R2 Decisiones | **Cumple, con observaciones** | No encuentro ningún apartamiento sin documentar. <ul><li>P-IMP-126: la pestaña 2 está oculta; la luz tiene la ayuda «Abrir E/S externas», el nombre accesible «E/S externas: desconectada» y la mano; con E/S a la vista pasa a `abierta` (fondo blanco, borde oscuro de 2 px y negrita) y vuelve al salir.</li><li>P-IMP-128: el panel inferior está oculto al arrancar y «Fijar» se puede marcar y sale sin marcar; la lógica de `_tras_gesto` no cambia.</li><li>P-IMP-75: los paneles conservan su ancho al pulsar Play (218 → 218 y 300 → 300).</li></ul>Observaciones, no bloqueantes: (a) P13 cambia la tabla «Temporizadores» de P-IMP-30 («dónde, estado, lleva, preset») y debería citarla. (b) Los paneles de 264 px a 1600 y de 300 px a 1920 se apartan de P-IMP-42 («los anchos salen de la paleta: 188–216»). Están descritos en P7 y P10 con su motivo, pero sin nombrar P-IMP-42. |
| R3 Suite | No la he pasado | La comprueba el verificador. `tests/` no cambia. |
| R4 Castellano y terceros | **Cumple** | Revisé las 3301 líneas añadidas en `escritorio/`. Ningún nombre de producto de terceros ni ninguna declaración de conformidad. Todos los textos nuevos están en castellano. En la barra de estado sigue «Basado en IEC 60848». |
| R5 Qt concreto | **Cumple, con una salvedad** | He reproducido por muestreo las cifras de `CAMBIOS.md` (§2 ter): anchos de ventana, «Fórmula», zoom, columnas, mínimos y líneas, y coinciden todas. La salvedad: `CAMBIOS.md` (N1 b) y P13 dicen que el texto de «Modo» oculto «sigue en la ayuda de la celda». No es así. La ayuda emergente de la fila dice solo el nombre («motor»), y la celda de «Modo», oculta, no se puede señalar. Solo queda en la línea de detalle. |

## Lo que se aprueba sin reservas

1. **Nombres largos.** Es el cambio de más peso de la ronda.
   - Variables, Entradas, «Salidas y variables» y «Temporizadores» enseñan el nombre **entero**, partido por los «_» en 2 o 3 líneas, y la fila crece lo que haga falta.
   - Con los nombres de aula salen 29/29, 17/17 y 12/12 textos distintos, ninguno con «…», a los seis tamaños.
   - Las listas y los canales de E/S salen distintos a todos los tamaños.
   - Antes, en `main`: Variables mostraba seis veces «final_carrera_cili…» a 1366, las entradas se cortaban («final_carrera_cilindro_A_avar») y el valor de las salidas quedaba fuera de la vista.
2. **Media pantalla con Propiedades abierto.** Partiendo de 1366×768, la ventana baja exactamente al ancho pedido: 683×768, 640×800, 640×520 y 960×1040. Al cerrar Propiedades y pedir el mismo tamaño, también. De vuelta, recupera 1366. El mínimo con Propiedades es de 554–606 px.
3. **Campo «Fórmula».** Mide 223 px a 683 y 180 px a 640. «Receptividad correcta.» baja a su propia línea, entera; a 1366 y 1920 va al lado, como antes.
4. **Zoom con Propiedades.** Con una transición elegida va en la cabecera a 1920, 1440, 1366, partida, cuarto y 640. Con una etapa elegida (panel bajo) vuelve a flotar a 1440 y a 1920, como fija `SAUC41`.
5. **Ayuda del ejemplo.** Ya no se corta a media frase: «más ▾» la despliega entera y «menos ▴» la recoge. Donde no cabe, sale el botón «Ayuda ▾». Se maneja con teclado (Espacio) y tiene anillo.
6. **Acabado.**
   - La línea de detalle ya no acaba en « · ».
   - El cuadrado de los títulos de E/S está separado del texto.
   - «Contribuyen» sale entero a 1920.
   - El subtítulo de 1366 con Propiedades cabe en dos líneas.
   - La cabecera «Variable» no se corta.
   - El estado del temporizador va bajo el nombre, con su color.
7. **Teclado.** Hay anillo en todas las paradas del editor, la simulación y E/S, y el clic con el ratón no lo deja.
8. **Tamaños y letra.** Redimensionar en caliente da lo mismo que arrancar a ese tamaño (1920→1366, 1366→1920, 1366→1700 y 1920→960). Ningún control mide menos de 32 px, salvo las pestañas plegadas (P4), y ninguna letra baja de 12 px.
9. **Las decisiones intactas:** P-IMP-75, P-IMP-126 y P-IMP-128.

## Seguimiento de los defectos de la ronda 4

| # r4 | Defecto | Estado | Evidencia propia |
|---|---|---|---|
| N1 | Nombres largos reales repetidos («…_carrer…_avance», «…_…e») | **Resuelto** | Comprobado a los seis tamaños: <ul><li>Variables, 29/29 nombres distintos y sin «…». Ejemplos: «final_carrera_» / «cilindro_A_avance» y «electrovalvula_» / «cilindro_» / «A_retroceso». La columna mide 136 px a 1920, 109 a 1366, 960×1040 y 640×800, y 97 en cuarto y mínima.</li><li>Entradas, 17/17, en dos líneas como máximo.</li><li>«Salidas y variables», 12/12: «piloto_marcha» y «piloto_averia», enteros.</li><li>E/S: listas y canales distintos.</li></ul>Ahora bien, el arreglo esconde «Modo» (F1). |
| N2 | La ventana con Propiedades no bajaba de 848 | **Resuelto** | Las cifras del punto 2 de la lista anterior. Queda un caso límite: desde 1920×1080, con la letra grande, una sola petición se queda en 777 (F6). |
| N3 | «Fórmula» de 97/54 px | **Resuelto** | 223/180 px. El estado va en su línea, entero. |
| N4 | Zoom flotando con Propiedades a 1440 y 1920 | **Resuelto** | En la cabecera y con sus palabras: 453 px a 1920 y 439 px a 1440. |
| N5 | Cuadrado pegado en los títulos de E/S | **Resuelto** | «□ Sensores 2», con hueco, a 1366. |
| N6 | « · » al final de la línea de detalle | **Resuelto** | «luz · salida continua · OFF». |
| N7 | Recortes con sitio de sobra | **Resuelto** | «Contribuyen» va entero a 1920, el subtítulo en dos líneas, la ayuda con «más ▾» y la cabecera «Variable», entera. |
| N8 | Documentar la abreviatura de Papel y Tipo | **Resuelto** | Está en P12, con su motivo. |
| N9 | Mínima: título «S…» y 91 px de dibujo con Propiedades | **Sin cambios** (anotación) | 348×91 a 640×520. Lo recogen P1 y P11. |

## Defectos abiertos, por prioridad

No queda ningún bloqueante.

### Medios

**F1. «Modo» desaparece de «Salidas y variables» sin dejar rastro** (C9 y C7; partida, cuarto, 1366, y también 1440, 1536 y 1600).

- **Dónde:** `ventana.py`, `_planes_vars`. Por debajo de unos 250 px útiles, el plan elegido pone `{1: 0}` y la columna se oculta.
- **Evidencia.** La columna «Modo» falta a 1366, 960×1040, 960×520, 1440×900, 1536×864 y 1600×900. Se ve, abreviada («cont.»), a 1680×1050, y entera a 1920. La ayuda emergente de la fila dice solo el nombre. «salida continua» o «memorizada» solo aparece en la línea de detalle al pasar el puntero o elegir la fila. `main` enseñaba la columna «Modo» en las mismas tablas.
- **Por qué importa:** que una salida siga a ON con su etapa desactivada solo se entiende si se sabe que es memorizada. Es justo la duda que el profesorado resuelve señalando la tabla en el proyector.
- **Se puede resolver sin tocar restricciones:**
  - El mecanismo ya existe: «Temporizadores» enseña su «Estado» bajo el nombre (`DelegadoNombres(..., secundaria=1)`). Lo mismo en `t_vars` dejaría «salida continua» o «memorizada» bajo cada nombre. Es la alternativa que la propia P13 apunta.
  - Además, hay que corregir la frase de `CAMBIOS.md` y de P13 sobre «la ayuda de la celda».
- **Ganancia estimada:** C9 +0,5 (7,5 → 8). C7 deja de rozar el 7,5.

**F2. Con prácticas grandes, «Salidas y variables» queda bajo el pliegue** (C7 y C5; 1366 sobre todo).

- **Por qué pasa:** las entradas de nombre largo ocupan dos líneas (55 px de alto; 61 a 1920).
- **Evidencia.** Filas de «Salidas y variables» que se ven sin desplazar el panel, de 9 en total:

  | Tamaño | 6 entradas | 10 entradas | 14 entradas | 17 entradas |
  |---|---|---|---|---|
  | 1920×1080 | 9 | 7 | 3 | 0 |
  | 1366×768 | 4 | 0 | 0 | 0 |
  | 960×1040 | 9 | 5 | 0 | 0 |

  `main` enseña 2 filas a 1366 (y 5 a 1920), pero **sin** la columna «Valor», que queda fuera de la vista con barra horizontal. Así que no se pierde acceso al valor, pero el panel tampoco aprovecha el sitio.
- **Por qué importa:** las salidas son lo que se mira al pulsar las entradas.
- **Mejora posible:** que la caja «Entradas» se pueda plegar desde su título, o reservar a «Salidas y variables» un alto mínimo a la vista.
- **Ganancia estimada:** C7 +0,5 a 1366.

### Menores

- **F3. Foco invisible en PLANOS** (C4). Con Tab, «+ Añadir hoja», el lienzo de la hoja (`VistaLamina`) y sus áreas de desplazamiento reciben el foco sin ningún cambio visible. Pasa igual en `main` y en la ronda 4. Las demás paradas de PLANOS sí tienen anillo (28 paradas con una hoja abierta).
- **F4. El chevron de plegar el panel derecho queda encima de la primera entrada visible al desplazar el panel** (C6, C8). A 1366, con el panel desplazado 60 px, el chevron se solapa 20×30 px con «detector_capacitivo_plastico = 0». Un clic en el solape pliega el panel y no pulsa la entrada. Ya pasaba en `main`, con un botón de 24×24.
- **F5. Etiquetas de los canales de E/S cortadas en partida y cuarto** (C2). Miden 71 y 65 px y salen «…lsador_paro», «…automati…», «sensor_pie…», mientras el marco del PLC deja mucho sitio vacío entre «Entrada n» y «Salida n». Son distintas entre sí, y `main` era peor: seis veces «final_carre…».
- **F6. Desde 1920×1080, la ventana no baja de 769 px en una sola petición** (C5, anotación). Pedir 683 o 640 se queda en 769 px (777 con Propiedades) y la segunda petición ya llega. En `main` nunca baja de 752.
- **F7. Cruzar el umbral de 1600×900 es algo más lento** (C5). En las mismas condiciones de carga, la ronda 4 tarda 215–350 ms por cruce y la ronda 5, 270–490 ms. Un arrastre de 1366 a 1700 en 42 pasos pasa de 1,5 a 2,0 s en total (peor paso: de 277–304 a 368–390 ms).
- **F8. Título recortado en ventanas estrechas** (anotación): «Secuen…» a 683 con Propiedades y «S…» a 640 (N9).
- **F9. Líneas de más** (C8):
  - A 1920 los nombres de «Salidas y variables» van en 3 líneas, con 97 px, porque se reparten las cuatro columnas; a 1366 caben en 2.
  - «Contribuyen» sale en 3 líneas cuando el panel lleva barra.
- **F10. Barras anidadas en cuarto** (C5, C6). Variables lleva la barra de la tabla y la del panel, una al lado de la otra.
- **F11. Documentación** (R2 y R5): las citas que faltan en P13 (P-IMP-30) y en P7/P10 (P-IMP-42), y la frase inexacta de F1.

**Qué haría falta para aprobar.** F1 y F2 son los que más suben (C9 a 8 y C7 a 8,5). Con F1–F5 la media rondaría 8,4. Para llegar a 8,5 haría falta además alguna propuesta que depende del responsable, en particular P7 (escala grande en el proyector de 1366) o P10 (panel derecho más ancho a 1366, que también devolvería «Modo»).

## Valoración de las propuestas pendientes

P5 y P6 no figuran en `PROPUESTAS_PENDIENTES.md`.

| Propuesta | ¿Se sostiene el motivo? | Recomendación |
|---|---|---|
| **D1** (descartada: mantener pulsado abre el menú) | **Sí.** Rompe P-IMP-75 y la tarea central: mantener «marcha» mientras corre un temporizador de 3 s. Con el panel táctil, el toque con dos dedos ya es el clic derecho; he comprobado que el menú se abre. | Mantenerla descartada. |
| **P1** (paleta de operadores en una fila por debajo de 560 px de alto) | **Sí.** P-IMP-93 fija unos 334 px, y lo comprueban las pruebas. | Preferir P11, que es más sencilla y no cambia la paleta. Dejar P1 como alternativa. |
| **P2** (entradas en una banda bajo el dibujo en pantalla partida) | **Sí.** Lo impiden los paneles laterales fijos (P-IMP-42, 44, 47 y 78). Pero la propuesta se queda corta en el coste: la maqueta solo tiene 2 entradas, y con 15–17 de aula la banda necesitaría varias filas y le quitaría al dibujo mucho más de 50 px. | No aceptarla tal cual. |
| **P3** (modo «cómodo» de E/S con filas de 28 px y asignación por clic) | **Sí.** P-IMP-63 y `SESP14`. | Aceptar la **asignación por clic**: es una ganancia clara con el panel táctil y no cambia la disposición. Las filas de 28 px, solo como opción que elige el usuario: Qt no da una señal fiable de «puntero de baja precisión». |
| **P4** (pestañas plegadas de 32 px) | **Sí.** `SPAN02` y `SPAN04` fijan 26 px. | Aceptar. Es una constante y unas pruebas, y es el único control de menos de 32 px que queda. |
| **P7** («Modo aula»: escala grande elegida a mano) | **Sí.** Añade un ajuste y una entrada de menú, que recorren las pruebas. Los proyectores de 1366×768 y 1280×720 no llegan al umbral automático. | **Aceptar.** Es lo que más ayuda a C2, C7 y C9 en el aula real. |
| **P8** (texto de «verdadero» en `#18771a`, 5,69:1) | **Sí.** `SUIV02` exige `true_text == active`. Además, el propio texto de P-IMP-77 pide «el texto de lo verdadero en un verde más oscuro con contraste suficiente», así que P8 devuelve la implementación a lo decidido. | **Aceptar.** El responsable decide el cambio de `SUIV02` y de `tools/dibujo.css`. |
| **P9** (borde de la etapa activa en `#157a35`) | **Sí.** P-IMP-77 fija el lima `#40d641`. | Aceptable, pero cambia la identidad de «activo» que decidió el responsable. Conviene probarla en un proyector real antes de decidir. |
| **P10** (paneles de unos 270 px a 1366 y menos) | **Sí.** `SPAL05` y `SPAL06` fijan 218 px. Además, por P-IMP-42 y P-IMP-75 el panel derecho conserva el ancho de la edición. | Recomendable al menos para el panel derecho: devolvería «Modo», «Papel» y «Tipo» enteros y las cuatro columnas a 1366, a cambio de unos 52 px de dibujo. Hay que revisar P-IMP-42. Mientras tanto, F1 se arregla sin ella. |
| **P11** (tope del 55 % para Propiedades en ventanas bajas) | **Sí.** P-IMP-93 y `SEDI122`. | **Aceptar.** Es sencilla y sube el dibujo de 91 px a algo útil en cuarto y en mínima. |
| **P12** (Papel y Tipo abreviados en el panel de 218 px; aplicada) | **Sí.** Con 96 px para el nombre, las palabras enteras no caben. `main` tampoco las mostraba enteras («Entr…», «Boole…»). | **Aceptar.** |
| **P13** («Modo» y «Estado» ceden su columna; aplicada) | **En parte.** Lo de «Estado» bajo el nombre, sí: la información sigue a la vista. Lo de esconder «Modo», no: había una alternativa sin tocar restricciones, y la propia P13 la cita. Además, la frase «su texto va en la ayuda de la celda» es inexacta. | Aceptar la parte de «Estado», citando P-IMP-30. **No aceptar** que «Modo» se esconda: hay que enseñarlo bajo el nombre (F1). |

## Anexo: evidencias

Los scripts y salidas del árbitro quedaron en la carpeta de trabajo local de la auditoría y no forman parte de esta entrega; se citan para trazabilidad.

- **Base común:** `base_f.py`, el preámbulo. Con `RAIZ_ARBITRO=<main_ref | r4_ref>` corre sobre `main` o sobre la ronda 4. `r4_ref\` es el volcado de `6690b5c` hecho con `git archive`.
- **Nombres de aula** (lo que pinta cada delegado, «…», distintos, alturas, columnas ocultas, E/S y canales): `nombres_f.py`. Salidas en `nl_1366.txt`, `nl_rama.txt` (seis tamaños), `nl_main.txt` y `nl_main2.txt`.
- **Estado de las salidas:** `estado_f.py` (qué electroválvula está a ON) y `densidad_f.py` (filas de salidas a la vista según el número de entradas).
- **Ventana con Propiedades:** `ancho_f.py` (N2, N3 y N4 a 1366, 1920, 1440, 960, 683 y 640). Salida en `ancho_rama.txt`.
- **P-IMP-75:** `pulsar_f.py` (mantener 1,5 s, Espacio, Ctrl+clic, línea de detalle) y `pulsar2_f.py` (menú contextual y salto de las entradas). `salto_f.py`: con el reloj en marcha, las entradas no saltan.
- **P-IMP-126/128, objetivos y letra:** `pimp_f.py`. Salida en `pimp_rama.txt`.
- **Foco:** `foco_f.py` (anillo con Tab en edición y simulación, y «más ▾» con Espacio). Las comprobaciones de E/S y PLANOS se hicieron con scripts en línea; están en el registro de la sesión.
- **Cambios de tamaño:** `cambio_f.py` (redimensionar en caliente frente a arrancar a ese tamaño) y `umbral_f.py` (cruce del umbral, rama frente a la ronda 4).
- **Chevron sobre las entradas:** `chevron_f.py` (rama y `main`).
- **Capturas:**
  - `cap_head\`: las 36 escenas regeneradas sobre HEAD. `cmp_capt.py` muestra que coinciden con las del repositorio.
  - `capt_rama\` y `capt_main\`: capturas propias (`nl_*`, `estado_*`, `props_*`, `ayuda_abierta_*`, `enclavada_pulsada_1366.png`, `chevron_*`).
  - Recortes `z_*.png`: Variables a 1366 y en cuarto, rama frente a `main`; el chevron sobre las entradas; la franja; los títulos de E/S; E/S en partida.
- **Utilidades:** `pimp.py` (consulta de filas P-IMP) y `recorte.py`.
