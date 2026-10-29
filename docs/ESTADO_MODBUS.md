# Estado Modbus — 29-10-2026

Objetivo implementado: conexión directa Factory I/O, pestaña E/S con módulo PLC
horizontal, digitales y analógicas INT16/UINT16 con escala exacta. Sin puente ni
dependencias nuevas; núcleo grafcet/ intacto y proyectos anteriores compatibles.

Arquitectura: conexion/ sin Qt, un trabajador de red; sesión exclusiva del hilo
principal. El QTimer existente recoge resultados; ningún segundo reloj del motor.
Antes de reanudar se solicita una lectura nueva; después, el avance temporal
existente precede a las muestras recibidas. Muestras completas y salidas efectivas
continuas/memorizadas. Comunicación opcional, desactivada al abrir el programa.

Políticas (P-IMP-50): pausa conserva estado/salidas; diagnóstico detiene y solicita
cero; pérdida pausa sin garantizar cero; reconectar solicita cero, lee sensores y
exige Ejecutar. Probar no escribe. Desconectar manualmente no fuerza cero.
Al reiniciar/cambiar modelo se desconecta y descartan respuestas pendientes.

Fases 1–7 COMPLETADAS: transporte digital, mapa/persistencia, adaptador, panel,
integración Qt, ciclo simulado y analógicas. Fase 8: regresión, guía y portable
COMPLETADAS; aceptación con una escena real PENDIENTE.

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

Siguiente tarea exacta: el responsable abre el portable actualizado, E/S externas
→ Abrir prueba guiada y sigue docs/PRIMERA_CONEXION_FACTORY_IO.md. Solo falta
que confirme lectura al accionar Pulsador marcha y control de Cinta entrada;
después ampliar validación a pausa, red y analógicas. Registrar los resultados.
Commits incrementales autorizados; consultar git log. Sin push ni subagentes.
