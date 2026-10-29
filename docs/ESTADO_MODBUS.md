# Estado Modbus — 29-10-2026

Objetivo implementado: conexión directa Factory I/O, botón E/S con panel de
asignación educativo, digitales y analógicas INT16/UINT16 con escala exacta. Sin puente ni
dependencias nuevas; núcleo grafcet/ intacto y proyectos anteriores compatibles.

Arquitectura: conexion/ sin Qt, un trabajador de red; sesión exclusiva del hilo
principal. El QTimer existente recoge resultados; ningún segundo reloj del motor.
Antes de reanudar se solicita una lectura nueva; después, el avance temporal
existente precede a las muestras recibidas. Muestras completas y salidas efectivas
continuas/memorizadas. Comunicación opcional, desactivada al abrir el programa.

Políticas (P-IMP-50): pausa conserva estado/salidas; diagnóstico detiene y solicita
cero; pérdida pausa sin garantizar cero; reconectar solicita cero, lee sensores y
exige Ejecutar. Probar no escribe. Desconectar manualmente no fuerza cero.
Reiniciar conserva TCP, descarta respuestas anteriores, publica salidas iniciales
y queda en pausa (P-IMP-56). Cambiar de modelo sí desconecta.

Fases 1–7 COMPLETADAS: transporte digital, mapa/persistencia, adaptador, panel,
integración Qt, ciclo simulado y analógicas. Fase 8: regresión, guía y portable
COMPLETADAS; escena digital real confirmada; analógicas/red reales PENDIENTES.

Archivos: conexion/{__init__,modbus,configuracion,adaptador,coordinador}.py,
escritorio/{entradas_salidas,ventana}.py, tests/test_modbus*.py, README, docs/04,
docs/05, docs/resultados_pruebas.json y este registro. .codex/ y AGENTS.md
estaban sin seguimiento al inicio y no se incluyen en los commits de esta tarea.

Validación final: tools/ejecutar_pruebas.py: 302 OK (16 Modbus nuevas);
tools/generar_trazabilidad.py: OK; tools/comprobar_paquete.py: 12 intactos.
Se corrigieron dos regresiones de geometría/pestañas, sin cambiar sus pruebas.
Captura Qt revisada; tools/construir_ejecutable.py OK, con arranque/captura del
portable. Ejecutable: dist/GRAFCET/GRAFCET.exe (copiar la carpeta completa).

Límites: lectura/escritura por señal; el periodo efectivo incluye red y turnos Qt,
pueden perderse pulsos cortos. No tiempo real garantizado; sin garantía de salidas
al perder red. No hay redondeo/saturación de analógicas. Control real completo pendiente.

Hoja de aceptación creada: docs/VALIDACION_FACTORY_IO.md, con resultados
BIEN/MAL/DUDAS/NO PROBADO y comentarios por caso. Pendiente de rellenar;
en la primera entrega no se realizó una prueba real. Cambio documental: revisado
contenido y diff; no se repite la batería automática por añadir esta hoja.

Seguimiento P-IMP-51: instrucciones iniciales insuficientes para el responsable.
Etiquetas explicadas, ayudas y diagnóstico concreto; direcciones propuestas por
área, botón Abrir prueba guiada y proyecto con PM/Input 0, PP/Input 1, Q/Coil 0.
Guía específica en docs/PRIMERA_CONEXION_FACTORY_IO.md; incluida en el portable
junto al proyecto. No se sobrescriben ni incluyen en commit las respuestas que
el responsable empezó a escribir en docs/VALIDACION_FACTORY_IO.md.

Comprobación REAL parcial (29-10-2026): servidor 192.168.1.133:502, unidad 1,
respondió a FC02, Input 0/1 = False/False. Solo lectura; ninguna salida escrita.
Esto verifica acceso y lectura real, no movimiento de actuadores desde la GUI.
Última validación tras P-IMP-51: 304 pruebas OK (18 Modbus), trazabilidad
regenerada y paquete intacto. Portable reconstruido y arranque/captura OK;
incluye prueba_factoryio_digital y la guía. Captura a 1020×850 revisada.

Actualización solicitada por el responsable: no ha probado la versión anterior.
La prueba guiada ahora es un GRAFCET 0 inicial → PM → 1, con acciones continuas
Q00/Q01 en etapa 1; marcha mantenida al soltar PM, sin transición de parada.
Mapa: PM/Input 0 (I00), Q00/Coil 0 (Cinta entrada), Q01/Coil 1 (Cinta acumulación).
Sin PP ni sensor emisor. SFIO18 actualizado: espera, arranque de ambas salidas
y mantenimiento al soltar. No altera el motor ni escribe salidas a la planta real.
Validación de esta actualización: 18 pruebas Modbus OK; captura del GRAFCET
revisada; portable reconstruido con el ejemplo y prueba de arranque superada.
No se repite la batería completa por este cambio de ejemplo, según trabajo por
unidades solicitado. La evidencia general anterior sigue siendo 304 pruebas OK.

ACEPTACIÓN REAL PARCIAL: el responsable confirma en el chat «Ha funcionado»
para el GRAFCET PM/I00 → Q00/Q01 y ambas cintas. No presupone validación de
analógicas, pérdida de red ni todos los casos de la hoja anterior.

P-IMP-53 IMPLEMENTADA, pendiente aceptación visual: panel E/S simplificado con arrastre de variables a
terminales, check verde de conexión confirmada y configuración separada.
Analógicas/formatos/escalas siguen disponibles; asociaciones se guardan en la
carpeta del proyecto si la tiene. Menú compacto Proyecto y barra con iconos.
No se toca el motor ni el cliente Modbus. No se alteran respuestas del responsable
en docs/VALIDACION_FACTORY_IO.md. SFIO19/20 cubren eventos de arrastre y estado.

Regresión final: 306 pruebas OK, incluidas SFIO19/20 (arrastre, sustitución,
rechazo por tipo, bloqueo conectado, ajustes ocultos y check confirmado).
SAPP13 conserva sus comprobaciones temporales y ahora comprueba iconos de
Ejecutar/Pausa en lugar de glifos dentro del texto. Paquete intacto y trazabilidad
regenerada; portable reconstruido con arranque/captura verificados. Vista de
1200×800 revisada. Las respuestas del responsable siguen sin tocarse ni incluirse.

P-IMP-54: el responsable rechaza la estética de P-IMP-53 y revoca expresamente
horizontal/industrial. Nueva vista oscura: listas transparentes izquierda/derecha,
módulo central vertical compacto y terminales en filas. Configuración con servidor
en vertical y detalles técnicos plegados. Se conservan los mapas, arrastre,
analógicas y conexión. Motor y transporte intactos. Capturas principal y ajustes
revisadas, SFIO20 comprueba disposición y ocultación progresiva de detalles.

P-IMP-55: sin pestañas GRAFCET/E/S. Botón E/S externas después de Reiniciar;
flecha Atrás en conexión vuelve al dibujo sin desconectar. SFIO18 comprueba ida
y vuelta. El usuario ha cerrado el ejecutable para permitir su reconstrucción.
Primer intento de empaquetado bloqueado por qwindows.dll en uso; empaquetado
alternativo no superó arranque y NO se entrega. Se reconstruye con el procedimiento
habitual y PATH limpio para evitar DLL ajenas (tal como hace el script existente).

Entrega final P-IMP-54/55: 306 pruebas OK; trazabilidad regenerada y paquete
intacto. Portable habitual dist/GRAFCET/GRAFCET.exe reconstruido y verificado
con arranque/captura tanto de ejemplo como del proyecto de dos cintas. Capturas
finales revisadas y copiadas como Vista_conexion.png y Vista_configuracion.png.
La carpeta alternativa fallida está marcada NO_USAR; no es la entrega válida.

P-IMP-56 IMPLEMENTADA: reinicio de GRAFCET conserva la conexión TCP, sustituye
sesión mediante Session.restart, invalida respuestas antiguas por generación y
escribe salidas iniciales; queda en pausa. SFIO16/21 verifican mismo socket,
reinicio con lectura pendiente y reinicios repetidos. Cierre detiene el QTimer
y el coordinador deja de aceptar trabajo. Cambiar modelo aún desconecta.
Nueva estética conforme a última referencia: tres paneles azul oscuro, tarjetas
arrastrables, canales fijos, LED, asignaciones y contadores. Las listas representan
variables GRAFCET, no un inventario automático de etiquetas de Factory I/O.
Paso/Completar recorrido solo en menú Simulación (depuración, sin Modbus).

Enteros del modelo ya disponibles. Transporte BOOL, INT16/UINT16 y decimal con
escala; no hay FLOAT32 directo ni registros compuestos de 32/64 bits. Digitales
probadas realmente por el responsable; analógicas solo con servidor simulado.
Consulta oficial del driver limitada al contrato de E/S y escalado, no a semántica
GRAFCET: https://docs.factoryio.com/manual/drivers/modbus-server/.

Validación final: 307 pruebas OK (21 Modbus), paquete intacto y trazabilidad
regenerada. Portable reconstruido y arranque/captura OK; captura de la nueva
vista revisada y guardada en dist/GRAFCET/Vista_conexion.png.

Siguiente tarea exacta: validar reinicio conectado en la escena del responsable.
Después validar entradas/salidas analógicas y
pérdida/reconexión reales. Guía: docs/PRIMERA_CONEXION_FACTORY_IO.md.
Quedan después pruebas reales de pausa, pérdida de red y analógicas.
Commits incrementales autorizados; consultar git log. Sin push ni subagentes.
