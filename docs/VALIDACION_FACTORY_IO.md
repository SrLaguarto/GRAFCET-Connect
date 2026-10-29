# Validación de GrafConnect con Factory I/O

Rellena la columna **Resultado** con `BIEN`, `MAL`, `DUDAS` o `NO PROBADO`.
En comentarios escribe lo que ocurrió, el mensaje mostrado y lo que esperabas.
Puedes hacer primero los casos 1–7 y dejar las analógicas para después.
No se considera validada la conexión real hasta completar esta hoja.

## Datos de tu prueba

- Fecha:
- Versión y edición de Factory I/O:
- Escena utilizada:
- Driver «Modbus TCP/IP Server» disponible: Sí / No / Dudas
- IP / puerto / Slave ID:
- Proyecto GRAFCET guardado en:
- Archivo de configuración Modbus guardado en:
- Escala configurada en el driver Factory I/O (si pruebas analógicas):

Programa preparado: `dist/GRAFCET/GRAFCET.exe`, desde la carpeta de este repositorio.
Abre ese ejecutable actualizado; si lo copias, copia **toda** la carpeta GRAFCET.
Las pruebas siguientes se hacen con la planta simulada de Factory I/O.

## Preparación mínima

1. En Factory I/O abre una escena sencilla, selecciona **Modbus TCP/IP Server**
   y apunta los datos de conexión. Asigna un sensor a una entrada discreta y un
   actuador a una coil. Anota las direcciones exactas; en GrafConnect son base cero.
2. En GrafConnect crea o utiliza un grafcet con una etapa inicial, una entrada
   booleana `sensor` y una salida booleana `motor`. Añade a la etapa una acción
   continua sobre `motor`, condicionada por `sensor`. No necesita transiciones:
   mientras esa etapa esté activa, el sensor debe gobernar la salida.
3. Guarda el proyecto, pasa a **Simular** y abre **E/S externas**. Marca ambas
   variables y asigna `sensor` a `discrete` y `motor` a `coil`, con las direcciones
   del paso 1. Formato `BOOL`, escala `1`. Configura IP, puerto y unidad.
4. Pulsa **Aplicar mapa** y **Guardar configuración…**. Activa el driver y la
   simulación de la escena en Factory I/O para probar los casos siguientes.

| Nº | Qué hacer | Qué debería ocurrir | Resultado | Comentarios |
|---|---|---|---|---|
| 1 | Abrir E/S externas y revisar el mapa. | Módulo horizontal legible, entradas arriba y salidas abajo; nombre, tipo, dirección e indicador visibles. | NO PROBADO | |
| 2 | Pulsar Probar conexión. | Confirma la conexión sin escribir actuadores ni ejecutar el grafcet. Si falla, copia el mensaje. | NO PROBADO | |
| 3 | Pulsar Conectar sin pulsar Ejecutar. | Conecta, solicita cero en las salidas asignadas y muestra los sensores. El motor GRAFCET espera a Ejecutar. | NO PROBADO | |
| 4 | Pulsar Ejecutar y activar/desactivar el sensor en la escena, manteniendo cada estado al menos un segundo. | Cambian la entrada, la salida motor y el actuador de la escena de forma coherente. | NO PROBADO | |
| 5 | Con el actuador activo, pulsar Pausa y cambiar el sensor. | El estado GRAFCET y la salida se conservan. El indicador del sensor externo puede actualizarse aunque el motor esté pausado. | NO PROBADO | |
| 6 | Volver a pulsar Ejecutar con el sensor cambiado durante la pausa. | Lee de nuevo los sensores antes de reanudar; la salida pasa a corresponder a la entrada actual. | NO PROBADO | |
| 7 | Desconectar, cerrar y volver a abrir el proyecto; revisar E/S externas. | Recupera el mapa guardado y sigue desconectado. No conecta automáticamente. | NO PROBADO | |
| 8 | Ejecutar y cortar la conexión desde el driver de Factory I/O. | Aparece un fallo y se pausa el motor. No se garantiza poner los actuadores a cero sin comunicación: anota cómo quedan. | NO PROBADO | |
| 9 | Restaurar el driver y pulsar Conectar en GrafConnect. | Solicita cero y lee sensores; conserva el estado GRAFCET y exige pulsar Ejecutar. No arranca solo. | NO PROBADO | |
| 10 | Conectar y pulsar Reiniciar. | Desconecta antes de recrear la sesión; no aplica respuestas antiguas y queda pausado. | NO PROBADO | |
| 11 | Si aparece un diagnóstico que detiene el motor, anotar código y comportamiento. No hace falta provocarlo. | Detiene la ejecución y solicita cero. Si falla también la red, muestra que las salidas no están garantizadas. | NO PROBADO | |
| 12 | Probar una entrada analógica según las indicaciones siguientes. | Coinciden valor, signo y escala; se ve el valor en el panel. | NO PROBADO | |
| 13 | Probar una salida analógica según las indicaciones siguientes. | El valor enviado corresponde a la consigna y el actuador de la escena responde. | NO PROBADO | |

## Analógicas: después de la prueba digital

- Usa un sensor analógico de la escena y una entrada GRAFCET decimal de 2 decimales.
  Asígnala al `input-register` que publique el driver. Configura la escala del mapa
  de acuerdo con la del driver: si Factory I/O publica 3,14 como 314, usa escala 100.
  El valor mostrado en GrafConnect debería ser equivalente a 3,14.
- Para una salida, añade una variable de salida decimal y una acción **al activar**
  en la etapa inicial que le asigne una consigna válida para el actuador. Asígnala
  a `holding` con la escala correspondiente. Por ejemplo, 12,50 con escala 100
  transmite 1250; usa ese ejemplo solo si el actuador admite ese valor.
- `INT16` interpreta −32768…32767 y `UINT16` 0…65535 **antes de dividir por la
  escala**. El formato debe corresponder al registro de la escena. Prueba un valor
  negativo únicamente si el sensor/actuador lo admite. No hace falta probar todos
  los límites en la escena: están cubiertos por pruebas automáticas.
- Conectar solicita cero aunque una acción inicial haya dejado una consigna en el
  motor. La consigna se envía al pulsar Ejecutar. No hay redondeo ni saturación:
  una conversión no representable detiene la conexión y muestra el fallo.

## Valoración y dudas

- Valoración general: BIEN / MAL / DUDAS / NO PROBADO
- Caso que debería corregirse primero:
- Mensajes de error (copiar literalmente):
- Comentarios de uso o de aspecto:
- Dudas:

## Comprobaciones ya realizadas por Codex

302 pruebas automáticas superadas, incluidas 16 de Modbus con servidor local
simulado. Paquete original intacto; portable construido con prueba de arranque y
captura Qt. Esto no sustituye la prueba con tu instalación de Factory I/O.
