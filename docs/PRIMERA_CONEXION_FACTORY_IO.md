# Primera conexión: sigue estos pasos con tus capturas

No necesitas crear un GRAFCET para esta prueba: hay uno preparado.
Esta guía se refiere al último estado de tus capturas; si cambias la configuración
de Factory I/O, copia los nuevos valores en GrafConnect.

## 1. Abre el programa y el proyecto preparados

1. Cierra la versión anterior de GrafConnect. Abre **dist/GRAFCET/GRAFCET.exe**
   desde la carpeta `implementacion` de este proyecto.
2. Pulsa la pestaña **E/S externas** y el botón **Abrir prueba guiada**, arriba a
   la derecha. Si no aparece ese botón, estás usando la versión anterior.
3. El título debe indicar «Prueba Factory I O - pulsador y cinta». Este proyecto
   ya tiene etapa inicial, variables y acción. También está disponible en
   `prueba_factoryio_digital/manifest.json`, junto al ejecutable, por si quieres
   abrirlo con **Archivo → Abrir modelo…**.
4. En **E/S externas**, las tres casillas «Usar» deben estar marcadas
   y deben aparecer tres tarjetas. Si no sucede, no continúes: anótalo abajo.

## 2. Comprueba estos valores, sin cambiar tu escena

En Factory I/O, tus capturas muestran **Modbus TCP/IP Server** y este mapa:

| Elemento de la escena | Terminal de Factory I/O | Variable de GrafConnect | Área en GrafConnect | Dirección |
|---|---|---|---|---|
| Pulsador marcha | Input 0 | PM | Inputs (entradas digitales 0/1) | 0 |
| Sensor emisor | Input 1 | PP | Inputs (entradas digitales 0/1) | 1 |
| Cinta entrada | Coil 0 | Q | Coils (señales digitales 0/1) | 0 |

**Q debe tener dirección 0, no 2.** Las entradas y las salidas tienen numeraciones
independientes. Coil 1 corresponde a «Cinta acumulación» y no participa en esta prueba.
PP es aquí el sensor emisor; no significa parada ni detiene la cinta.

En GrafConnect comprueba los campos situados encima de la tabla:

| Campo | Valor de tu última captura |
|---|---|
| IP (Host) | **192.168.1.133** |
| Puerto | **502** |
| Esclavo ID | **1** |
| Periodo | Déjalo en **50 ms** |
| Espera | Déjalo en **500 ms** |

Una captura anterior muestra 127.0.0.1. Usa la dirección que esté mostrando
**ahora** Factory I/O en CONFIGURACIÓN y en el centro del DRIVER. El proyecto
preparado tiene 192.168.1.133, según tus últimas dos capturas.

Las tres señales son digitales: formato **BOOL (apagado/encendido)** y escala **1**.
La escala **100** que se ve en Factory I/O sirve para las señales numéricas y no
debes copiarla en estas tres señales digitales. No cambies los demás ajustes de
Factory I/O para esta primera prueba.

## 3. Comprueba la conexión, todavía sin mover la cinta

1. En Factory I/O deja activo el driver **Modbus TCP/IP Server**. En tu captura
   aparece un indicador verde y la opción «PARAR»: no pulses PARAR para esta prueba.
   Ese indicador por sí solo no demuestra que GrafConnect esté conectado.
2. En GrafConnect pulsa **Aplicar mapa** y después **Probar conexión**.
3. Arriba del panel debe aparecer **«Conexión probada; no se han escrito actuadores»**.
   Si aparece otra cosa, copia el mensaje exacto abajo y detente en este punto.
4. Pulsa **Conectar**. Debe aparecer **«Conectado · actuadores a cero · pulse Ejecutar»**.
   Conectar y Probar conexión son dos operaciones distintas: Probar termina su
   comprobación y cierra la conexión; Conectar la mantiene abierta.

## 4. Prueba solo el pulsador y la cinta de entrada

1. En Factory I/O vuelve desde DRIVER a la escena con la flecha de atrás y pon
   la escena en marcha con su botón de reproducción (▶).
2. En GrafConnect pulsa **Ejecutar** en la barra superior. Si el botón muestra
   **Pausa**, ya has dado la orden de ejecutar.
3. Acciona el **Pulsador marcha de la escena**, manteniéndolo aproximadamente un
   segundo. No basta con seleccionar su nombre en la lista de asignaciones DRIVER.
4. Mientras el pulsador esté activo, **PM y Q deben indicar 1**, y «Cinta entrada»
   debe moverse. Cuando el pulsador deje de estar activo, **PM y Q deben indicar 0**
   y la cinta debe detenerse. Este ejemplo no memoriza la marcha.
5. No hace falta generar cajas, activar el Emisor ni probar toda la instalación.
   Si PP cambia cuando el Sensor emisor detecta algo, también debería verse en su tarjeta.

Si PM cambia pero Q no lo hace, comprueba primero que GrafConnect está en Ejecutar.
Si PM y Q cambian pero la cinta no, anota ese resultado: no es el mismo problema que
un fallo de conexión. Si PM no cambia, anota si el pulsador aparece activo en Factory I/O.

## Qué significan las palabras

| Texto | Significado para esta conexión |
|---|---|
| Host / IP | Dirección del ordenador donde está escuchando Factory I/O. |
| Puerto | Punto de acceso de la comunicación; aquí 502. |
| Esclavo ID / Unidad | Identificador Modbus; debe coincidir en ambos programas, aquí 1. |
| Inputs / discrete | Entradas digitales: sensores o pulsadores que GrafConnect lee como 0 o 1. |
| Coils | Señales digitales modificables: aquí GrafConnect las escribe para activar o desactivar actuadores. |
| Input Registers | Números que GrafConnect puede leer de sensores analógicos. No se usan en esta prueba. |
| Holding Registers | Números modificables que pueden servir para consignas de actuadores. No se usan en esta prueba. |
| BOOL | Un valor de dos estados: 0/1 o apagado/encendido. |
| Dirección (base 0) | Número del terminal: Input 0 significa dirección 0; Coil 0 también significa dirección 0. |

## Tu respuesta: basta con rellenar esto

| Paso | BIEN / MAL / DUDAS / NO PROBADO | Mensaje o comentario |
|---|---|---|
| Abre el proyecto y aparecen las tres tarjetas | NO PROBADO | |
| Probar conexión confirma la comunicación | NO PROBADO | |
| Conectar confirma conexión mantenida | NO PROBADO | |
| PM cambia al accionar el Pulsador marcha | NO PROBADO | |
| Q cambia junto con PM | NO PROBADO | |
| La cinta de entrada se mueve y se detiene | NO PROBADO | |

Si te atascas, indica **el número del apartado y del paso**, y copia el mensaje.
Esta prueba real sigue pendiente; el proyecto preparado no se conecta automáticamente.

Comprobación parcial realizada por Codex el 29-10-2026: el servidor real
192.168.1.133:502, Esclavo ID 1, respondió a la lectura de Input 0 y Input 1,
ambos con valor 0 en ese momento. No se escribió ninguna salida. Queda pendiente
la prueba del pulsador y del movimiento de la cinta desde la interfaz.
