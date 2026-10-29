# Estado Modbus — 29-10-2026

Arquitectura: conexion/ sin Qt ni dependencias nuevas; trabajador de red único;
sesión/reloj en hilo principal con QTimer existente. Motor grafcet/ intacto.
Conexión opcional y manual. Mapa externo conexion-factoryio.json por ID de variable.

Políticas actuales: pausa conserva estado/salidas. Reiniciar conserva TCP,
recrea sesión, descarta respuestas antiguas y publica salidas iniciales; queda en
pausa (P-IMP-56). Cambiar modelo desconecta. Diagnóstico solicita cero; pérdida
pausa sin garantizar salidas; reconexión manual solicita cero y exige Ejecutar.

Interfaz educativa: botón E/S en barra y Atrás; PLC central, listas laterales,
LED y asignaciones. Paso/Completar solo en menú Simulación para depurar sin Modbus.
P-IMP-57: solo entradas puede conectar desde Editar o sin modelo compilable;
MonitorEntradas no tiene motor ni salidas y no envía escrituras. Mapa se guarda
contra el documento del panel, no contra un modelo de simulación anterior.

P-IMP-58: Configuración muestra offset/cantidad para I/Q/AI/AQ. Campo opcional
canales en JSON de conexión, sin cambiar formato de modelo. Fuera del rango no
se permite asignar; reducirlo con asignaciones fuera se rechaza sin borrarlas.
Sin campo canales se conserva compatibilidad de la vista anterior.
Botón + Canales visible en cabecera PLC; × para quitar y drag desde la propia
tarjeta para mover. Editar desconectado: botón Desconectar / editar y tooltip.
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
