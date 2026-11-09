# Plan de implementación KIV-101 · Revisión 1

**Base:** `docs/specs/KIV-101/spec.md` y `assignment.md` (fase 2).
**Estado:** revisión crítica aplicada sobre el borrador inicial (commit 5b25630).

---

## 1. Objetivo del plan

Implementar la especificación KIV-101: generar `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` a partir de las entregas de la tienda (pedidos, clientes, pagos y devoluciones), manteniendo la interfaz de ejecución inmutable y sin modificar `data/inbox/` ni `deliveries/`.

Los tres archivos de salida obligatorios de KIV-101 son distintos de los dos archivos heredados (`daily_sales.csv` y `top_customers.csv`) y se exportan además de ellos, no en sustitución.

---

## 2. Pasos concretos de implementación

Cada paso indica la tarea, los archivos afectados y cómo se verifica.

### Paso 1 · Añadir soporte de ingest de `refunds.json`

**Tarea:** Extender `kivora/ingest.py` para leer `refunds.json` de cada día y cargarlo en una tabla `raw_refunds` con columnas `refund_id`, `order_id`, `refunded_at`, `amount`, `currency` y `_day`. El campo `amount` se almacena como texto para evitar conversión prematura a punto flotante.

**Archivos afectados:**
- `kivora/ingest.py`: añadir `"refunds"` a `SOURCES` con sus columnas; leer el JSON y crear `raw_refunds`.

**Verificación:** `uv run python tasks.py run` no falla y la tabla `raw_refunds` existe en `output/warehouse.db` con todas las devoluciones de todos los días presentes en `data/inbox/`.

---

### Paso 2 · Staging de pedidos: deduplicación de `order_id` por `updated_at`

**Tarea:** Modificar `sql/staging.sql` para que `stg_orders` seleccione una sola versión por `order_id`: la de `updated_at` más reciente. Ante empate de `updated_at`, se conserva la primera aparición encontrada al recorrer los días en orden cronológico (criterio determinista). `total_amount` se mantiene como texto; la conversión a numérico se hace con `Decimal` en Python, no con `REAL` en SQL.

**Archivos afectados:**
- `sql/staging.sql`: bloque de `stg_orders` reescrito para deduplicar por `order_id` con desempate determinista.

**Verificación:** Cada `order_id` aparece una sola vez en `stg_orders`. Para `K-10059`, `K-10060`, `K-10149`, `K-10151` y `K-10156` (múltiples filas en los datos actuales) se conserva la versión con `updated_at` más reciente.

---

### Paso 3 · Staging de pagos: validación sin multiplicación de importes

**Tarea:** Mantener `stg_payments` tal como está (columnas como texto, incluido `amount`). Los pagos se usan únicamente para validar que un pedido tiene al menos un pago `captured`; nunca se suman ni se multiplican para calcular el importe bruto de una venta.

**Archivos afectados:**
- `sql/staging.sql`: sin cambios estructurales, solo confirmar que `stg_payments` no se usa para sumar importes.

**Verificación:** Ningún cálculo de `gross_amount` deriva de `SUM(p.amount)`. El importe bruto siempre es `total_amount` del pedido convertido a EUR.

---

### Paso 4 · Staging de devoluciones y deduplicación de `refund_id`

**Tarea:** Añadir a `sql/staging.sql` la creación de `stg_refunds` a partir de `raw_refunds`, con deduplicación por `refund_id` (conservar primera aparición por orden cronológico de archivo). Las ocurrencias repetidas de un mismo `refund_id` se conservan en `raw_refunds` para poder informarlas en `rejected.csv`; solo se excluyen del cálculo de métricas.

**Archivos afectados:**
- `sql/staging.sql`: bloque nuevo para `stg_refunds`.

**Verificación:** Cada `refund_id` aparece una sola vez en `stg_refunds`. Las ocurrencias duplicadas (como `R-1006` en los datos actuales) están en `raw_refunds` pero no se duplican en `stg_refunds`.

---

### Paso 5 · Tabla de métricas diarias por cliente

**Tarea:** Crear `sql/daily_customer_metrics.sql` que construya `daily_customer_metrics`:
- Ventas válidas: `order_id` único (última versión por `updated_at`), `status <> 'cancelled'`, y al menos un pago `captured` en `stg_payments`.
- Importe bruto: `total_amount` del pedido convertido a EUR con `fx_rates.csv`, usando `Decimal` y redondeo `ROUND_HALF_UP` a dos decimales. Nunca `REAL`.
- Devoluciones atribuidas al `created_at` del pedido (día de compra original), acumuladas por cliente-día desde `stg_refunds`.
- `last_purchase_date`: máxima fecha de compra válida del cliente hasta `metric_date` inclusive.
- Clientes sin país → `UNKNOWN`.
- Ordenamiento por `metric_date`, `customer_id` (determinista).
- Importes calculados con `Decimal` en Python (o con `CAST ... AS NUMERIC` en SQLite evitando `REAL`), nunca con punto flotante.

**Archivos afectados:**
- `sql/daily_customer_metrics.sql` (nuevo).

**Verificación:** `output/daily_customer_metrics.csv` tiene las 9 columnas exigidas y las filas de los escenarios E-1 a E-11 de `spec.md` se verifican con `tasks.py acceptance`.

---

### Paso 6 · Tabla de registros rechazados

**Tarea:** Crear la lógica que genera `rejected.csv` con columnas `source`, `record_id`, `reason`. Los registros que se rechazan son:

- `refunds` con `order_id` inexistente en ningún `orders.csv` → `pedido no encontrado`.
- `refunds` sobre pedido cuya última versión está `cancelled` → `pedido cancelado`.
- `refund_id` duplicado (segunda y sucesivas ocurrencias) → `refund_id duplicado`.
- Pedido o devolución con moneda no presente en `fx_rates.csv` → `moneda no soportada`.

Los rechazados se conservan en `rejected.csv` para trazabilidad; no se descartan silenciosamente.

**Archivos afectados:**
- `sql/rejected.sql` (nuevo) o integración en `kivora/pipeline.py` con Python.

**Verificación:** `output/rejected.csv` contiene los registros rechazados con su `source`, `record_id` y `reason` explícito. Las duplicaciones de `refund_id` aparecen como filas propias en `rejected.csv`.

---

### Paso 7 · Exportación de archivos de salida

**Tarea:** Actualizar `kivora/pipeline.py` para ejecutar los nuevos scripts SQL y exportar los archivos a CSV en `--out`:

- Archivos nuevos de KIV-101: `daily_customer_metrics.csv`, `rejected.csv`, `quality_report.json`.
- Archivos heredados (sin cambios): `daily_sales.csv`, `top_customers.csv`.

La exportación de `daily_customer_metrics.csv` y `rejected.csv` se hace desde las tablas SQL correspondientes; `quality_report.json` se genera desde Python con los resultados de los controles.

**Archivos afectados:**
- `kivora/pipeline.py`: `SCRIPTS` y `EXPORTS` se amplían con los nuevos scripts y la exportación de `quality_report.json`.

**Verificación:** `uv run python -m kivora --inbox data/inbox --reference data/reference --out output` genera los 5 archivos de salida (4 CSV + 1 JSON) con código de salida 0.

---

### Paso 8 · Reporte de calidad (`quality_report.json`)

**Tarea:** Implementar en `kivora/pipeline.py` la generación de `output/quality_report.json` con los controles de `spec.md` (sección 8):

- C-1: `net_amount = gross_amount - refunded_amount` en cada fila (consistencia aritmética).
- C-2: `net_amount >= 0` (anomalía de calidad: devoluciones superan compras del cliente-día; no bloquea la ejecución).
- C-3: devoluciones totales de un pedido no superan su importe bruto (anomalía de calidad; no bloquea).
- C-4: cada `refund_id` aparece una sola vez tras deduplicación (consistencia).
- C-5: cada fila de `rejected.csv` tiene `reason` no vacío (integridad del rechazo).

**Separación clave:** Los controles C-2 y C-3 detectan anomalías de calidad que se reportan en `quality_report.json` con `passed: false`, pero **no** bloquean la ejecución ni impiden la escritura de los archivos de salida. El pipeline termina con código 0 aunque estos controles fallen. Solo un error de infraestructura (falta de archivo de entrada, fallo de SQL, etc.) impide la salida con código 0.

**Archivos afectados:**
- `kivora/pipeline.py` (generación del JSON).

**Verificación:** `quality_report.json` tiene la estructura `{"checks": [{"name": "...", "passed": true/false, "failed_records": N}, ...]}` con al menos dos controles. Con los datos actuales, C-2 y C-3 reportan `failed_records > 0` (anomalías detectadas, no errores bloqueantes).

---

### Paso 9 · Tarea `acceptance` en `tasks.py`

**Tarea:** Añadir a `tasks.py` la tarea `acceptance` que ejecute el pipeline sobre `data/inbox/` y compruebe los escenarios de aceptación de `spec.md` (E-1 a E-11), con código de salida 0 solo si todos pasan. La tarea no usa cantidades fijas de los datos actuales como reglas del pipeline; usa los valores actuales solo como ejemplos esperados en las aserciones.

**Archivos afectados:**
- `tasks.py`: nueva tarea `acceptance`.

**Verificación:** `uv run python tasks.py acceptance` termina con código 0 cuando todos los escenarios pasan.

---

### Paso 10 · Tests unitarios

**Tarea:** Añadir tests en `tests/` que cubran, como mínimo:

1. Eliminación correcta de duplicados de pedidos (mismo `order_id` cuenta una vez).
2. Tratamiento de valores nulos (país vacío → `UNKNOWN`).
3. Devoluciones parciales.
4. Varias devoluciones sobre un mismo pedido.
5. Devoluciones sin pedido asociado (rechazadas en `rejected.csv`).
6. Cálculo del importe neto (`net_amount = gross_amount - refunded_amount`).
7. Ausencia de duplicidades después de joins de pagos (varios `captured` no multiplican el pedido).
8. Ausencia de duplicidades después de joins de devoluciones (varias devoluciones se acumulan, no duplican el pedido).
9. Conversión de monedas a EUR con `fx_rates.csv`.
10. Determinismo: dos ejecuciones sobre los mismos datos dan archivos idénticos.

**Archivos afectados:**
- `tests/` (nuevos archivos de test).

**Verificación:** `uv run python tasks.py test` termina con código de salida 0.

---

## 3. Archivos afectados (resumen)

| Archivo | Acción | Motivo |
|---------|--------|--------|
| `kivora/ingest.py` | Modificar | Leer `refunds.json` en `raw_refunds` (amount como texto) |
| `sql/staging.sql` | Modificar | `stg_orders` deduplicado por `order_id`/`updated_at`; `stg_refunds` nuevo |
| `sql/daily_customer_metrics.sql` | Crear | Métricas cliente-día con devoluciones atribuidas al día de compra |
| `sql/rejected.sql` | Crear | Registros rechazados con motivo explícito |
| `kivora/pipeline.py` | Modificar | Ejecutar nuevos scripts, exportar 4 CSV + 1 JSON, generar `quality_report.json` |
| `tasks.py` | Modificar | Añadir tarea `acceptance` |
| `tests/` | Crear | Tests de duplicados, nulos, devoluciones, neto, joins, monedas, determinismo |
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

| ID | Nombre | Tipo | Condición de fallo |
|----|--------|------|-------------------|
| C-1 | `net_amount_equals_gross_minus_refunded` | Consistencia | Alguna fila con `net_amount <> gross_amount - refunded_amount` |
| C-2 | `net_amount_not_negative_anomaly` | Anomalía | Alguna fila con `net_amount < 0` |
| C-3 | `refunded_not_exceeds_gross_per_order` | Anomalía | Algún pedido con devoluciones totales > importe bruto del pedido |
| C-4 | `no_duplicate_refund_ids` | Consistencia | Algún `refund_id` repetido tras deduplicación |
| C-5 | `all_rejected_records_have_reason` | Integridad | Alguna fila de `rejected.csv` con `reason` vacío |

C-1, C-4 y C-5 son controles de consistencia que deben pasar siempre. C-2 y C-3 son controles de anomalía de negocio que pueden fallar con datos válidos del origen; se reportan en `quality_report.json` pero no bloquean la ejecución.

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
- Los 3 archivos nuevos de KIV-101 (`daily_customer_metrics.csv`, `rejected.csv`, `quality_report.json`) se generan junto a los 2 heredados (`daily_sales.csv`, `top_customers.csv`).

---

## 7. Criterios de cierre de la fase

- `spec.md` y `plan.md` commiteados (al menos dos commits: borrador y revisión).
- Sin cambios en `kivora/`, `sql/` ni `tests/` en esta fase (solo especificación y plan).
- Tag `phase-2` creado al cerrar la fase (pendiente).

---

## 8. Revisión del plan

Cada observación sobre el borrador inicial (commit 5b25630), con la decisión adoptada y su justificación.

### Observación 1 · Evitar REAL para cálculos monetarios; usar Decimal

**Observación:** El borrador usaba `CAST(total_amount AS REAL)` en `stg_orders` y conversión a `REAL` para `stg_refunds`, lo que introduce errores de punto flotante en cálculos monetarios.

**Decisión:** `stg_orders` y `stg_refunds` mantienen `amount`/`total_amount` como texto. La conversión a EUR y el redondeo a dos decimales se hacen con `Decimal` y `ROUND_HALF_UP`, ya sea en Python durante la exportación o con `CAST ... AS NUMERIC` en SQLite (evitando `REAL`).

**Justificación:** `REAL` es punto flotante binario y no es apto para dinero. `Decimal` garantiza exactitud en centavos, requerido por el contrato de dos decimales y por el control C-1.

---

### Observación 2 · Deduplicación de `order_id` por `updated_at` con desempate determinista

**Observación:** El borrador mencionaba "última versión" pero no especificaba el criterio de desempate ante `updated_at` iguales, lo que rompe el determinismo.

**Decisión:** `stg_orders` selecciona la versión con `updated_at` más reciente por `order_id`. Ante empate, se conserva la primera aparición al recorrer los días en orden cronológico.

**Justificación:** Garantiza que dos ejecuciones sobre los mismos datos produzcan la misma fila seleccionada (requisito RF-7 y determinismo RF-18).

---

### Observación 3 · Conservar duplicados de `refund_id` en `rejected.csv`

**Observación:** El borrador decía "deduplicar por `refund_id`" pero no aclaraba qué hacer con las ocurrencias repetidas, riesgo de perder trazabilidad.

**Decisión:** `stg_refunds` deduplica para el cálculo, pero las segunda y sucesivas ocurrencias de un mismo `refund_id` se informan en `rejected.csv` con `reason = refund_id duplicado` (paso 6).

**Justificación:** Cumple el ticket ("quiero saber cuáles son y por qué") y el escenario E-11.

---

### Observación 4 · Diferenciar las 3 salidas obligatorias de los archivos heredados

**Observación:** El borrador decía "exportar las tres tablas a CSV" sin distinguir claramente que `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` son nuevos y se suman a `daily_sales.csv` y `top_customers.csv` sin reemplazarlos.

**Decisión:** El paso 7 enumera explícitamente los 3 archivos nuevos de KIV-101 y los 2 archivos heredados que se mantienen sin cambios. El pipeline genera 5 archivos de salida en total.

**Justificación:** Evita confusiones en la implementación y respeta la interfaz existente (los archivos heredados siguen produciéndose).

---

### Observación 5 · Separar anomalías de calidad de errores bloqueantes

**Observación:** El borrador no dejaba claro si un control de calidad que falla (por ejemplo, neto negativo) debe impedir que el pipeline termine con código 0.

**Decisión:** C-1, C-4 y C-5 son controles de consistencia que deben pasar. C-2 y C-3 son controles de anomalía de negocio: se reportan en `quality_report.json` con `passed: false`, pero el pipeline termina con código 0 igualmente. Solo errores de infraestructura bloquean la salida.

**Justificación:** El ticket pide señalar anomalías ("quiero saber cuáles son y por qué"), no bloquear el pipeline por datos inesperados del origen. Coherente con RF-20.

---

### Observación 6 · No usar cantidades fijas de los datos actuales como reglas del pipeline

**Observación:** El borrador citaba "32 devoluciones totales, 31 únicos porque R-1006 se duplica" como si fueran reglas del pipeline, lo que lo acopla a los datos actuales.

**Decisión:** Las cantidades fijas (32, 31, R-1006, etc.) se mantienen solo como ejemplos de verificación en los pasos de verificación y escenarios de aceptación, nunca como reglas del código. El pipeline no contiene ningún valor hardcodeado de las entregas actuales.

**Justificación:** El pipeline debe funcionar con datos futuros desconocidos (RNF-3, assignment.md punto 2).

---

### Observación 7 · Definir sin ambigüedad qué registros se rechazan

**Observación:** El borrador listaba rechazos de forma dispersa y dejaba una opción "opcional" para pedidos sin pago/cancelados, generando incertidumbre.

**Decisión:** El paso 6 define de forma cerrada y sin ambigüedad los cuatro motivos de rechazo: `pedido no encontrado`, `pedido cancelado`, `refund_id duplicado`, `moneda no soportada`. Los pedidos sin pago `captured` simplemente no son ventas válidas (no aparecen en métricas, no generan rechazo a menos que sean fuente de una devolución rechazada por pedido cancelado/inexistente).

**Justificación:** Trazabilidad completa (RF-4) y claridad para la implementación (RF-12, RF-13).

---

### Observación 8 · Evitar multiplicación de importes en joins de pagos y devoluciones

**Observación:** Un `JOIN` entre pedidos y pagos (o devoluciones) puede multiplicar filas si un pedido tiene varios pagos o varias devoluciones, inflando `gross_amount` o `orders_count`.

**Decisión:**
- Para pagos: se usa `EXISTS` (o `IN`) para validar que hay al menos un `captured`, sin hacer `JOIN` que multiplique. El importe bruto es `total_amount` del pedido, nunca suma de pagos.
- Para devoluciones: se agregan por `order_id` antes de unirse a pedidos, para evitar que una devolución multiplique la fila del pedido.

**Justificación:** Cumple RF-9, RF-14 y el escenario E-7 (un pedido con dos pagos `captured` cuenta una sola vez).
