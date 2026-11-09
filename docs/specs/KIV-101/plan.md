# Plan de implementación KIV-101 · Revisión 2

**Base:** `docs/specs/KIV-101/spec.md` y `assignment.md` (fase 2).
**Estado:** revisión 1 (commit b7513de) sobre el borrador inicial (commit 5b25630), más la revisión 2 de cierre de fase (sección 9): precisión monetaria solo con `Decimal` en Python, escenarios E-12 y E-13, y corrección de los controles C-2/C-3.

**Decisión transversal de precisión monetaria.** Todo cálculo monetario (conversión a EUR, sumas, restas, comparaciones de los controles y redondeo `ROUND_HALF_UP` a dos decimales) se hace en Python con `decimal.Decimal` (RNF-2 de `spec.md`). SQL solo selecciona, deduplica y une registros; los importes se guardan y se leen como texto. `CAST ... AS NUMERIC` de SQLite **no** se considera equivalente a `Decimal` y no se usa para aritmética monetaria.

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

**Tarea:** Añadir a `sql/staging.sql` una tabla nueva, `stg_orders_latest`, con una sola versión por `order_id`: la de `updated_at` más reciente (las marcas ISO 8601 UTC con `Z` se ordenan correctamente como texto). Ante empate de `updated_at`, se conserva la primera aparición al recorrer los días en orden cronológico (`_day` ascendente y, dentro del día, orden de carga), por ejemplo con `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC, _day ASC, rowid ASC)`. `total_amount` se mantiene como texto: no se convierte en SQL.

La tabla heredada `stg_orders` (que convierte a `REAL` y alimenta `daily_sales` y `top_customers`) **no se modifica** en este ticket: sus defectos se analizaron en KIV-100 y corregirlos queda fuera del alcance de KIV-101. Las nuevas salidas leen `stg_orders_latest`.

**Archivos afectados:**
- `sql/staging.sql`: bloque nuevo `stg_orders_latest`; `stg_orders` sin cambios.

**Verificación:** Cada `order_id` aparece una sola vez en `stg_orders_latest`. Con los datos actuales, `K-10151` conserva la versión del 2026-09-05 (`total_amount` 58.50, escenario E-12), `K-10149` queda `cancelled` y `K-10060` y `K-10059`/`K-10156` (filas repetidas) aparecen una sola vez.

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

**Tarea:** Dividir el trabajo entre SQL (selección) y Python (aritmética monetaria con `Decimal`):

- `sql/daily_customer_metrics.sql` (nuevo) **solo selecciona y une, sin aritmética**, y deja dos tablas con importes en texto:
  - ventas válidas: una fila por `order_id` de `stg_orders_latest` con `status <> 'cancelled'` y `EXISTS` un pago `captured` en `stg_payments` (sin `JOIN` que multiplique filas), con `customer_id`, `metric_date` (día de `created_at`), `currency`, `total_amount` (texto) y el país del cliente (`UNKNOWN` si falta o si el cliente no existe);
  - devoluciones imputables: una fila por `refund_id` de `stg_refunds` cuyo pedido existe y es una venta válida, con el `metric_date` y el `customer_id` de su pedido, `currency` y `amount` (texto).
- `kivora/metrics.py` (nuevo) calcula con `Decimal`, a partir de esas tablas y de `ref_fx_rates`: conversión a EUR con `ROUND_HALF_UP` a dos decimales, agregación por `(metric_date, customer_id)` de `orders_count`, `gross_amount`, `refunded_amount`, `refunds_count`, `net_amount = gross_amount - refunded_amount` y `last_purchase_date`, ordenación por `metric_date` y `customer_id`, y escritura de `daily_customer_metrics.csv` con importes de dos decimales.
- Atribución de devoluciones al `created_at` del pedido (día de compra original).
- `last_purchase_date` = máxima fecha de compra válida del cliente hasta `metric_date` inclusive. Con una fila por cliente-día con compra (sin filas de días sin compras), coincide con `metric_date` en todas las filas (RF-16).

**Archivos afectados:**
- `sql/daily_customer_metrics.sql` (nuevo).
- `kivora/metrics.py` (nuevo).

**Verificación:** `output/daily_customer_metrics.csv` tiene las 9 columnas exigidas y las filas de los escenarios E-1 a E-13 de `spec.md` se verifican con `tasks.py acceptance`. Ningún importe pasa por `float` ni por `REAL`/`NUMERIC` de SQLite.

---

### Paso 6 · Tabla de registros rechazados

**Tarea:** Crear la lógica que genera `rejected.csv` con columnas `source`, `record_id`, `reason`. Los registros que se rechazan son:

- `refunds` con `order_id` inexistente en ningún `orders.csv` → `pedido no encontrado`.
- `refunds` sobre pedido cuya última versión está `cancelled` → `pedido cancelado`.
- `refund_id` duplicado (segunda y sucesivas ocurrencias) → `refund_id duplicado`.
- Pedido o devolución con moneda no presente en `fx_rates.csv` → `moneda no soportada`.

Los rechazados se conservan en `rejected.csv` para trazabilidad; no se descartan silenciosamente.

**Decidido (A-9 de `spec.md`):** los pedidos cancelados o sin pago `captured` no se rechazan por ese solo motivo: son estados de negocio válidos que no cuentan como venta. Esta lista de cuatro motivos es cerrada; solo las devoluciones que no pueden procesarse (y, por moneda no soportada, pedidos o devoluciones) llegan a `rejected.csv`. Verificación: `K-10149` y `K-10062` no aparecen en `rejected.csv` como pedidos (E-8, E-13), mientras que `R-1005` sí aparece como devolución.

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

**Tarea:** Implementar en `kivora/pipeline.py` (con la aritmética en `kivora/metrics.py`, siempre con `Decimal`) la generación de `output/quality_report.json` con los controles de `spec.md` (sección 8):

- C-1: `net_amount = gross_amount - refunded_amount` en cada fila (consistencia aritmética, comparación exacta entre `Decimal`).
- C-2: `net_amount >= 0` **por fila cliente-día** (anomalía de calidad: lo devuelto supera lo comprado ese cliente-día; no bloquea la ejecución).
- C-3: devoluciones totales de un **pedido** no superan su importe bruto (anomalía de calidad; no bloquea).
- C-4: cada `refund_id` aparece una sola vez tras deduplicación (consistencia).
- C-5: cada fila de `rejected.csv` tiene `reason` no vacío (integridad del rechazo).

**Separación clave:** Los controles C-2 y C-3 detectan anomalías de calidad que se reportan en `quality_report.json` con `passed: false`, pero **no** bloquean la ejecución ni impiden la escritura de los archivos de salida. El pipeline termina con código 0 aunque estos controles fallen. Solo un error de infraestructura (falta de archivo de entrada, fallo de SQL, etc.) impide la salida con código 0.

**Archivos afectados:**
- `kivora/pipeline.py` (generación del JSON).

**Verificación:** `quality_report.json` tiene la estructura `{"checks": [{"name": "...", "passed": true/false, "failed_records": N}, ...]}` con al menos dos controles. Con los datos actuales, solo C-3 reporta `failed_records = 1` (`K-10148`: 101.20 EUR devueltos sobre 92.00 EUR); C-2 pasa con `failed_records = 0` (verificado: 118 filas cliente-día, ninguna con neto negativo). C-2 se mantiene para detectar casos futuros y, como los datos reales no lo ejercitan, su test usa datos sintéticos (paso 10).

---

### Paso 9 · Tarea `acceptance` en `tasks.py`

**Tarea:** Añadir a `tasks.py` la tarea `acceptance` que ejecute el pipeline sobre `data/inbox/` y compruebe los escenarios de aceptación de `spec.md` (E-1 a E-13), con código de salida 0 solo si todos pasan. La tarea no usa cantidades fijas de los datos actuales como reglas del pipeline; usa los valores actuales solo como ejemplos esperados en las aserciones.

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
11. Última versión de un pedido por `updated_at` y desempate determinista (E-12): cambio de importe (`K-10151`) y filas idénticas en dos días (`K-10060`).
12. Pedido confirmado sin pago `captured` no es venta (E-13, `K-10062`).
13. Precisión monetaria con `Decimal`: un caso sintético en el que el redondeo `ROUND_HALF_UP` a dos decimales difiere del que daría un `float` o `REAL` (el caso concreto se fija al implementar, comprobando que el test falla con una implementación en coma flotante).
14. Control C-2 con datos sintéticos que produzcan un neto negativo por cliente-día (los datos reales no lo ejercitan) y control C-3 con el pedido `K-10148`.

**Archivos afectados:**
- `tests/` (nuevos archivos de test).

**Verificación:** `uv run python tasks.py test` termina con código de salida 0.

---

## 3. Archivos afectados (resumen)

| Archivo | Acción | Motivo |
|---------|--------|--------|
| `kivora/ingest.py` | Modificar | Leer `refunds.json` en `raw_refunds` (amount como texto) |
| `sql/staging.sql` | Modificar | Tabla nueva `stg_orders_latest` (una versión por `order_id`) y `stg_refunds`; `stg_orders` heredada sin cambios |
| `sql/daily_customer_metrics.sql` | Crear | Selección de ventas válidas y devoluciones imputables, sin aritmética monetaria |
| `kivora/metrics.py` | Crear | Conversión, agregación, neto y controles con `Decimal` |
| `sql/rejected.sql` | Crear | Registros rechazados con motivo explícito |
| `kivora/pipeline.py` | Modificar | Ejecutar nuevos scripts, exportar 4 CSV + 1 JSON, generar `quality_report.json` |
| `tasks.py` | Modificar | Añadir tarea `acceptance` |
| `tests/` | Crear | Tests de duplicados, nulos, devoluciones, neto, joins, monedas, determinismo |
| `docs/specs/KIV-101/spec.md` | Sin cambios | Base de este plan |

---

## 4. Pruebas

- `uv run python tasks.py test`: tests unitarios (pytest), código de salida 0.
- `uv run python tasks.py acceptance`: escenario completo sobre `data/inbox/`, código de salida 0 solo si todos los escenarios E-1 a E-13 pasan.
- `uv run python tasks.py check`: comprobaciones básicas sobre `output/`.
- Determinismo: ejecutar el pipeline dos veces y comparar archivos de salida byte a byte.

---

## 5. Controles de calidad

Incluidos en `quality_report.json` (espec.md, sección 8):

| ID | Nombre | Tipo | Condición de fallo |
|----|--------|------|-------------------|
| C-1 | `net_amount_equals_gross_minus_refunded` | Consistencia | Alguna fila con `net_amount <> gross_amount - refunded_amount` |
| C-2 | `net_amount_not_negative_anomaly` | Anomalía | Alguna fila **cliente-día** con `net_amount < 0` (con los datos actuales: 0 filas, el control pasa) |
| C-3 | `refunded_not_exceeds_gross_per_order` | Anomalía | Algún **pedido** con devoluciones totales > importe bruto del pedido (con los datos actuales: `K-10148`, 1 registro) |
| C-4 | `no_duplicate_refund_ids` | Consistencia | Algún `refund_id` repetido tras deduplicación |
| C-5 | `all_rejected_records_have_reason` | Integridad | Alguna fila de `rejected.csv` con `reason` vacío |

C-1, C-4 y C-5 son controles de consistencia que deben pasar siempre. C-2 y C-3 son controles de anomalía de negocio que pueden fallar con datos válidos del origen; se reportan en `quality_report.json` pero no bloquean la ejecución.

---

## 6. Criterios de aceptación

El plan se considera completo cuando se cumplen todos los escenarios de `spec.md` (E-1 a E-13):

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
- **E-12:** Se usa la última versión de un pedido por `updated_at` (`K-10151`: 58.50, no 64.00) y las filas repetidas con el mismo `updated_at` (`K-10060`) cuentan una vez.
- **E-13:** Un pedido confirmado sin pago `captured` (`K-10062`) no cuenta como venta.

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

**Decisión:** las tablas de staging de KIV-101 mantienen `amount`/`total_amount` como texto. La conversión a EUR, las sumas y el redondeo a dos decimales se hacen **siempre en Python con `Decimal` y `ROUND_HALF_UP`** (corregido en la revisión 2: la redacción de la revisión 1 admitía también `CAST ... AS NUMERIC` en SQLite, lo que no es equivalente a `Decimal`; ver sección 9).

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

---

## 9. Revisión 2 (cierre de la fase 2)

Cambios sobre la revisión 1 (commit `b7513de`), a raíz de cinco incidencias detectadas al contrastar `spec.md` y `plan.md` con los datos reales. Las decisiones son del usuario.

| # | Incidencia | Decisión | Cambio en este plan | Justificación |
|---|---|---|---|---|
| 1 | `R-1006` figuraba en los ficheros de 09-04 y 09-05 | Corregir a los ficheros reales: **2026-09-05 y 2026-09-06** | Sin cambio de pasos; la verificación del paso 4 sigue válida | Verificado leyendo ambos `refunds.json` |
| 2 | Se afirmaba que C-2 falla con los datos actuales | C-2 se mantiene, pero se corrige: con los datos actuales **pasa** (0 filas cliente-día con neto negativo); solo C-3 falla (`K-10148`) | Paso 8, sección 5 y tests (paso 10, punto 14: C-2 con datos sintéticos) | El -9.20 era el neto del pedido `K-10148`, no de un cliente-día; `C022 / 2026-09-04` tiene neto 199.15 |
| 3 | `last_purchase_date` no aporta información distinta de `metric_date` | Se mantiene el grano actual (una fila por cliente y día con compra); no se añaden filas de días sin compras; se documenta la coincidencia | Paso 5 | Es una consecuencia lógica del grano elegido, no depende de los datos |
| 4 | La revisión 1 presentaba `CAST ... AS NUMERIC` de SQLite como alternativa a `Decimal` | Todo cálculo monetario en Python con `Decimal`; SQL solo selecciona, deduplica y une, con importes en texto | Cabecera, pasos 2, 5 y 8, tabla de archivos (nuevo `kivora/metrics.py`), tests 13 y 14; observación 1 corregida | `CAST AS NUMERIC` no equivale a `Decimal`; con `Decimal` en Python los controles comparan importes exactos |
| 5 | Faltaban escenarios para RF-7 y RF-8 | Añadir **E-12** (`K-10151` cambia de 64.00 a 58.50 EUR; `K-10060` repetido con el mismo `updated_at`) y **E-13** (`K-10062` sin pago cobrado) | Pasos 9 y 10, secciones 4 y 6 | Cifras verificadas sobre `data/inbox/`: `C010 / 2026-09-04` bruto 258.32; `C021 / 2026-09-02` 78.68; `C024 / 2026-09-02` 197.51 |

**Decisión de diseño confirmada por el usuario.** Para no alterar las salidas heredadas, el paso 2 crea `stg_orders_latest` y conserva `stg_orders` sin cambios. Corregir los defectos de `daily_sales` y `top_customers` identificados en KIV-100 queda fuera de KIV-101.

**Aclaración A-9, resuelta.** Los pedidos cancelados o sin pago cobrado no aparecen en `rejected.csv` por ese solo motivo; las devoluciones que no puedan procesarse siguen rechazándose (paso 6).

**Aclaraciones de las decisiones 2 y 10.** El usuario confirmó que están documentadas en RF-7 y RF-17 y que no hacen falta entradas nuevas en «Aclaraciones» de `spec.md`.
