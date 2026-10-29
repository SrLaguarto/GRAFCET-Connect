# Estado Modbus — continuidad

Objetivo: conexión directa con Factory I/O, panel horizontal PLC con digitales y
analógicas INT16/UINT16 obligatorias. Sin puente ni dependencias nuevas.
Arquitectura: `conexion/` sin Qt; trabajador de red Qt; sesión propiedad exclusiva
del hilo principal; un único reloj de simulación, el QTimer existente. Motor intacto.

Políticas acordadas: pausa conserva estado/salidas; diagnóstico detiene y solicita
cero; desconexión pausa (no garantiza cero); reconexión solicita cero, lee sensores
y exige Ejecutar. No reanudar automáticamente. Conexión apagada por defecto.

Fases: 1 cliente digital COMPLETADA; 2 configuración/mapa COMPLETADA; 3 adaptador digital COMPLETADA; 4 panel PLC COMPLETADA;
5 integración Qt/políticas; 6 ciclo completo; 7 analógicas; 8 regresión/guía/prueba real.
Archivos propios: `conexion/__init__.py`, `conexion/modbus.py`, este registro.
No tocar `.codex/` ni `AGENTS.md`: estaban sin seguimiento al empezar.
Pruebas: `python -m unittest discover -s tests -t tests -p test_modbus.py`: 3 OK
(fragmentación, lectura/escritura, excepciones, desconexión, reconexión, límites).
No se ha probado Factory I/O real. Pendiente ampliar pruebas de timeout/MBAP.
Decisión: implementar primero FC01/02/15; ampliar funciones con sus consumidores.
Fase 2: `conexion/configuracion.py`, `tests/test_modbus_configuracion.py`;
2 pruebas OK (persistencia independiente, preservación por save_project, mapas inválidos).
Fase 3: `conexion/adaptador.py`, `tests/test_modbus_adaptador.py`; 2 pruebas OK
(lote simultáneo, muestras inválidas, salidas continuas/memorizadas, cero sin cambiar motor).
Fase 4: `escritorio/entradas_salidas.py`, `tests/test_modbus_panel.py`; prueba Qt
offscreen OK: mapa digital/analógico, valores, bloqueo de configuración al conectar.
Siguiente tarea exacta: integrar pestaña y coordinador asíncrono usando solo QTimer existente.
Commits autorizados por el usuario, solo pruebas relevantes por unidad; sin push.
