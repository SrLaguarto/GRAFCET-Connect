# Estado Modbus — 29-10-2026

Arquitectura: conexion/ sin Qt ni dependencias nuevas; trabajador de red único;
sesión/reloj en hilo principal con QTimer existente. Motor grafcet/ intacto.
Conexión opcional y manual. Mapa externo conexion-factoryio.json por ID de variable.

Políticas actuales (segunda ronda, P-IMP-67): pausa pone a cero las coils y holding asignadas y deja el GRAFCET sin estado; Play arranca siempre una sesión nueva desde la situación inicial. Reiniciar conserva TCP,
recrea sesión, descarta respuestas antiguas; en Play lee las entradas antes de escribir y ya no publica salidas iniciales (P-IMP-69; «publica salidas iniciales» de P-IMP-56 queda superado); queda en
pausa (P-IMP-56) [superado en P-IMP-60: en Play sigue en Play]. Abrir otro modelo no desconecta: sus salidas pasan a cero (P-IMP-60). Diagnóstico solicita cero; pérdida
pausa sin garantizar salidas; reconexión manual pone a cero las salidas asignadas antes de la primera lectura y exige Ejecutar. Desconectar pide el cero antes de cerrar el TCP («Desconectado · salidas a cero»); si la red falla, cierra igual, pasa a «error» y avisa «Desconectado · salidas no garantizadas · no se pudo poner a cero la planta» (P-IMP-69). Cerrar la ventana también intenta el cero, sin aviso si la red falla. Probar conexión no escribe.

Interfaz educativa: botón E/S en barra y Atrás; PLC central, listas laterales,
LED y asignaciones. Paso/Completar retirados (P-IMP-60); para depurar sin Modbus, Play, Pausa y «Avanzar el tiempo…» (solo en Play).
P-IMP-57: solo entradas puede conectar desde Editar o sin modelo compilable;
MonitorEntradas no tiene motor ni salidas; Conectar en Pausa escribe solo el cero de las salidas asignadas (P-IMP-67). Mapa se guarda
contra el documento del panel, no contra un modelo de simulación anterior.

P-IMP-58: Configuración muestra offset/cantidad para I/Q/AI/AQ. Campo opcional
canales en JSON de conexión, sin cambiar formato de modelo. Fuera del rango no
se permite asignar; reducirlo con asignaciones fuera se rechaza sin borrarlas.
Sin campo canales se conserva compatibilidad de la vista anterior.
Botón + Canales visible en cabecera PLC; × para quitar y drag desde la propia
tarjeta para mover. [P-IMP-63: sin «+ Canales» (los canales se ajustan en
Configuración) y la × aparece al pasar el ratón por el canal.] Editar desconectado: botón Desconectar / editar y tooltip.
El ejemplo guiado tiene 16/16/4/4 con offsets 0, copiados de la captura del usuario;
no son una detección. Direcciones y formato/escalado se revisan en Configuración.

Detección automática imposible por este servidor: responde incluso a dirección
65535 en las cuatro áreas, pese a 16 digitales/4 registros configurados. Cero no
permite saber si un canal existe, está asignado o qué tipo/escala tiene.

Pruebas reales realizadas: dos cintas PM/I00 -> Q00/Q01 confirmadas por usuario.
Modelo con dos salidas Enteras 1/1 -> INT16 -> Holding 0/1: lectura 1/1 confirmada
y restauración 0/0 confirmada. Sin prueba física de escala/movimiento ni negativos.
Monitor real Input 0 sin motor y sin salidas conectado. Registros de entrada
responden pero no tienen sensores asignados en captura. Evidencia completa:
docs/prueba_real_registros_modbus.json. Control visual detenido por Escape;
posteriormente solo captura del usuario y conexión TCP, sin más control Windows.

Cobertura: BOOL, INT16/UINT16 y decimal exacto escalado. Sin FLOAT32 directo ni
registros compuestos 32/64 bits. Periodo efectivo incluye latencia y solicitudes;
pulsos cortos pueden perderse. No hay garantías de tiempo real ni de salida sin red.

Estado de entrega: observación P-IMP-57 en commit 915b11e, con 308 pruebas OK.
P-IMP-58 COMPLETADA: 311 pruebas OK (25 Modbus); SFIO23/24/25 cubren límites,
persistencia, movimiento, × y gesto desde tarjeta. Portable reconstruido y
arranque/captura verificados. Capturas principal y configuración revisadas.

No tocar respuestas del responsable en docs/VALIDACION_FACTORY_IO.md, .codex/
ni AGENTS.md (estos dos últimos estaban sin seguimiento al inicio).
Commits incrementales autorizados; sin push ni subagentes.
P-IMP-59: escala fija 100 para entradas y salidas numéricas en la aplicación,
también al cargar/guardar mapas anteriores; digitales 1. Campo no editable.
Driver Factory I/O debe seguir en 100; recepción fraccionaria requiere Decimal,
sin redondeos a Entera. Límites de representación INT16/UINT16 siguen vigentes.
SFIO26 verifica valor inicial 100 y migración de mapas. Validación final:
312 pruebas OK (26 Modbus), paquete intacto y trazabilidad regenerada.
Portable reconstruido y arranque/captura verificados. La prueba real histórica
del JSON se hizo con escala 1 antes de esta política; no confundir sus registros
con la conversión actual. Falta validar recepción fraccionaria real con 100.

Siguiente tarea exacta: validar recepción fraccionaria con escala 100 en la escena.
El responsable prueba también desasignar/mover y configurar
cantidades con el portable actualizado. Después validar
reinicio real, lectura de sensores numéricos, escalado y pérdida/reconexión.

Segunda ronda (P-IMP-66 y P-IMP-67; documentada el 30-10-2026, sin ejecutar las pruebas):
- Pausa = todo a 0 hasta nuevo Play (decisión del responsable): pide el cero de las coils y holding asignadas y deja el GRAFCET sin estado. Play siempre arranca desde la situación inicial, leyendo antes las entradas. Reiniciar en Pausa no crea sesión. Pruebas SFIO47, SFIO48, SAPP09 y SAPP17.
- Conectar (sin sesión) escribe el cero de las salidas asignadas antes de la primera lectura («Conectado · Pausa · salidas a cero · observando las entradas»); Probar conexión no escribe (SFIO51). Desconectar escribe el cero antes de cerrar el TCP (SFIO52, SFIO53); con la red caída cierra igual y avisa (SFIO54). Cerrar la ventana: SFIO55 comprueba el cero y el cierre del TCP, no el aviso.
- IP: primera vez 192.168.1.133, puerto 502, esclavo 1 (`CONEXION_INICIAL`); después, la última conexión o prueba con éxito, en QSettings `modbus/host`, `modbus/puerto` y `modbus/unidad` (SFIO43 a SFIO46). El mapa guardado del proyecto manda.
- Panel E/S: se actualiza con el modelo; con la conexión viva avisa de variables nuevas hasta desconectar (SFIO37 a SFIO42).
- Mapa tolerante: `Configuracion.cargar` descarta solo lo que ya no casa, con aviso; un JSON corrupto se rechaza entero (SFIO56, SFIO57). El formato no cambia.
Ronda 4 (P-IMP-68 y P-IMP-69; documentada el 30-10-2026, sin ejecutar las pruebas):
- Play lee antes de escribir: `vincular` ya no escribe nada. Tras Play, y tras Reiniciar en Play, la primera petición es una lectura; se aplican las entradas, se calcula y solo entonces se escribe (SFIO59, SFIO60).
- Abrir un ejemplo o un proyecto deja Pausa sin estado, también en el panel de E/S (SFIO66; SAPP05 a SAPP07).
- Abrir otro proyecto con la conexión viva pone a cero también las salidas del mapa nuevo, con un solo cero por canal (SFIO63, SFIO64).
- Un solo cero tras un diagnóstico o un motor parado (SFIO61, SFIO62).
- Mensajes: una variable asignada que pasa a interna dice «ya no es de entrada ni de salida» (SFIO67). Desconectar con la red caída dice «Desconectado · salidas no garantizadas · no se pudo poner a cero la planta», sin «Pulsa Conectar», y el estado queda en «error» (SFIO54, SFIO65).
- Límite sin decidir: si se abre otro proyecto mientras se prueba la conexión, el estado puede quedarse en «probando» hasta Desconectar (ya ocurría antes). Cerrar la ventana con la red caída sigue sin avisar.
- Pendiente: ejecutar `python tools/ejecutar_pruebas.py` y validar con la escena real.
