# 07. Medición indicativa de presupuestos

**No es aceptación (U-10).** El equipo no es el de referencia (aún sin fijar), así que estas cifras no comprometen ninguna promesa de rendimiento.

Equipo: Windows-11-10.0.26200-SP0 · AMD64 · 16 CPU lógicas · Python 3.12.10. Modelo: 5 000 etapas, 5 000 transiciones, 10 000 acciones; archivo de 3.9 MB; presentación con 10 000 elementos dibujados.

| Medida | Mediana | Máximo | Objetivo P (doc. 10) | Estado indicativo |
|---|---|---|---|---|
| Validación completa (≤5 s) | 0.997 s | 1.235 s | ≤5 s | dentro |
| Guardar modelo (≤5 s) | 0.458 s | 0.479 s | ≤5 s | dentro |
| Abrir modelo (≤5 s) | 0.260 s | 0.270 s | ≤5 s | dentro |
| Operación de vista (mover), p95 de 100 | 23 ms (mediana) | 27 ms | p95 ≤100 ms | dentro (p95 25 ms) |
| Edición semántica (renombrar), 5 repeticiones | 782 ms | 797 ms | sin objetivo en doc. 10 | informativo |
| Pico de memoria de la validación | 74 MiB | — | ≤2 GiB | dentro |

Observaciones:

- Primera medición: una operación de vista tardaba unos 1 s de mediana (p95 2,7 s), fuera de objetivo, porque toda transacción copiaba el modelo y recalculaba su digest. Desde la corrección (P-IMP-08), una operación de vista solo copia la presentación y no recalcula la revisión semántica.
- Una edición semántica sigue copiando el modelo y recalculando la revisión: su coste es O(tamaño del modelo). Si la interfaz lo necesita, el remedio previsto es un historial por diferencias, que no cambia ni contratos ni formato.
- Las mediciones de aceptación deben repetirse en el equipo y los sistemas de U-10, con cinco repeticiones documentadas, como pide el documento 10.
