# Primera conexión: sigue estos pasos con tus capturas

No necesitas crear un GRAFCET para esta prueba: hay uno preparado.
Esta guía se refiere al último estado de tus capturas; si cambias la configuración
de Factory I/O, copia los nuevos valores en GrafConnect.

## 1. Abre el programa y el proyecto preparados

1. Cierra la versión anterior de GrafConnect. Abre **dist/GRAFCET/GRAFCET.exe**
   desde la carpeta `implementacion` de este proyecto.
2. Pulsa la pestaña **E/S externas** y el botón **Abrir prueba guiada**, arriba a
   la derecha. Si no aparece ese botón, estás usando la versión anterior.
3. El título debe indicar «Prueba Factory I O - PM y dos cintas». Este proyecto
   ya tiene etapa inicial, variables y acción. También está disponible en
   `prueba_factoryio_digital/manifest.json`, junto al ejecutable, por si quieres
   abrirlo con **Archivo → Abrir modelo…**.
4. En **E/S externas**, las tres casillas «Usar» deben estar marcadas
   y deben aparecer tres tarjetas. Si no sucede, no continúes: anótalo abajo.

## 2. Comprueba estos valores, sin cambiar tu escena

En Factory I/O, tus capturas muestran **Modbus TCP/IP Server** y este mapa:

| Elemento de la escena | Terminal de Factory I/O | Variable de GrafConnect | Área en GrafConnect | Dirección |
|---|---|---|---|---|
| Pulsador marcha | Input 0 (I00) | PM | Inputs (entradas digitales 0/1) | 0 |
| Cinta entrada | Coil 0 (Q00) | Q00 | Coils (señales digitales 0/1) | 0 |
| Cinta acumulación | Coil 1 (Q01) | Q01 | Coils (señales digitales 0/1) | 1 |

Las entradas y las salidas tienen numeraciones independientes. No escribas I00
o Q00 en la columna Dirección: escribe solo **0**, o **1** para Q01.
El ejemplo no utiliza el sensor emisor ni necesita una entrada PP.

El GRAFCET ya está hecho: **etapa 0 inicial (espera) → transición PM → etapa 1
(acciones continuas Q00 y Q01)**. Al pulsar PM, las dos cintas arrancan y siguen
activas al soltarlo. No hay transición de parada en este ejemplo.

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

## 4. Arranca las dos cintas con el pulsador

1. En Factory I/O vuelve desde DRIVER a la escena con la flecha de atrás y pon
   la escena en marcha con su botón de reproducción (▶).
2. En GrafConnect pulsa **Ejecutar** en la barra superior. Si el botón muestra
   **Pausa**, ya has dado la orden de ejecutar.
3. Acciona el **Pulsador marcha de la escena**, manteniéndolo aproximadamente un
   segundo. No basta con seleccionar su nombre en la lista de asignaciones DRIVER.
4. Al activar el pulsador, **PM debe indicar 1** y la etapa 1 debe quedar activa.
   **Q00 y Q01 deben indicar 1**: «Cinta entrada» y «Cinta acumulación» deben moverse.
   Al soltarlo, PM vuelve a 0, pero ambas cintas siguen en marcha porque el GRAFCET
   permanece en la etapa 1.
5. No hace falta generar cajas, activar el Emisor ni probar toda la instalación.
   Para detener la planta simulada, usa su control de pausa en Factory I/O.
   Pausa en GrafConnect conserva las salidas: no apaga las cintas. Para repetir
   desde la etapa 0, pulsa Reiniciar en GrafConnect (desconecta), luego Conectar
   (solicita cero) y Ejecutar; vuelve a accionar PM.

Si PM cambia pero Q00 y Q01 no, comprueba primero que GrafConnect está en Ejecutar.
Si PM y las salidas cambian pero las cintas no, anota ese resultado: no es el mismo problema que
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
| Q00 y Q01 pasan a 1 al pulsar PM y se mantienen al soltar | NO PROBADO | |
| Se mueven Cinta entrada y Cinta acumulación | NO PROBADO | |

Si te atascas, indica **el número del apartado y del paso**, y copia el mensaje.
Esta prueba real sigue pendiente; el proyecto preparado no se conecta automáticamente.

Comprobación parcial realizada por Codex el 29-10-2026: el servidor real
192.168.1.133:502, Esclavo ID 1, respondió a la lectura de Input 0 y Input 1,
ambos con valor 0 en ese momento. No se escribió ninguna salida. Queda pendiente
la prueba del pulsador y del movimiento de la cinta desde la interfaz.
