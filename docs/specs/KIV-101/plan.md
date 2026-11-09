# Plan de implementación KIV-101 · Borrador inicial

**Base:** `docs/specs/KIV-101/spec.md` y `assignment.md` (fase 2).
**Estado:** borrador inicial, tal como se generó. Sin revisión crítica aún.

---

## 1. Objetivo del plan

Implementar la especificación KIV-101: generar `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` a partir de las entregas de la tienda (pedidos, clientes, pagos y devoluciones), manteniendo la interfaz de ejecución inmutable y sin modificar `data/inbox/` ni `deliveries/`.

---

## 2. Pasos concretos de implementación

Cada paso indica la tarea, los archivos afectados y cómo se verifica.

### Paso 1 · Añadir soporte de ingest de `refunds.json`

**Tarea:** Extender `kivora/ingest.py` para leer `refunds.json` de cada día y cargarlo en una tabla `raw_refunds` con columnas `refund_id`, `order_id`, `refunded_at`, `amount`, `currency` y `_day`.

**Archivos afectados:**
- `kivora/ingest.py`: añadir `"refunds"` a `SOURCES` con sus columnas; leer el JSON y crear `raw_refunds`.

**Verificación:** `uv run python tasks.py run` no falla y la tabla `raw_refunds` existe en `output/warehouse.db` con todas las devoluciones de los 4 días nuevos.

---

### Paso 2 · Staging de devoluciones y deduplicación de `refund_id`

**Tarea:** Añadir a `sql/staging.sql` la creación de `stg_refunds` a partir de `raw_refunds`, con conversión de `amount` a REAL y deduplicación por `refund_id` (conservar primera aparición por orden cronológico de archivo).

**Archivos afectados:**
- `sql/staging.sql`: bloque nuevo para `stg_refunds`.

**Verificación:** El número de filas en `stg_refunds` es igual al número de `refund_id` únicos (32 devoluciones totales, 31 únicos porque `R-1006` se duplica).

---

### Paso 3 · Tabla de métricas diarias por cliente

**Tarea:** Crear `sql/daily_customer_metrics.sql` que construya `daily_customer_metrics`:
- Ventas válidas: último `order_id` por `updated_at`, `status <> 'cancelled'`, al menos un pago `captured`.
- Importe bruto: `total_amount` del pedido convertido a EUR con `fx_rates.csv`.
- Devoluciones atribuidas al `created_at` del pedido, acumuladas por cliente-día.
- `last_purchase_date`: máxima fecha de compra válida del cliente hasta `metric_date`.
- Clientes sin país → `UNKNOWN`.
- Ordenamiento por `metric_date`, `customer_id`.

**Archivos afectados:**
- `sql/daily_customer_metrics.sql` (nuevo).

**Verificación:** `output/daily_customer_metrics.csv` tiene las 9 columnas exigidas y las filas de los escenarios E-1 a E-11 coinciden con los valores esperados de `spec.md`.

---

### Paso 4 · Tabla de registros rechazados

**Tarea:** Crear la lógica que genera `rejected.csv` con columnas `source`, `record_id`, `reason`:
- `refunds` con `order_id` inexistente → `pedido no encontrado`.
- `refunds` sobre pedido cancelado → `pedido cancelado`.
- `refund_id` duplicado → `refund_id duplicado`.
- Moneda no en `fx_rates.csv` → `moneda no soportada`.
- Pedidos sin pago `captured` y cancelados como fuente de ventas no válidas (opcional, según decisión de alcance).

**Archivos afectados:**
- `sql/rejected.sql` (nuevo) o integración en `pipeline.py` con Python.

**Verificación:** `output/rejected.csv` contiene `R-1003` (pedido no encontrado), `R-1005` (pedido cancelado) y la segunda ocurrencia de `R-1006` (duplicado).

---

### Paso 5 · Exportación de archivos de salida

**Tarea:** Actualizar `kivora/pipeline.py` para ejecutar los nuevos scripts SQL y exportar las tres tablas a CSV en `--out`:
- `daily_customer_metrics.csv`
- `rejected.csv`
- `daily_sales.csv` y `top_customers.csv` se mantienen sin cambios.

**Archivos afectados:**
- `kivora/pipeline.py`: `SCRIPTS` y `EXPORTS` se amplían.

**Verificación:** `uv run python -m kivora --inbox data/inbox --reference data/reference --out output` genera los 4 archivos CSV con código de salida 0.

---

### Paso 6 · Reporte de calidad (`quality_report.json`)

**Tarea:** Implementar en `kivora/pipeline.py` (o script aparte) la generación de `output/quality_report.json` con los controles C-1 a C-5 de `spec.md`:
- C-1: `net_amount = gross_amount - refunded_amount` en cada fila.
- C-2: `net_amount >= 0` (señala anomalía, no bloquea).
- C-3: devoluciones por pedido no superan bruto del pedido.
- C-4: no hay `refund_id` duplicados tras deduplicación.
- C-5: cada fila de `rejected.csv` tiene `reason` no vacío.

**Archivos afectados:**
- `kivora/pipeline.py` (generación del JSON).

**Verificación:** `quality_report.json` tiene la estructura `{"checks": [...]}`, al menos dos checks, y C-2/C-3 reportan `failed_records > 0` con los datos actuales.

---

### Paso 7 · Tarea `acceptance` en `tasks.py`

**Tarea:** Añadir a `tasks.py` la tarea `acceptance` que ejecute el pipeline sobre `data/inbox/` y compruebe los escenarios de aceptación de `spec.md` (E-1 a E-11), con código de salida 0 solo si todos pasan.

**Archivos afectados:**
- `tasks.py`: nueva tarea `acceptance`.

**Verificación:** `uv run python tasks.py acceptance` termina con código 0 cuando todos los escenarios pasan.

---

### Paso 8 · Tests unitarios

**Tarea:** Añadir tests en `tests/` que cubran, como mínimo:
1. Eliminación correcta de duplicados de pedidos.
2. Tratamiento de valores nulos (país vacío → UNKNOWN).
3. Devoluciones parciales.
4. Varias devoluciones sobre un mismo pedido.
5. Devoluciones sin pedido asociado.
6. Cálculo del importe neto.
7. Ausencia de duplicidades después de joins.

**Archivos afectados:**
- `tests/` (nuevos archivos de test).

**Verificación:** `uv run python tasks.py test` termina con código de salida 0.

---

## 3. Archivos afectados (resumen)

| Archivo | Acción | Motivo |
|---------|--------|--------|
| `kivora/ingest.py` | Modificar | Leer `refunds.json` en `raw_refunds` |
| `sql/staging.sql` | Modificar | Crear `stg_refunds` deduplicado por `refund_id` |
| `sql/daily_customer_metrics.sql` | Crear | Métricas cliente-día con devoluciones atribuidas al día de compra |
| `sql/rejected.sql` | Crear | Registros rechazados con motivo |
| `kivora/pipeline.py` | Modificar | Ejecutar nuevos scripts, exportar 4 CSVs, generar `quality_report.json` |
| `tasks.py` | Modificar | Añadir tarea `acceptance` |
| `tests/` | Crear | Tests de duplicados, nulos, devoluciones parciales, varias, sin pedido, neto, joins |
| `docs/specs/KIV-101/spec.md` | Sin cambios | Base de este plan |

---

## 4. Pruebas

- `uv run python tasks.py test`: tests unitarios (pytest), código de salida 0.
- `uv run python tasks.py acceptance`: escenario completo sobre `data/inbox/`, código de salida 0 solo si todos los escenarios E-1 a E-11 pasan.
- `uv run python tasks.py check`: comprobaciones básicas sobre `output/`.
- Determinismo: ejecutar el pipeline dos veces y comparar archivos de salida byte a byte.

---

## 5. Controles de calidad

Incluidos en `quality_report.json` (espec.md, sección 8):

| ID | Nombre | Condición de fallo |
|----|--------|-------------------|
| C-1 | `net_amount_equals_gross_minus_refunded` | Alguna fila con `net_amount <> gross_amount - refunded_amount` |
| C-2 | `net_amount_not_negative_anomaly` | Alguna fila con `net_amount < 0` |
| C-3 | `refunded_not_exceeds_gross_per_order` | Algún pedido con devoluciones totales > importe bruto del pedido |
| C-4 | `no_duplicate_refund_ids` | Algún `refund_id` repetido tras deduplicación |
| C-5 | `all_rejected_records_have_reason` | Alguna fila de `rejected.csv` con `reason` vacío |

---

## 6. Criterios de aceptación

El plan se considera completo cuando se cumplen todos los escenarios de `spec.md` (E-1 a E-11):

- **E-1:** Duplicados exactos de pedidos no se duplican en el conteo ni el importe.
- **E-2:** Clientes sin país aparecen con `country = UNKNOWN` y sus ventas no se pierden.
- **E-3:** Devolución parcial calcula correctamente `net_amount = gross_amount - refunded_amount`.
- **E-4:** Varias devoluciones sobre un mismo pedido se acumulan en `refunded_amount` y `refunds_count`.
- **E-5:** Devolución sobre pedido inexistente aparece en `rejected.csv` con motivo explícito.
- **E-6:** `net_amount` es exacto a dos decimales (`gross_amount - refunded_amount`).
- **E-7:** Pedidos con varios pagos `captured` cuentan una sola vez y no multiplican el importe.
- **E-8:** Pedidos cancelados no cuentan como venta y sus devoluciones van a `rejected.csv`.
- **E-9:** Dos ejecuciones sobre los mismos datos producen ficheros idénticos.
- **E-10:** Importes en USD y GBP se convierten a EUR con `fx_rates.csv`.
- **E-11:** `refund_id` duplicado se cuenta una vez y la repetición se informa en `rejected.csv`.

Además:
- `uv run python tasks.py test` → salida 0.
- `uv run python tasks.py acceptance` → salida 0.
- `uv run python tasks.py check` → salida 0 sobre `output/`.
- `quality_report.json` contiene al menos dos controles con la estructura especificada.

---

## 7. Criterios de cierre de la fase

- `spec.md` y `plan.md` commiteados (al menos dos commits: borrador y revisión).
- Sin cambios en `kivora/`, `sql/` ni `tests/` en esta fase (solo especificación y plan).
- Tag `phase-2` creado al cerrar la fase (pendiente).
