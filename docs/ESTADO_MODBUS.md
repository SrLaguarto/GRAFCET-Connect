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
al perder red. No hay redondeo/saturación de analógicas. No se ha probado Factory I/O.

Hoja de aceptación creada: docs/VALIDACION_FACTORY_IO.md, con resultados
BIEN/MAL/DUDAS/NO PROBADO y comentarios por caso. Pendiente de rellenar;
no se ha realizado ni declarado una prueba real. Cambio documental: revisado
contenido y diff; no se repite la batería automática por añadir esta hoja.

Siguiente tarea exacta: el responsable rellena primero los casos 1–7 de esa hoja;
después continúa con red, reinicio y analógicas, o comunica el primer fallo.
El responsable abre el portable, confirma edición/driver
Modbus TCP/IP Server, IP/puerto/Slave ID, asigna una escena sencilla y guarda
conexion-factoryio.json; comprobar Probar → Conectar → Ejecutar, sensores,
actuadores, analógicas, pausa y reconexión. Registrar el resultado real antes de
dar por cerrada la aceptación. Guía breve en README, apartado Factory I/O.
Commits incrementales autorizados; consultar git log. Sin push ni subagentes.
