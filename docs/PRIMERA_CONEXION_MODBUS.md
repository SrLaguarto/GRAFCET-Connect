# Primera conexión con un simulador de procesos por Modbus

GRAFCET Connect se conecta como **cliente Modbus TCP** a un simulador de procesos que tenga un **servidor Modbus TCP**
activo. Lee sus entradas (sensores, pulsadores) y escribe sus salidas (motores, válvulas) mientras simula el grafcet.

## 1. Preparar el simulador de procesos

1. Abra la escena que quiera controlar.
2. En la configuración del driver, elija **Modbus TCP/IP Server** y actívelo.
3. Anote la **IP** del equipo donde corre el simulador y el **puerto** (normalmente 502).
4. Ponga la escena en marcha.

## 2. Abrir el ejemplo

El programa trae un ejemplo listo: **Prueba-Modbus.grafnet** («Prueba Modbus - PM y dos cintas»). Está en la carpeta
de instalación (por defecto `C:\Program Files\GRAFCET Connect\Prueba-Modbus.grafnet`).

- **Proyecto > Abrir…** y elija ese archivo.
- Una entrada `PM` (pulsador de marcha) y dos salidas `Q00` y `Q01` (dos cintas) ya están asignadas a direcciones
  Modbus.

## 3. Conectar

1. Vaya a la pestaña **E/S externas**.
2. Compruebe **IP**, **Puerto** (502) y **Esclavo ID** (1). La IP se escribe en cuatro casillas; puede pegar la IP entera en la primera. Los valores por defecto son 192.168.1.133:502, esclavo 1.
3. Pulse **Conectar**. El estado pasa a «Conectado»; el panel muestra el valor de cada entrada y salida asignada. En la barra de simulación, la luz de conexión se pone en verde.

Las variables nuevas se asignan solas al primer canal libre de su tipo: digitales en *Input* / *Coil* y numéricas en
*Input Reg* / *Holding Reg*. Por defecto hay 32 canales digitales y 12 numéricos de cada clase (**Canales del
servidor**). Arrastre una variable a otro canal si quiere cambiar la dirección.

## 4. Simular

1. Pulse **Play** (F5). La entrada `PM` que mande el simulador hace avanzar el grafcet y las cintas se mueven.
2. **Stop** detiene la simulación y pone a cero las salidas asignadas.
3. **Reiniciar** (Ctrl+R) vuelve a la situación inicial.

## Señales analógicas

El simulador manda las analógicas como registros con **escala 100**: un registro de 130 vale 1,30.

- Declare esas variables como **Decimal (2 decimales)** para tener el valor exacto.
- Si una variable es **Entera**, el programa redondea al entero más cercano (1,30 → 1; 1,5 → 2), sigue conectado
  y marca la fila en ámbar con el aviso.

## Si algo falla

| Síntoma | Qué revisar |
|---|---|
| «El simulador de procesos no acepta la conexión» | Que la escena esté en marcha, el servidor Modbus activo y la IP correcta. |
| «El simulador de procesos no ha respondido a tiempo» | Red o cortafuegos entre los dos equipos; pruebe con el simulador en el mismo PC. |
| La entrada cambia pero las salidas no | Que la simulación esté en **Play** y que las salidas estén asignadas en E/S externas. |
| Una fila en ámbar | Una Entera recibe decimales: use Decimal (2 decimales). |

Tras un fallo de red, las salidas no están garantizadas: pulse **Conectar** para reanudar.
