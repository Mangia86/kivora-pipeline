# Especificación KIV-101 · Devoluciones y métricas diarias por cliente

**Ticket:** `docs/tickets/KIV-101.md`
**Autor del ticket:** Marta Ibáñez, Control de Gestión (Finanzas)
**Fecha del ticket:** 2026-09-08
**Versión:** 1.0

---

## 1. Objetivo y alcance

### Objetivo

Generar una nueva tabla de negocio, `daily_customer_metrics`, que indique para cada cliente y cada día:

- cuántos pedidos ha hecho (`orders_count`)
- cuánto ha comprado en bruto (`gross_amount`, en EUR)
- cuánto se le ha devuelto (`refunded_amount`, en EUR)
- el importe neto (`net_amount`, en EUR)
- cuántas devoluciones ha tenido (`refunds_count`)
- la fecha de su última compra hasta ese día (`last_purchase_date`)

Las cifras deben cuadrar con contabilidad: expresadas en euros, sin pedidos contados dos veces, y con trazabilidad de los registros que no se han podido usar.

### Alcance

El pipeline existente (`kivora/`, `sql/`) sigue generando `daily_sales.csv` y `top_customers.csv`. KIV-101 añade tres nuevos archivos de salida sin modificar la interfaz de ejecución ni los contratos existentes.

Los tres nuevos archivos de salida son:

1. `output/daily_customer_metrics.csv`
2. `output/rejected.csv`
3. `output/quality_report.json`

El pipeline se ejecuta con el comando inmutable:

```
uv run python -m kivora --inbox <carpeta> --reference <carpeta> --out <carpeta>
```

---

## 2. Exclusiones (fuera de alcance)

Los siguientes elementos no forman parte de KIV-101 y se dejan para fases posteriores o quedan fuera del ticket:

- Modificación de `kivora/`, `sql/` ni `tests/` en esta fase (solo especificación).
- El ticket KIV-102 (cambio de formato de `refunds.json`) no se aborda aquí.
- Cualquier agregación distinta de cliente-día (por ejemplo, métricas solo por cliente o solo por día).
- Corrección de los datos de entrada en `data/inbox/` o `deliveries/`: los problemas de datos se resuelven en el pipeline, no modificando la entrada.
- Envío de notificaciones o alertas externas a Finanzas más allá de `rejected.csv` y `quality_report.json`.

---

## 3. Requisitos funcionales

| ID | Requisito |
|----|-----------|
| RF-1 | Generar `output/daily_customer_metrics.csv` con, como mínimo, las columnas `metric_date`, `customer_id`, `country`, `orders_count`, `gross_amount`, `refunded_amount`, `net_amount`, `refunds_count`, `last_purchase_date`. Una fila por cliente-día con actividad de compra válida. |
| RF-2 | Generar `output/rejected.csv` con, como mínimo, las columnas `source`, `record_id`, `reason`. Una fila por cada devolución o pedido que no se haya podido procesar por un problema del dato (los cuatro motivos de §5.2), con el motivo explícito. Un pedido cancelado o sin pago `captured` es un estado de negocio válido: no cuenta como venta, pero **no** se rechaza por ese solo motivo (A-9). |
| RF-3 | Generar `output/quality_report.json` con la estructura `{"checks": [{"name": "...", "passed": true, "failed_records": 0}, ...]}` y al menos dos controles de calidad. |
| RF-4 | Todos los importes de salida en EUR, con punto decimal y dos decimales. |
| RF-5 | La conversión a EUR usa `data/reference/fx_rates.csv` (`importe_eur = importe × rate_to_eur`). Las monedas no listadas en esa tabla no se convierten: el registro se rechaza e informa. |
| RF-6 | Cada `order_id` cuenta una sola vez en `daily_customer_metrics`, aunque aparezca repetido en varios días o filas. |
| RF-7 | Ante varias versiones de un mismo `order_id`, se usa la más reciente según `updated_at`. En caso de empate de `updated_at`, se conserva la primera aparición encontrada al recorrer los días en orden cronológico (criterio determinista). |
| RF-8 | Un pedido cuenta como venta válida si, en su última versión: (a) `status` distinto de `cancelled`, y (b) tiene al menos un pago con `status = captured`. |
| RF-9 | Los pagos `captured` solo sirven para validar que el pedido se cobró. Nunca multiplican el importe ni el número de pedidos. El importe bruto se toma siempre de `total_amount` del pedido. |
| RF-10 | Cada `refund_id` cuenta una sola vez. Las ocurrencias duplicadas (mismo `refund_id` en varios ficheros o filas) se deduplican en el cálculo y la ocurrencia repetida se informa en `rejected.csv`. |
| RF-11 | Las devoluciones se atribuyen al día de compra original del pedido (`created_at` del pedido) para calcular el neto de ese día. |
| RF-12 | Las devoluciones sobre pedidos que no existen en ninguna entrega se rechazan y se informan en `rejected.csv` con motivo explícito. |
| RF-13 | Las devoluciones sobre pedidos cancelados se rechazan y se informan en `rejected.csv` con motivo explícito (el pedido cancelado no es una venta válida). |
| RF-14 | Las devoluciones parciales y varias devoluciones sobre un mismo pedido se acumulan correctamente en `refunded_amount` y `refunds_count`. |
| RF-15 | Los clientes sin país informado (`country` vacío) se muestran con `country = UNKNOWN`. No se pierden ventas por falta de país. |
| RF-16 | `last_purchase_date` es la fecha de la última compra válida de ese cliente hasta `metric_date` inclusive. Como el grano es una fila por cliente y día **con compra válida** (RF-1) y no se emiten filas de días sin compras, el cliente siempre compró en `metric_date` y, por tanto, `last_purchase_date = metric_date` en todas las filas. La columna se mantiene por el contrato del ticket. |
| RF-17 | El importe neto se calcula como `gross_amount - refunded_amount` por fila cliente-día. Si las devoluciones superan el importe bruto, el neto puede ser negativo: se refleja el dato real y se señala mediante un control de calidad, sin ocultar el registro. |
| RF-18 | El pipeline es determinista: dos ejecuciones sobre los mismos datos de entrada producen ficheros de salida idénticos (byte a byte). |
| RF-19 | El pipeline nunca escribe en la carpeta de entrada (`--inbox`) ni en `deliveries/`. |
| RF-20 | El código de salida del pipeline es 0 cuando termina correctamente, incluso si hay registros rechazados o controles de calidad que fallan. |

---

## 4. Requisitos no funcionales

| ID | Requisito |
|----|-----------|
| RNF-1 | Determinismo de salida (mismo orden de filas, mismos valores, mismos redondeos). |
| RNF-2 | Precisión monetaria: **todos** los cálculos monetarios (conversión a EUR, sumas, restas, comparaciones de los controles y redondeo a dos decimales con `ROUND_HALF_UP`) se hacen en Python con `decimal.Decimal`. No se usa `float` ni `REAL` de SQLite para importes. `CAST ... AS NUMERIC` de SQLite no se considera equivalente a `Decimal` y no se usa para aritmética monetaria; SQL solo selecciona, deduplica y une registros, y los importes viajan como texto hasta Python. |
| RNF-3 | Aplicable a datos futuros desconocidos: las reglas no deben depender de identificadores, fechas o valores concretos de las entregas actuales. |
| RNF-4 | Trazabilidad: todo registro descartado debe aparecer en `rejected.csv` con su `source`, `record_id` y `reason`. |
| RNF-5 | No modificar `data/inbox/` ni `deliveries/`. |
| RNF-6 | La interfaz de ejecución (`--inbox`, `--reference`, `--out`) no cambia. |

---

## 5. Contrato de los archivos de salida

### 5.1 `daily_customer_metrics.csv`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `metric_date` | fecha `AAAA-MM-DD` | Día natural de la métrica (fecha de compra del pedido, en UTC, sin conversión de zona horaria). |
| `customer_id` | texto | Identificador del cliente. |
| `country` | texto | País del cliente (ISO 3166-1 alfa-2). Si el cliente no tiene país, `UNKNOWN`. |
| `orders_count` | entero | Número de pedidos válidos del cliente en ese día. |
| `gross_amount` | decimal | Importe bruto comprado en EUR, dos decimales. |
| `refunded_amount` | decimal | Importe total devuelto en EUR, dos decimales. |
| `net_amount` | decimal | `gross_amount - refunded_amount`, dos decimales. Puede ser negativo. |
| `refunds_count` | entero | Número de devoluciones computadas para ese cliente-día. |
| `last_purchase_date` | fecha `AAAA-MM-DD` | Fecha de la última compra válida del cliente hasta `metric_date` inclusive. Con el grano actual (solo días con compra) coincide con `metric_date` en todas las filas (RF-16). |

**Grano:** una fila por cliente-día con al menos un pedido válido. No hay filas para días sin compras, aunque haya devoluciones atribuidas a ese día (las devoluciones sin compra asociada en ese cliente-día se suman al `refunded_amount` de la fila existente; si no existe fila de compra, la devolución se rechaza en `rejected.csv`).

**Ordenamiento:** por `metric_date` ascendente, luego `customer_id` ascendente (garantiza determinismo).

---

### 5.2 `rejected.csv`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `source` | texto | Origen del registro rechazado: `refunds` (devolución) u `orders` (pedido con moneda no soportada). |
| `record_id` | texto | Identificador del registro rechazado (`refund_id` u `order_id`). |
| `reason` | texto | Motivo del rechazo; cerrado a cuatro valores: `pedido no encontrado` y `pedido cancelado` (devoluciones cuyo pedido no existe o está cancelado), `refund_id duplicado` (segunda y sucesivas ocurrencias) y `moneda no soportada`. |

Un pedido cancelado o sin pago `captured` no genera fila por sí mismo (A-9). Un cliente sin país o inexistente tampoco: su venta se conserva con `country = UNKNOWN` (RF-15).

**Grano:** una fila por registro rechazado.

**Ordenamiento:** por `source` ascendente, luego `record_id` ascendente (garantiza determinismo).

---

### 5.3 `quality_report.json`

Estructura:

```json
{
  "checks": [
    {"name": "<nombre del control>", "passed": true, "failed_records": 0},
    ...
  ]
}
```

Cada control tiene:
- `name`: nombre corto y descriptivo del control.
- `passed`: `true` si ningún registro incumple el control, `false` si al menos uno lo incumple.
- `failed_records`: número de registros que incumplen el control.

Se requiere al menos dos controles (ver sección 8).

---

## 6. Reglas de tratamiento de datos

### 6.1 Duplicados de pedidos

- Varios registros pueden tener el mismo `order_id` en distintos días o dentro de un mismo día (duplicados exactos o versiones actualizadas).
- Se selecciona la versión con el `updated_at` más reciente. En caso de empate, se conserva la primera aparición al recorrer días en orden cronológico.
- El `order_id` seleccionado cuenta una sola vez en `daily_customer_metrics`.

### 6.2 Pagos y validación de venta

- Un pedido es venta válida si su última versión no está `cancelled` y tiene al menos un pago `captured`.
- Los pagos `failed` no invalidan la venta si existe al menos un `captured` para el mismo pedido.
- Un pedido con varios pagos `captured` cuenta como una sola venta. El importe bruto es `total_amount` del pedido, nunca la suma de pagos.

### 6.3 Devoluciones

- Cada `refund_id` cuenta una sola vez. Ocurrencias repetidas se deduplican y se informan en `rejected.csv`.
- Una devolución se asocia al pedido mediante `order_id`.
- Si el pedido no existe en ninguna entrega, la devolución se rechaza (`source=refunds`, `reason=pedido no encontrado`).
- Si el pedido existe pero está cancelado en su última versión, la devolución se rechaza (`source=refunds`, `reason=pedido cancelado`).
- El importe de la devolución se convierte a EUR con `fx_rates.csv`. Si la moneda no está en la tabla, se rechaza.
- Las devoluciones se atribuyen al día de compra del pedido (`created_at`), no al `refunded_at`.
- Varias devoluciones sobre un mismo pedido se acumulan en `refunded_amount` y `refunds_count`.
- Una devolución puede superar el importe bruto del pedido (devolución errónea del origen): se refleja el dato real y se señala por control de calidad, no se oculta.

### 6.4 Monedas y conversión

- Todos los importes (pedidos y devoluciones) se convierten a EUR con `data/reference/fx_rates.csv`: `importe_eur = importe × rate_to_eur`.
- Se usa `Decimal` en Python para la conversión, las sumas y el redondeo a dos decimales con `ROUND_HALF_UP` (RNF-2).
- Si una moneda no aparece en `fx_rates.csv`, el registro se rechaza e informa en `rejected.csv` (`moneda no soportada`).

### 6.5 Datos incompletos

- Cliente sin país (`country` vacío): `country = UNKNOWN` en la salida. La venta no se rechaza por falta de país.
- Cliente no encontrado en `customers.csv` para un pedido válido: el pedido se conserva con `country = UNKNOWN`.
- Pedido sin pagos `captured` o cancelado: no es venta válida y no aparece en métricas; tampoco se rechaza por ese solo motivo (A-9).

---

## 7. Escenarios de aceptación

Todos los escenarios se verifican contra los datos reales de `data/inbox/` (días 2026-09-01 a 2026-09-07). Ningún valor es inventado: se calculó directamente sobre los archivos existentes.

### E-1 — Eliminación correcta de duplicados de pedidos

**Contexto:** `K-10059` aparece dos veces (fila idéntica) en `data/inbox/2026-09-01/orders.csv`. `K-10156` aparece dos veces en `data/inbox/2026-09-06/orders.csv`.

**Resultado esperado:**
- `C009 / 2026-09-01`: `orders_count = 1`, `gross_amount = 45.90` (no 91.80).
- `C017 / 2026-09-06`: `orders_count = 1`, `gross_amount = 23.10` (no 46.20).

**Falla si:** el conteo da 2 o el importe se duplica.

### E-2 — Tratamiento de clientes sin país

**Contexto:** `C007`, `C019` y `C032` tienen `country = ''`. `C007` tiene dos pedidos el 2026-09-01: `K-10009` (166.04 EUR) y `K-10066` (80.62 EUR), más una devolución `R-1021` (41.51 EUR sobre K-10009).

**Resultado esperado:**
- `C007 / 2026-09-01`: `orders_count = 2`, `gross_amount = 246.66`, `refunded_amount = 41.51`, `net_amount = 205.15`, `refunds_count = 1`, `country = UNKNOWN`, `last_purchase_date = 2026-09-01`.

**Falla si:** `country` está vacío, o las filas se omiten por falta de país.

### E-3 — Devolución parcial

**Contexto:** `K-10001` (cliente `C020`, 2026-09-01, 72.77 EUR) tiene la devolución `R-1014` de 21.83 EUR.

**Resultado esperado:**
- `C020 / 2026-09-01`: `orders_count = 1`, `gross_amount = 72.77`, `refunded_amount = 21.83`, `net_amount = 50.94`, `refunds_count = 1`.

**Falla si:** `net_amount` ≠ 50.94 o `refunded_amount` ≠ 21.83.

### E-4 — Varias devoluciones sobre un mismo pedido

**Contexto:** `K-10148` (cliente `C022`, 2026-09-04, 100.00 USD = 92.00 EUR) tiene dos devoluciones: `R-1004` (60.00 USD = 55.20 EUR, archivo 2026-09-05) y `R-1009` (50.00 USD = 46.00 EUR, archivo 2026-09-07). Además `C022` tiene `K-10070` (179.88 USD = 165.49 EUR) y `K-10079` (73.56 USD = 67.68 EUR) el mismo día, y `R-1025` (26.98 USD = 24.82 EUR sobre K-10070).

**Resultado esperado:**
- `C022 / 2026-09-04`: `orders_count = 3`, `gross_amount = 325.17`, `refunded_amount = 126.02`, `net_amount = 199.15`, `refunds_count = 3`, `last_purchase_date = 2026-09-04`.
- El neto del cliente-día es 199.15. Que las devoluciones de `K-10148` (101.20 EUR) superen el importe de ese pedido (92.00 EUR) no se oculta: lo señala el control C-3 (por pedido), no C-2 (por cliente-día, que aquí pasa).

**Falla si:** `refunds_count` ≠ 3, o `refunded_amount` ≠ 126.02, o se cuenta una sola devolución.

### E-5 — Devolución sin pedido asociado

**Contexto:** `R-1003` referencia `K-19999`, que no existe en ningún `orders.csv`.

**Resultado esperado:**
- `rejected.csv` contiene una fila con `source = refunds`, `record_id = R-1003`, `reason` que indique pedido no encontrado.
- No aparece ninguna fila de `daily_customer_metrics` asociada a `K-19999`.

**Falla si:** no está en `rejected.csv`, o aparece una mérica sin pedido base.

### E-6 — Cálculo del importe neto

**Contexto:** `C003` el 2026-09-01 tiene tres pedidos válidos: `K-10010` (214.51 EUR), `K-10015` (124.21 EUR), `K-10053` (107.92 EUR), y una devolución `R-1024` (74.53 EUR sobre K-10015).

**Resultado esperado:**
- `C003 / 2026-09-01`: `gross_amount = 446.64`, `refunded_amount = 74.53`, `net_amount = 372.11`, `refunds_count = 1`.
- `net_amount = gross_amount - refunded_amount` con centavos exactos.

**Falla si:** `net_amount` ≠ `gross_amount - refunded_amount`.

### E-7 — Ausencia de duplicidades después de joins (varios pagos captured)

**Contexto:** `K-10145` (cliente `C018`, 2026-09-04, 210.00 GBP = 245.70 EUR) tiene dos pagos `captured` (84.00 y 126.00 GBP). `K-10146` (cliente `C006`, 2026-09-06, 134.50 EUR) tiene dos pagos `captured` (53.80 y 80.70 EUR).

**Resultado esperado:**
- `C018 / 2026-09-04`: `orders_count = 1`, `gross_amount = 245.70`.
- `C006 / 2026-09-06`: `orders_count = 1`, `gross_amount = 134.50`.

**Falla si:** `orders_count = 2` por esos clientes-días, o `gross_amount` se duplica.

### E-8 — Pedido cancelado no cuenta como venta

**Contexto:** `K-10149` fue `confirmed` el 2026-09-04 (75.00 EUR, cliente `C014`) y pasó a `cancelled` el 2026-09-05. La devolución `R-1005` (75.00 EUR) referencia `K-10149`.

**Resultado esperado:**
- `C014` no tiene fila para `K-10149` en `daily_customer_metrics` el 2026-09-04 (el pedido cancelado no es venta).
- `rejected.csv` contiene una fila con `source = refunds`, `record_id = R-1005`, `reason` que indique pedido cancelado.
- `rejected.csv` **no** contiene ninguna fila con `source = orders` y `record_id = K-10149`: el pedido cancelado es un estado de negocio válido (A-9); solo se rechaza su devolución.

**Falla si:** el pedido cancelado cuenta como venta, `R-1005` no está en `rejected.csv`, o `K-10149` aparece en `rejected.csv` como pedido.

### E-9 — Determinismo

**Contexto:** Ejecutar el pipeline dos veces sobre los mismos `data/inbox/`.

**Resultado esperado:** `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` son idénticos byte a byte entre ambas ejecuciones.

**Falla si:** cualquier diferencia entre ejecuciones.

### E-10 — Conversión de monedas

**Contexto:** `K-10070` (cliente `C022`, 2026-09-04, 179.88 USD). La devolución `R-1025` (26.98 USD sobre K-10070).

**Resultado esperado:**
- `179.88 USD × 0.92 = 165.49 EUR` (incluido en `gross_amount` de `C022 / 2026-09-04`).
- `26.98 USD × 0.92 = 24.82 EUR` (incluido en `refunded_amount` de `C022 / 2026-09-04`).

**Falla si:** importes sin convertir o con tipo de cambio erróneo.

### E-11 — Refund_id duplicado

**Contexto:** `R-1006` aparece dos veces (mismo `refund_id`, `order_id = K-10157`, 12.00 EUR, mismo `refunded_at = 2026-09-05T16:20:00Z`) en los archivos `refunds.json` de **2026-09-05 y 2026-09-06**. El pedido `K-10157` es del cliente `C028`, creado el 2026-09-04.

**Resultado esperado:**
- `C028 / 2026-09-04`: `gross_amount = 196.69`, `refunded_amount = 12.00`, `refunds_count = 1` (no 24.00 ni 2).
- La segunda ocurrencia de `R-1006` (la del fichero 2026-09-06, en orden cronológico de ficheros) aparece en `rejected.csv` como duplicado.

**Falla si:** se suman ambas ocurrencias, o el duplicado no se informa en `rejected.csv`.

### E-12 — Última versión de un pedido por `updated_at` y empate determinista (RF-7)

**Contexto (cambio de importe):** `K-10151` (cliente `C010`, creado el 2026-09-04T07:13:45Z) llega dos veces: en `2026-09-04/orders.csv` con `updated_at = 2026-09-04T07:13:45Z` y `total_amount = 64.00` EUR, y en `2026-09-05/orders.csv` con `updated_at = 2026-09-05T09:12:00Z` y `total_amount = 58.50` EUR. Su único pago es `P-30161` (`captured`, 64.00). El mismo día `C010` compró `K-10076` (199.82 EUR), con la devolución `R-1023` (99.91 EUR).

**Contexto (empate):** `K-10060` (cliente `C021`, 67.25 GBP, creado el 2026-09-02T10:43:52Z) llega en `2026-09-02/orders.csv` y en `2026-09-03/orders.csv` con filas idénticas (mismo `updated_at = 2026-09-02T10:43:52Z`). Su devolución es `R-1017` (33.62 GBP).

**Resultado esperado:**
- `C010 / 2026-09-04`: `orders_count = 2`, `gross_amount = 258.32` (199.82 + **58.50**, no 64.00 ni la suma de las dos versiones), `refunded_amount = 99.91`, `net_amount = 158.41`, `refunds_count = 1`. Se usa `total_amount` de la última versión (58.50), no el importe del pago (64.00).
- `C010 / 2026-09-05`: `orders_count = 1`, `gross_amount = 41.55` (solo `K-10104`): la actualización del 2026-09-05 no crea ni altera una fila de ese día, porque el pedido se atribuye a su `created_at`.
- `C021 / 2026-09-02`: `orders_count = 1`, `gross_amount = 78.68` (67.25 GBP × 1.17), `refunded_amount = 39.34` (33.62 GBP × 1.17), `net_amount = 39.34`, `refunds_count = 1`. `C021` no tiene fila el 2026-09-03: la aparición repetida de `K-10060` ese día no genera una venta.

**Falla si:** `C010 / 2026-09-04` usa 64.00 o suma ambas versiones, aparece `K-10151` el 2026-09-05, o `K-10060` cuenta dos veces.

### E-13 — Pedido confirmado sin pago cobrado no es venta (RF-8)

**Contexto:** `K-10062` (cliente `C024`, creado el 2026-09-02T19:31:03Z, `status = confirmed`, 99.00 EUR) tiene dos pagos, `P-30066` y `P-30067`, ambos `failed` (99.00). No tiene ningún pago `captured`. `C024` tiene ese día otro pedido válido: `K-10020` (197.51 EUR).

**Resultado esperado:**
- `C024 / 2026-09-02`: `orders_count = 1`, `gross_amount = 197.51`, `refunded_amount = 0.00`, `net_amount = 197.51`, `refunds_count = 0` (`K-10062` no cuenta).
- Con los datos actuales, `K-10062` y `K-10149` (E-8) son los dos únicos pedidos únicos que no son venta (158 pedidos únicos, 156 ventas).
- `rejected.csv` **no** contiene ninguna fila con `source = orders` y `record_id = K-10062`: un pedido sin pago cobrado es un estado de negocio válido que no cuenta como venta (A-9).

**Falla si:** `C024 / 2026-09-02` muestra `orders_count = 2` o `gross_amount = 296.51`, o `K-10062` aparece en `rejected.csv`.

---

## 8. Controles de calidad de datos (`quality_report.json`)

Se incluyen los siguientes controles verificables. Cada uno tiene `name`, `passed` y `failed_records`.

| # | Nombre | Qué comprueba | Registros que fallarían con datos actuales |
|---|--------|---------------|--------------------------------------------|
| C-1 | `net_amount_equals_gross_minus_refunded` | En cada fila de `daily_customer_metrics`, `net_amount = gross_amount - refunded_amount` | Ninguno (si el cálculo es correcto) |
| C-2 | `net_amount_not_negative_anomaly` | `net_amount >= 0` **por fila cliente-día**. Señala los cliente-día en los que lo devuelto supera lo comprado ese día. | **Ninguno** (verificado: 118 filas cliente-día, ninguna con `net_amount < 0`). El control se mantiene para detectar casos futuros |
| C-3 | `refunded_not_exceeds_gross_per_order` | Para cada pedido, la suma de sus devoluciones convertidas no supera el importe bruto del pedido | `K-10148` (devoluciones 101.20 EUR > pedido 92.00 EUR). Es el único pedido en esa situación con los datos actuales |
| C-4 | `no_duplicate_refund_ids` | Cada `refund_id` aparece una sola vez en las devoluciones que se computan, tras la deduplicación | Ninguno (`R-1006` se deduplica antes del cálculo y se informa en `rejected.csv`) |
| C-5 | `all_rejected_records_have_reason` | Cada fila de `rejected.csv` tiene un `reason` no vacío | Ninguno (si `rejected.csv` se genera correctamente) |

**Nota:** C-2 y C-3 pueden fallar con datos válidos del negocio (anomalías de origen). Eso no es un error del pipeline: es la señal que Finanzas pidió explícitamente ("quiero saber cuáles son y por qué"). El pipeline termina con código 0 aunque estos controles fallen; el fallo se reporta en `quality_report.json`.

**Niveles de comprobación.** C-2 se evalúa por cliente-día y C-3 por pedido: son distintos. Con los datos actuales `K-10148` incumple C-3 pero no C-2, porque `C022 / 2026-09-04` compró además `K-10070` y `K-10079` y su neto agregado es 199.15 (E-4). Con los datos actuales, por tanto, solo C-3 reporta `failed_records > 0` (1 registro); C-2 pasa con 0.

---

## 9. Reglas de tratamiento de duplicados, pagos, devoluciones, monedas y datos incompletos

### Duplicados

- **Pedidos:** mismo `order_id` en varias filas → una sola venta, versión más reciente por `updated_at`, empate resuelve por primera aparición cronológica.
- **Devoluciones:** mismo `refund_id` en varias filas → una sola devolución computa, la repetición va a `rejected.csv`.
- **Filas exactas repetidas en un mismo día:** eliminadas por la selección de última versión (son idénticas, no afectan el resultado).

### Pagos

- Un pago `captured` valida la venta. Varios pagos `captured` no multiplican el importe ni el conteo.
- El importe bruto es siempre `total_amount` del pedido.
- Pagos `failed` solos no validan la venta.

### Devoluciones

- Atribuidas al día de compra del pedido (`created_at`), no al `refunded_at`.
- `refund_id` duplicado → deduplicar y reportar.
- Pedido inexistente → rechazar en `rejected.csv`.
- Pedido cancelado → rechazar en `rejected.csv`.
- Varias devoluciones sobre un mismo pedido → acumular.
- Devolución > importe original → reflejar y señalar por QC (C-2, C-3).

### Monedas

- Conversión a EUR con `fx_rates.csv`, `Decimal`, redondeo `ROUND_HALF_UP` a dos decimales.
- Moneda no listada → rechazar e informar.

### Datos incompletos

- Cliente sin país → `UNKNOWN`.
- Cliente no encontrado → `UNKNOWN`.
- Pedido sin pago `captured` → no es venta válida (no se rechaza por ese solo motivo, A-9).

---

## 10. Aclaraciones

Cada ambigüedad detectada en el ticket y en los datos, con las opciones consideradas, la decisión adoptada y la justificación.

### A-1 — ¿A qué día se atribuye una devolución: al día del pedido o al día de la devolución (`refunded_at`)?

**Alternativas:**
- (a) Día del pedido (`created_at`).
- (b) Día de la devolución (`refunded_at`).

**Decisión adoptada:** (a) día del pedido.

**Justificación:** La tabla es una métrica diaria de cliente centrada en su actividad de compra, y `last_purchase_date` refuerza que el eje temporal es la fecha de compra. Atribuir la devolución al día de la compra mantiene `net_amount = gross_amount - refunded_amount` dentro de una misma fila cliente-día de compra, lo que simplifica los controles de calidad y es más útil para contabilidad de margen por día de venta.

### A-2 — ¿Cómo tratar las ocurrencias duplicadas de un mismo `refund_id` (`R-1006` aparece dos veces)?

**Alternativas:**
- (a) Deduplicar y contar una sola vez.
- (b) Contar ambas ocurrencias.
- (c) Deduplicar y reportar la repetición en `rejected.csv`.

**Decisión adoptada:** (c).

**Justificación:** El ticket pide explícitamente no tirar registros sin más y saber cuáles son y por qué. La opción (c) mantiene el cálculo correcto (una sola vez) y da trazabilidad a Finanzas mediante `rejected.csv`.

### A-3 — ¿Qué hacer con una devolución sobre un pedido que no existe (`R-1003` → `K-19999`)?

**Alternativas:**
- (a) Rechazar e informar en `rejected.csv`.
- (b) Ignorar silenciosamente.
- (c) Crear una fila cliente-día con solo la devolución.

**Decisión adoptada:** (a).

**Justificación:** (b) pierde trazabilidad que el ticket exige. (c) no es factible sin `customer_id` del pedido. (a) es la única coherente con "quiero saber cuáles son y por qué".

### A-4 — ¿Qué hacer con una devolución sobre un pedido cancelado (`R-1005` → `K-10149`)?

**Alternativas:**
- (a) Rechazar e informar en `rejected.csv` (el pedido cancelado no es venta válida).
- (b) Aceptar y acumular en la métrica del cliente.

**Decisión adoptada:** (a).

**Justificación:** Un pedido cancelado no es venta válida (RF-8), por lo que su devolución no tiene una fila de métrica donde acumularse. Se rechaza con motivo explícito para trazabilidad.

### A-5 — ¿Qué importe usar para un pedido con varios pagos `captured` de importe distinto?

**Alternativas:**
- (a) `total_amount` del pedido.
- (b) Suma de pagos `captured`.

**Decisión adoptada:** (a).

**Justificación:** Coherente con el contrato existente de `daily_sales` ("cada venta cuenta una sola vez, tenga los pagos que tiene"). Los pagos son evidencia de cobro, no el importe oficial del pedido.

### A-6 — ¿Qué país usar para clientes sin país informado?

**Alternativas:**
- (a) `UNKNOWN`.
- (b) Rechazar la venta.

**Decisión adoptada:** (a).

**Justificación:** Coherente con el contrato de `daily_sales` ("Si el cliente no lo tiene informado, `UNKNOWN`"). No se pierden ventas por falta de país.

### A-7 — ¿Qué representa `last_purchase_date` en una fila cliente-día?

**Alternativas:**
- (a) La fecha de la última compra de ese cliente en ese día (redundante con `metric_date`).
- (b) La última compra válida de ese cliente hasta `metric_date` inclusive.

**Decisión adoptada:** (b).

**Justificación:** (b) es la definición correcta de «última compra» y no depende de que cambie el grano: si en el futuro se emitieran filas de días sin compras, `last_purchase_date` ya tendría el significado acumulativo esperado.

**Consecuencia reconocida:** con el grano vigente (una fila por cliente y día con compra válida; no se añaden filas de días sin compras), el cliente siempre compró en `metric_date`, por lo que `last_purchase_date` **coincide con `metric_date` en todas las filas**. La decisión no aporta información distinta de `metric_date` bajo este alcance; se mantiene porque el ticket pide la columna y para no cambiar su definición si el grano se ampliara.

### A-8 — ¿Se convierten las devoluciones a EUR con `fx_rates.csv`?

**Alternativas:**
- (a) Sí, igual que los pedidos.
- (b) Solo en EUR, rechazar el resto.

**Decisión adoptada:** (a).

**Justificación:** Coherencia con el tratamiento de importes de pedidos. Si la moneda no está en la tabla, se rechaza (RF-5).

### A-9 — ¿Un pedido que no es venta (cancelado o sin pago cobrado) debe aparecer en `rejected.csv`?

**Contexto:** el ticket pide en `rejected.csv` «un registro por cada pedido o devolución que no se ha podido usar». Con los datos actuales hay dos pedidos que no son venta: `K-10149` (cancelado) y `K-10062` (sin pago `captured`).

**Alternativas:**
- (a) No se rechazan: cancelado o impagado es un estado de negocio legítimo, no un defecto del dato; simplemente no cuentan como venta.
- (b) Se rechazan con motivo explícito (`pedido cancelado`, `sin pago cobrado`), de modo que `rejected.csv` explique también por qué faltan pedidos en las métricas.

**Decisión adoptada:** (a). Los pedidos cancelados o sin pago `captured` no aparecen en `rejected.csv` por ese solo motivo. Las devoluciones que no puedan procesarse (pedido inexistente, pedido cancelado, `refund_id` duplicado, moneda no soportada) siguen registrándose como rechazadas.

**Justificación:** son estados de negocio válidos, aunque no cuenten como ventas (RF-8); rechazarlos mezclaría pedidos legítimos con registros con un problema de datos. Coherente con el contrato de `daily_sales`. `rejected.csv` queda reservado a lo que no se pudo procesar.

---

## 11. Consistencia con `assignment.md`

Esta especificación respeta todas las reglas de `assignment.md` aplicables a la fase 2:

- **Interfaz de ejecución inmutable:** se mantiene `uv run python -m kivora --inbox --reference --out`.
- **Los tres archivos de salida exigidos por KIV-101:** `daily_customer_metrics.csv`, `rejected.csv`, `quality_report.json`.
- **`data/inbox/` y `deliveries/` no se modifican:** todas las reglas de tratamiento resuelven problemas en el pipeline.
- **Commits reales y frecuentes:** este spec se entrega en un commit propio.
- **No hay cambios en `kivora/`, `sql/` ni `tests/` en esta fase:** solo especificación.
- **No se crea aún `plan.md` ni el tag `phase-2`:** quedan para los siguientes pasos de la fase 2.

---

## 12. Próximos pasos (fuera de este documento)

Tras la revisión de esta especificación:

1. Redactar `docs/specs/KIV-101/plan.md` (borrador y revisión, al menos dos commits).
2. Fase 3: preparar al agente (permisos en `.claude/settings.json` y mecanismo de extensión).
3. Fase 4: implementar `daily_customer_metrics`, `rejected.csv`, `quality_report.json`, tests y tarea `acceptance` en `tasks.py`.
4. Crear tag `phase-2` al cerrar la fase.
