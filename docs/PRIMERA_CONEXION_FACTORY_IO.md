# Primera conexión: sigue estos pasos con tus capturas

No necesitas crear un GRAFCET para esta prueba: hay uno preparado.
Esta guía se refiere al último estado de tus capturas; si cambias la configuración
de Factory I/O, copia los nuevos valores en GrafConnect.

## 1. Abre el programa y el proyecto preparados

1. Cierra la versión anterior de GrafConnect. Abre **dist/GRAFCET/GRAFCET.exe**
   desde la carpeta `implementacion` de este proyecto.
2. Pulsa el botón **E/S externas** de la barra superior, junto a Reiniciar;
   después **Configuración → Abrir prueba guiada**. La flecha Atrás vuelve al GRAFCET.
3. El título debe indicar «Prueba Factory I O - PM y dos cintas». Este proyecto
   ya tiene etapa inicial, variables y acción. También está disponible en
   `prueba_factoryio_digital/manifest.json`, junto al ejecutable, por si quieres
   abrirlo con **Proyecto → Abrir modelo…**.
4. En **E/S externas** deben aparecer PM en I00, Q00 en Q00 y Q01 en Q01.
   El ejemplo ya está asignado. Para asignar otro modelo, arrastra sus variables
   desde la lista a los terminales. La **×** quita una asignación y también puedes
   arrastrar una señal desde su slot a otro. Si estás conectado, pulsa primero
   **Desconectar / editar**.

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

En GrafConnect abre **Configuración** para comprobar los campos de conexión:

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

### Cantidades y direcciones de canales

En **Configuración → Canales del servidor** copia el offset y la cantidad de
Factory I/O. En tu última captura: offset 0 en las cuatro filas; cantidades
**I=16, Q=16, AI=4, AQ=4**. El ejemplo guiado ya contiene esos valores.
También puedes abrir esta sección desde **+ Canales**, en la cabecera del PLC.
Estos cambios solo ajustan GrafConnect: no crean canales en Factory I/O.
No se pueden deducir por Modbus: tu servidor responde incluso en dirección 65535.
Si reduces un rango y una señal quedaría fuera, quítala o muévela primero.
Con muchos canales, desplaza verticalmente la zona central para ver los demás.

### Solo observar sensores

Puedes conectar con únicamente entradas asignadas, desde Pausa (edición) y sin un
GRAFCET compilable. Se activa observación de solo lectura: no escribe ninguna
salida ni ejecuta el motor. Para controlar actuadores sí necesitas un GRAFCET
válido y pulsar Ejecutar (Play). El estado de conexión muestra el detalle al pasar el ratón.

## 3. Comprueba la conexión, todavía sin mover la cinta

1. En Factory I/O deja activo el driver **Modbus TCP/IP Server**. En tu captura
   aparece un indicador verde y la opción «PARAR»: no pulses PARAR para esta prueba.
   Ese indicador por sí solo no demuestra que GrafConnect esté conectado.
2. En Configuración puedes pulsar **Probar conexión** (opcional, sin escribir salidas).
3. Arriba del panel debe aparecer **«Conexión probada»**; el detalle está al dejar
   el ratón sobre el estado.
   Si aparece otra cosa, copia el mensaje exacto abajo y detente en este punto.
4. Cierra Configuración y pulsa **Conectar** en el panel. Debe aparecer un
   **check verde y «Conectado»**. Sigue pendiente pulsar Ejecutar para mover las cintas.
   Conectar y Probar conexión son dos operaciones distintas: Probar termina su
   comprobación y cierra la conexión; Conectar la mantiene abierta. Si Ejecutar
   está activo, Conectar o Probar conexión lo pasan a Pausa.

## 4. Arranca las dos cintas con el pulsador

Hay un solo control de ejecución: **Ejecutar** (Play) simula y **Pausa** vuelve a editar. Al abrir el ejemplo, el
programa queda en Pausa; con la conexión viva, en Pausa se siguen observando las entradas (PM) y las salidas se
conservan.

1. En Factory I/O vuelve desde DRIVER a la escena con la flecha de atrás y pon
   la escena en marcha con su botón de reproducción (▶).
2. En GrafConnect pulsa **Ejecutar** (Play, F5) en la barra superior. El botón pasa
   a decir **Pausa** mientras la simulación corre; Pausa detiene y vuelve a editar,
   sin cerrar la conexión.
3. Acciona el **Pulsador marcha de la escena**, manteniéndolo aproximadamente un
   segundo. No basta con seleccionar su nombre en la lista de asignaciones DRIVER.
4. Al activar el pulsador, **PM debe indicar 1** y la etapa 1 debe quedar activa.
   **Q00 y Q01 deben indicar 1**: «Cinta entrada» y «Cinta acumulación» deben moverse.
   Al soltarlo, PM vuelve a 0, pero ambas cintas siguen en marcha porque el GRAFCET
   permanece en la etapa 1.
5. No hace falta generar cajas, activar el Emisor ni probar toda la instalación.
   Para detener la planta simulada, usa su control de pausa en Factory I/O.
   Pausa en GrafConnect conserva las salidas: no apaga las cintas, y sigue
   observando PM. Para repetir desde la etapa 0, pulsa Reiniciar (Ctrl+R) en
   GrafConnect: mantiene Modbus conectado y publica las salidas iniciales. Si
   estabas en Ejecutar, la simulación sigue en marcha; si estabas en Pausa, pulsa
   después Ejecutar y vuelve a accionar PM.

Si PM cambia pero Q00 y Q01 no, comprueba primero que GrafConnect está en Play (el botón muestra «Pausa»).
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

## Qué está listo y qué falta verificar

- El responsable ya confirmó el arranque real de las dos cintas con PM.
- Reiniciar mantiene TCP y vuelve al estado y salidas iniciales: en Play sigue en
  Play y en Pausa queda en pausa. Falta confirmar esta nueva conducta en la escena real.
- Paso y Completar recorrido se han retirado: el único control de ejecución es
  Ejecutar (Play, F5), y Pausa vuelve a editar. Para depurar sin Modbus use Play y
  Pausa, y «Avanzar el tiempo…» (menú Simulación, solo en Play).
- Se pueden crear variables **Enteras** y **Decimales**. Para enviarlas deben tener
  papel **Salida**, asignarse a un canal numérico AQ y al Holding Register del
  actuador correspondiente. Los sensores numéricos se leen por AI/Input Registers.
- El transporte admite INT16 (−32768…32767), UINT16 (0…65535) y decimales escalados.
  El modelo admite enteros más grandes, pero no todos caben en un registro Modbus.
  No se redondea ni se recorta automáticamente.
- En las capturas iniciales de tu driver, las cantidades de registros numéricos
  estaban a 0. Para probar números, habilita registros en Factory I/O y asigna
  un sensor/actuador numérico de la escena. Añadir una variable Entera en
  GrafConnect por sí solo no crea ese canal en Factory I/O.
- Para una consigna decimal 3,14 con escala 100 se envía el registro 314. La escala
  está fijada ahora en 100 para todas las señales numéricas de GrafConnect,
  tanto de entrada como de salida, incluidos los mapas guardados antes. Mantén
  el driver Factory I/O también en 100. Factory
  recibe direcciones y valores, no nombres de variables ni acciones GRAFCET.
- Para recibir valores con decimales usa una variable **Decimal**: un registro
  125 representa 1,25 y no cabe exactamente en una variable Entera. No se redondea.
- Analógicas probadas con servidor simulado; quedan por validar con tu escena,
  junto con pérdida de red y reconexión. No se ha implementado FLOAT32 directo ni
  números de 32/64 bits repartidos entre varios registros.
