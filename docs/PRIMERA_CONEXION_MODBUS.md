# Primera conexión con un simulador de fábricas por Modbus

GRAFCET Connect se conecta como **cliente Modbus TCP** a un simulador de fábricas que tenga un **servidor Modbus TCP**
activo. Lee sus entradas (sensores, pulsadores) y escribe sus salidas (motores, válvulas) mientras simula el grafcet.

## 1. Preparar el simulador de fábricas

1. Abre la escena que quieras controlar.
2. En la configuración del controlador, elige **Modbus TCP/IP Server** y actívalo.
3. Anota la **IP** del equipo donde corre el simulador y el **puerto** (normalmente 502).
4. Pon la escena en marcha.

## 2. Abrir el ejemplo

El programa trae un ejemplo listo: **Prueba-Modbus.grafnet** («Prueba Modbus - PM y dos cintas»). Está en la carpeta
de instalación (por defecto `C:\Program Files\GRAFCET Connect\Prueba-Modbus.grafnet`).

- **Proyecto > Abrir…** y elige ese archivo.
- Una entrada `PM` (pulsador de marcha) y dos salidas `Q00` y `Q01` (dos cintas) ya están asignadas a direcciones
  Modbus.

## 3. Conectar

1. Pulsa la luz «E/S externas», a la derecha de la fila de pestañas.
2. Comprueba **IP**, **Puerto** (502) y **Esclavo ID** (1). La IP se escribe en cuatro casillas; puedes pegar la IP entera en la primera. Los valores por defecto son 192.168.1.133:502, esclavo 1.
3. Pulsa **Conectar**. El estado pasa a «● Conectado · servidor:puerto»; el panel muestra el valor de cada entrada y salida asignada. En la barra de simulación, la luz de conexión se pone en verde.

Las variables nuevas se asignan solas al primer canal libre de su tipo: digitales en *Input* / *Coil* y numéricas en
*Input Reg* / *Holding Reg*. Por defecto hay 16 canales digitales y 4 numéricos de cada clase (**Canales del
servidor**). Arrastra una variable a otro canal si quieres cambiar la dirección.

## 4. Simular

1. Pulsa **Simular** (F5). La entrada `PM` que mande el simulador hace avanzar el grafcet y las cintas se mueven.
2. **Detener** detiene la simulación y pone a cero las salidas asignadas.
3. **Reiniciar** (Ctrl+R) vuelve a la situación inicial.

## Señales analógicas

El simulador manda las analógicas como registros con **escala 100**: un registro de 130 vale 1,30.

- Declara esas variables como **Decimal (2 decimales)** para tener el valor exacto.
- Si una variable es **Entera**, el programa redondea al entero más cercano (1,30 → 1; 1,5 → 2), sigue conectado
  y marca la fila en ámbar con el aviso.

## Si algo falla

| Síntoma | Qué revisar |
|---|---|
| «El simulador de fábricas no acepta la conexión» | Que la escena esté en marcha, el servidor Modbus activo y la IP correcta. |
| «El simulador de fábricas no ha respondido a tiempo» | Red o cortafuegos entre los dos equipos; prueba con el simulador en el mismo PC. |
| La entrada cambia pero las salidas no | Que la simulación esté en marcha (**Simular**) y que las salidas estén asignadas en E/S externas. |
| Una fila en ámbar | Una Entera recibe decimales: usa Decimal (2 decimales). |

Tras un fallo de red, las salidas no están garantizadas. Una banda de error da el motivo: corrige la causa y pulsa **Reintentar**. Para terminar la conexión, pulsa **Desconectar**.
