# docs/analysis.md — Análisis del pipeline Kivora (Fase 1 / KIV-100)

Este documento analiza el estado inicial del pipeline de ventas de Kivora, con
evidencias verificables (archivo:línea) sobre cada afirmación. No se ha modificado
ningún archivo de código ni de datos; solo se documenta lo que existe.

---

## 1. Objetivo y alcance

El pipeline lee las entregas diarias de la tienda en `data/inbox/` (pedidos,
clientes y pagos), las carga en SQLite, aplica transformaciones SQL y escribe
tablas de negocio en `output/`. Hoy genera dos tablas: `daily_sales` y
`top_customers`. El análisis se centra en si `daily_sales` cumple su contrato
(`docs/data-contracts/daily_sales.md`), qué prueban realmente los tests, y qué
instrucciones de `CLAUDE.md` son incorrectas.

---

## 2. Cómo funciona el pipeline hoy (paso a paso)

| Paso | Archivo:línea | Qué hace |
|------|---------------|----------|
| 1 | `kivora/__main__.py:16-28` | Punto de entrada `python -m kivora`. Parsea `--inbox`, `--reference` y `--out` y llama a `kivora.pipeline.run`. |
| 2 | `kivora/pipeline.py:26-45` | `run()` crea `output/warehouse.db` (borrando el existente si hay uno) y orquesta carga, SQL y exportación. |
| 3 | `kivora/ingest.py:19-34` | `load_inbox()` lee cada subcarpeta de `data/inbox/` en orden alfabético y carga `orders.csv`, `customers.csv` y `payments.csv` en tablas `raw_orders`, `raw_customers` y `raw_payments`, todo como `TEXT`, con una columna `_day` que indica la carpeta del día. |
| 4 | `kivora/ingest.py:37-42` | `load_reference()` carga `data/reference/fx_rates.csv` en `ref_fx_rates`. |
| 5 | `kivora/pipeline.py:36-37` | Ejecuta en orden `sql/staging.sql`, `sql/daily_sales.sql` y `sql/top_customers.sql`. |
| 6 | `sql/staging.sql:5-15` | Crea `stg_orders`: `DISTINCT` sobre toda la fila, `total_amount` a `REAL`, `order_date = substr(created_at, 1, 10)`. No filtra cancelados ni elige última versión por `order_id`. |
| 7 | `sql/staging.sql:18-24` | Crea `stg_customers`: `DISTINCT` sobre `customer_id, name, country, signup_date`. |
| 8 | `sql/staging.sql:26-35` | Crea `stg_payments`: todas las filas (sin `DISTINCT`), `amount` a `REAL`, sin filtrar por `status`. |
| 9 | `sql/daily_sales.sql:5-19` | Une `stg_orders` ⋈ `stg_payments` (solo `status = 'captured'`) ⋈ `stg_customers`; agrupa por `order_date` y `country`; `orders_count = COUNT(*)`, `gross_amount = ROUND(SUM(total_amount), 2)`; filtra `status <> 'cancelled'`. |
| 10 | `kivora/pipeline.py:38-39` | Exporta `daily_sales` y `top_customers` a CSV en `--out`. |

### Salidas actuales (con los 3 días iniciales de `data/inbox/`)

- `output/daily_sales.csv`: `sales_date,country,orders_count,gross_amount` (17 filas; incluye una fila con país vacío en la línea 2).
- `output/top_customers.csv`: `customer_id,orders_count,gross_amount` (top 10).
- `output/warehouse.db`: base intermedia.

---

## 3. ¿Cumple `daily_sales` su contrato de datos? Incumplimientos detectados

El contrato está en `docs/data-contracts/daily_sales.md`. `daily_sales` **no lo cumple**
en varios puntos:

### 3.1 Conversión de moneda a EUR (incumplimiento)

El contrato (§ Importes) exige convertir todos los importes a EUR usando
`data/reference/fx_rates.csv` (`importe_eur = importe × rate_to_eur`, redondeado
a dos decimales), e informar de las monedas sin tipo de cambio.

- `sql/daily_sales.sql:10` hace `SUM(o.total_amount)` directamente sobre el importe
  en **moneda original**, sin convertir.
- Los datos contienen pedidos en USD y GBP, por ejemplo
  `data/inbox/2026-09-01/orders.csv:19` (`K-10052`, USD, 196.07) y `:20` (`K-10056`,
  GBP, 91.34). Por tanto, `gross_amount` es incorrecto para cualquier fila que
  incluya esas monedas.
- No hay validación de moneda desconocida ni informe de rechazados, contrariamente
  al contrato (§ Importes: "no se usa y se informa de él").

### 3.2 Última versión del pedido (incumplimiento)

El contrato (§ Qué es una venta) exige que un pedido se evalúe en su **última
versión** (mismo `order_id`, `updated_at` posterior), y que cada venta cuente
una sola vez.

- `sql/staging.sql:6-15` aplica `DISTINCT` sobre **toda la fila**, no sobre
  `order_id`. Si la tienda reenvía un pedido modificado (mismo `order_id`,
  `updated_at` posterior, otros campos distintos), ambas versiones coexisten en
  `stg_orders`.
- `docs/sources.md:25-26` confirma que la tienda reenvía pedidos modificados así.
- Como consecuencia, `COUNT(*)` y `SUM()` en `sql/daily_sales.sql` pueden contar
  el mismo pedido dos veces y sumar versiones obsoletas.

### 3.3 Fecha en hora peninsular española (incumplimiento)

El contrato (§ Columnas) exige `sales_date` en `Europe/Madrid` a partir de
`created_at` (que viene en UTC, `docs/sources.md:7`).

- `sql/staging.sql:14` calcula `order_date = substr(created_at, 1, 10)`, que es
  la **fecha UTC**, sin conversión a Madrid.
- `sql/daily_sales.sql:8` solo renombra esa columna como `sales_date`.
- Un pedido a las `2026-09-01T23:30:00Z` ya es 2 de septiembre en Madrid, pero el
  pipeline le asignaría el 1 de septiembre.

### 3.4 País `UNKNOWN` cuando falta (incumplimiento)

El contrato (§ Columnas) exige que si el cliente no tiene país, el valor sea
`UNKNOWN`. `docs/sources.md:34` confirma que `country` puede venir vacío.

- `sql/daily_sales.sql:16` selecciona `c.country` directamente, sin fallback a
  `UNKNOWN`.
- `output/daily_sales.csv:2` muestra una fila `2026-09-01,,3,314.95` con país
  vacío, lo que confirma que no se aplica `UNKNOWN`.

---

## 4. Riesgos (no incumplimientos comprobados, puntos débiles del código)

### 4.1 Pagos duplicados → doble conteo (problema de corrección, no de determinismo)

`sql/staging.sql:26-35` crea `stg_payments` sin `DISTINCT`. Si existen dos pagos
`captured` para la misma orden, el `JOIN` en `sql/daily_sales.sql` duplica la fila
del pedido y por tanto `orders_count` e `gross_amount` para esa orden.

- Ejemplo real de duplicado parcial en los datos:
  `data/inbox/2026-09-01/payments.csv:9-10` tiene `K-10008` con dos pagos (uno
  `failed`, uno `captured`). Aunque hoy solo uno es `captured`, un escenario con
  dos `captured` duplicaría el pedido.

**Nota importante (corrección al análisis preliminar):** esto es un problema de
doble conteo (corrección), no un problema de determinismo. El determinismo se
refiere a que dos ejecuciones idénticas produzcan el mismo fichero.

### 4.2 Determinismo de la salida (riesgo, no comprobado)

El contrato (§ Garantías) asegura que dos ejecuciones sobre los mismos datos dan
el mismo fichero. Las consultas de creación usan `GROUP BY ... ORDER BY`, lo que
determina el orden físico en SQLite, pero la exportación en
`kivora/pipeline.py:18` hace `SELECT * FROM {table}` sin `ORDER BY`. Aunque en
la práctica SQLite suele devolver las filas en orden de creación, no hay una
garantía explícita de orden en la exportación CSV. Esto es un **riesgo** de
incumplimiento de la garantía de determinismo, no un hecho comprobado (no se ha
ejecutado el pipeline dos veces para comparar salida byte a byte en esta fase).

### 4.3 `top_customers` sin conversión de moneda ni deduplicación por pago

`sql/top_customers.sql:8` hace `ROUND(SUM(o.total_amount), 2)` sin convertir a
EUR, y `COUNT(*)` sobre el join con pagos puede duplicar pedidos con varios
pagos capturados. No hay pruebas para esta tabla.

---

## 5. ¿Qué comprueban los tests? ¿Qué falta?

Los cuatro tests de `tests/test_pipeline.py`:

| Test:línea | Qué comprueba realmente |
|------------|-------------------------|
| `test_pipeline_generates_daily_sales:41-44` | Que `daily_sales.csv` tiene al menos una fila. No valida columnas ni valores. |
| `test_sales_dates_are_iso:47-51` | Que `sales_date` tiene formato `\d{4}-\d{2}-\d{2}`. No comprueba que sea la fecha correcta en Madrid. |
| `test_exact_duplicate_orders_counted_once:53-63` | Que una fila de orden idéntica repetida se cuenta una vez. Valida la deduplicación de filas exactamente iguales (`DISTINCT` en `sql/staging.sql`), **no** la selección de la última versión de un pedido modificado. |
| `test_gross_matches_source_total:66-75` | Que la suma de `gross_amount` coincide con la suma de totales de órdenes pagadas y no canceladas en el origen. Este test está construido sobre el comportamiento actual (sin conversión de moneda), por lo que "pasa" aunque el pipeline infrinja el contrato de conversión a EUR. |

**Pruebas que faltan:**
1. Conversión de moneda a EUR para pedidos USD/GBP.
2. Selección de la última versión de un pedido reenviado modificado.
3. País `UNKNOWN` cuando `country` está vacío.
4. Zona horaria: `created_at` en UTC convertido a fecha en `Europe/Madrid`.
5. Moneda sin tipo de cambio: rechazo e informe del registro.
6. Pagos duplicados `captured` sobre una misma orden (doble conteo).
7. Determinismo: dos ejecuciones sobre los mismos datos dan el mismo fichero.
8. La tabla `top_customers` no tiene pruebas en absoluto.

---

## 6. Fiabilidad de la documentación

No se debe confiar ciegamente en la documentación heredada. `CLAUDE.md` contiene
instrucciones incorrectas (detalle en la sección 7). `README.md` es más fiable
sobre cómo preparar el entorno y ejecutar el pipeline, pero no advierte de los
defectos del pipeline respecto al contrato de datos.

---

## 7. Correcciones necesarias de `CLAUDE.md`

`CLAUDE.md` afirma lo siguiente, y es falso o inexistente en el repositorio:

- "Ejecutar el pipeline: `python run.py`" → no existe `run.py`. El comando real
  es `uv run python -m kivora --inbox ... --reference ... --out ...` (o
  `python tasks.py run`).
- "Tests: `python -m unittest discover tests`" → el proyecto usa `pytest`
  (`pyproject.toml:19-21`, `tasks.py:47-49`).
- "Los importes ya vienen en euros" → falso: hay pedidos en USD y GBP y una
  tabla de tipos de cambio en `data/reference/fx_rates.csv`.
- "Las consultas SQL están en `queries/`" → falso: están en `sql/`.

Además, falta información crítica para una sesión nueva: qué no se puede tocar
(`data/inbox/`, `deliveries/`), la interfaz de ejecución inamovible, y cómo se
recibe una entrega (`python tasks.py deliver N`).

---

## 8. Criterios de finalización de la fase 1

Un trabajo de esta fase se considera terminado solo cuando:

1. `docs/analysis.md` existe, con el análisis del pipeline, incumplimientos y
   evidencias verificables (archivo:línea).
2. `CLAUDE.md` contiene instrucciones reales del proyecto (comandos, reglas,
   criterios de finalización).
3. `docs/tickets/KIV-100.md` tiene sus cuatro respuestas completadas con hechos
   comprobados.
4. Se ha verificado que el análisis documenta los incumplimientos de los contratos
   de datos en `docs/data-contracts/` (por ejemplo, `daily_sales.md`) con
   evidencias verificables. **La fase 1 solo exige analizar y documentar esos
   incumplimientos, no corregirlos todavía; las correcciones técnicas
   corresponden a fases posteriores.** También debe pasar `python tasks.py test`.
5. No se han modificado `kivora/`, `sql/` ni `tests/` (restricción de la fase 1,
   `assignment.md:115`).
6. No se han creado commits ni tags aún (se hacen tras la revisión de este
   análisis).
