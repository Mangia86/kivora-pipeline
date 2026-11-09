# Especificación KIV-102 · Soporte del nuevo formato de `refunds.json`

- **Ticket:** `docs/tickets/KIV-102.md` (Plataforma, 2026-09-11).
- **Documentos de partida:** `docs/specs/KIV-102/impact.md` (commit `677fc96`) y `docs/specs/KIV-101/spec.md`.
- **Alcance de este documento:** solo lo que cambia. Todo lo que no se menciona aquí sigue como en la especificación de KIV-101
  (RF-1 a RF-23, RNF-1 a RNF-6, contratos de salida y controles C-1 a C-6).

## 1. Objetivo y alcance

**Objetivo.** Que el pipeline lea correctamente las devoluciones de `refunds.json` tanto en el formato anterior (`amount`) como en el nuevo
(`refund_amount` y `reason`), de modo que no se pierdan devoluciones válidas y que las salidas de KIV-101 mantengan su contrato.

**Por qué.** Hoy, con los datos de los días 08 a 10, 14 de las 15 devoluciones nuevas se rechazan como `importe no valido` sin que ningún control lo señale (`impact.md` §2).

**Dentro del alcance**

- Lectura de los dos formatos de `refunds.json`, que conviven en `data/inbox/` (ticket: «los ficheros anteriores no se van a reenviar»).
- Tratamiento de `reason` (incluido `null`).
- Tratamiento de registros con los dos campos de importe o con ninguno.
- Mecanismo para que un fallo de este tipo no vuelva a pasar inadvertido.

**Fuera de alcance**

- Cambiar el contrato de `daily_customer_metrics.csv`, `rejected.csv`, `quality_report.json`, `daily_sales.csv` o `top_customers.csv` (columnas, orden, motivos de rechazo).
- Usar `reason` para analítica o para ninguna salida: el ticket no lo pide.
- Cambiar la regla de atribución de devoluciones, la conversión de moneda, el tratamiento de duplicados o los controles C-1 a C-6.
- Reescribir los documentos históricos de KIV-101.
- Cambiar la interfaz de ejecución (`--inbox`, `--reference`, `--out`).

## 2. Requisitos

| ID | Requisito | Verificación |
| --- | --- | --- |
| RC-1 | El pipeline acepta devoluciones con el importe en `refund_amount` (formato nuevo) y las trata como las del formato anterior: conversión a EUR, atribución al día de compra, acumulación en `refunded_amount` y `refunds_count`. | E-1, E-2, E-3, E-5, E-8 |
| RC-2 | El pipeline sigue aceptando `amount` (formato anterior). Los ficheros de los días 01 a 07 dan las mismas cifras que antes del cambio, salvo las filas que reciben devoluciones nuevas. | E-6 |
| RC-3 | Los dos formatos pueden convivir en el mismo `--inbox` y en el mismo pedido. La detección se hace **por registro**, no por fichero. | E-4 |
| RC-4 | Si un registro trae ambos campos de importe, se usa `refund_amount` (regla defensiva: no ocurre en los datos actuales). | E-9 |
| RC-5 | Un campo de importe cuenta como **presente** si la clave existe y su valor no es `null` ni una cadena vacía o de solo espacios. Si el registro no tiene ningún campo de importe presente, se rechaza con `source=refunds` y `reason=importe no valido` (motivo ya existente, RF-23). No se cuenta como 0. | E-9 |
| RC-6 | `reason` no es obligatorio: ausente, `null`, vacío o con texto no provoca rechazo ni cambia ningún importe. | E-1, E-10 |
| RC-7 | El **valor** del campo `reason` de `refunds.json` no aparece en ninguna salida (`daily_customer_metrics.csv`, `rejected.csv`, `quality_report.json`, `daily_sales.csv`, `top_customers.csv`). No cambia ninguna cabecera: la columna `reason` de `rejected.csv` es el motivo de rechazo de KIV-101 y no tiene relación con el campo `reason` de la devolución. La tabla intermedia `raw_refunds` (`output/warehouse.db`) gana la columna `reason`, con el texto sin tratar (`null` se guarda como cadena vacía, igual que el resto de campos). `sql/staging.sql` y las tablas `kpi_*` no la propagan. | E-10 |
| RC-8 | Campos desconocidos en un registro de `refunds.json` se ignoran sin error (regla defensiva, no presente en los datos actuales). | E-11 |
| RC-9 | Con los datos de los días 01 a 10, el pipeline no produce ningún `importe no valido` por falta de `amount` en los registros del formato nuevo. | E-7 |
| RC-10 | Los controles de calidad existentes (C-1 a C-6) pasan a evaluar las devoluciones del formato nuevo sin cambios; las anomalías que aparezcan se informan y **no** se ocultan (RF-17 de KIV-101). | E-5, E-7 |
| RC-11 | Las salidas de KIV-101 conservan columnas, orden, formato y determinismo (RF-18, RNF-1). | E-12 |
| RC-12 | `tasks.py acceptance` conserva sus 28 comprobaciones de KIV-101 (ejecución limitada a 2026-09-07) y añade una segunda pasada sobre todos los días de `data/inbox/` con las comprobaciones de los escenarios reales E-1 a E-8 de este documento. Código de salida 0 solo si todas pasan. | `tasks.py acceptance` |
| RC-13 | No se modifican `data/inbox/` ni `deliveries/` (RNF-5). | `git diff` |

**Dónde se verifica cada escenario.** E-1 a E-8 (datos reales): `tasks.py acceptance` (segunda pasada) y tests de `pytest` con los mismos pedidos. E-9 a E-11 (sintéticos): tests de `pytest` con ficheros temporales. E-12: test de `pytest` que ejecuta dos veces y compara byte a byte. Cada test nuevo debe fallar con el código de la fase 4 (ver el plan).

Los requisitos de seguridad frente a datos desconocidos (RNF-3 de KIV-101) se aplican: ninguna regla depende de identificadores o fechas concretos.

## 3. Escenarios de aceptación con datos reales (días 08 a 10)

Importes en EUR con `fx_rates.csv` y redondeo `ROUND_HALF_UP`. Los valores «antes» son los del pipeline actual (`impact.md` §2 y §3).

### E-1 — Devolución en formato nuevo con `reason: null` (RC-1, RC-6)

`R-1033` (`2026-09-08/refunds.json`): pedido `K-10214`, `refund_amount = 10.0` EUR, `reason = null`.
`K-10214` es de `C029`, creado el 2026-09-07, total 85.12 EUR.
Resultado: `2026-09-07 / C029` pasa de `refunded_amount = 0.00` / `net_amount = 85.12` / `refunds_count = 0`
a `refunded_amount = 10.00`, `net_amount = 75.12`, `refunds_count = 1`. `R-1033` no está en `rejected.csv`.

### E-2 — Moneda USD en formato nuevo (RC-1)

`R-1037` (08): pedido `K-10131`, `refund_amount = 36.65` USD, `reason = "talla incorrecta"`. `K-10131` es de `C022`, creado el 2026-09-07, total 61.08 USD (56.19 EUR).
Resultado: `2026-09-07 / C022` pasa a `gross_amount = 56.19`, `refunded_amount = 33.72`, `net_amount = 22.47`, `refunds_count = 1`.

### E-3 — Moneda GBP en formato nuevo (RC-1)

`R-1039` (08): pedido `K-10145`, `refund_amount = 31.5` GBP. Resultado: `2026-09-04 / C018` pasa de `refunded_amount = 0.00` a `36.86`,
`gross_amount = 245.70`, `net_amount = 208.84`, `refunds_count = 1`.

### E-4 — Los dos formatos sobre un mismo pedido (RC-3)

Pedido `K-10155` (cliente `C026`, creado el 2026-09-06, total 80.00 EUR): `R-1013` (fichero del 2026-09-07, formato anterior, `amount = 70.0`) y
`R-1035` (fichero del 2026-09-09, formato nuevo, `refund_amount = 20.0`).
Resultado: `2026-09-06 / C026`: `gross_amount = 80.00`, `refunded_amount = 90.00`, `net_amount = -10.00`, `refunds_count = 2` (antes: `refunded_amount = 70.00`, `net_amount = 10.00`, `refunds_count = 1`).

### E-5 — Devolución sin pedido y anomalías visibles (RC-1, RC-10)

`R-1034` (09): pedido `K-19998`, que no existe en ninguna entrega. Resultado: `rejected.csv` contiene `refunds,R-1034,pedido no encontrado` (ya ocurre hoy; debe mantenerse).
Por E-4, `quality_report.json` pasa a tener `net_amount_not_negative_anomaly` con `failed_records = 1` (`C026 / 2026-09-06`) y
`refunded_not_exceeds_gross_per_order` con `failed_records = 2` (`K-10148`, ya conocido, y `K-10155`, 90.00 > 80.00). Ambos controles se informan, sin ocultar las filas.

### E-6 — Compatibilidad con el formato anterior (RC-2)

Las filas de los días 01 a 07 que no reciben devoluciones nuevas no cambian. Ejemplos de KIV-101 que siguen idénticos:
`C007 / 2026-09-01` (`refunded_amount = 41.51`, `net_amount = 205.15`) y `C022 / 2026-09-04` (`refunded_amount = 126.02`, `net_amount = 199.15`, `refunds_count = 3`).
Las únicas filas de los días 01 a 07 que cambian son las 12 de `impact.md` §3 (devoluciones tardías, atribuidas al día de compra): `C003 09-02`, `C005 09-03`, `C023 09-03`,
`C018 09-04`, `C006 09-05`, `C025 09-05`, `C015 09-06`, `C026 09-06`, `C001 09-07`, `C022 09-07`, `C027 09-07` y `C029 09-07`.

### E-7 — Resultado completo con los datos 01 a 10 (RC-9, RC-10)

`rejected.csv` contiene exactamente 4 filas: `R-1003` (`pedido no encontrado`), `R-1005` (`pedido cancelado`), `R-1006` (`refund_id duplicado`) y `R-1034` (`pedido no encontrado`).
Ninguna es `importe no valido`. `daily_customer_metrics.csv` tiene 164 filas, de las cuales cambian respecto a hoy exactamente 14: una por cada devolución atribuible (12 en los días 01 a 07 y 2 en los días 08 y 09).
`daily_sales.csv` y `top_customers.csv` no cambian por este ticket.

### E-8 — Devolución del día 08 sobre pedido del mismo día y del día 09 (RC-1)

`R-1041` (09): pedido `K-10161` (`C007`, creado el 2026-09-08, total 81.87 EUR), `refund_amount = 40.94`. Resultado: `2026-09-08 / C007`: `refunded_amount = 40.94`, `net_amount = 40.93`, `refunds_count = 1`.
`R-1036` (10): pedido `K-10215` (`C031`, creado el 2026-09-09, total 16.06 EUR; la fila del día suma 103.49 EUR), `refund_amount = 9.95`. Resultado: `2026-09-09 / C031`: `refunded_amount = 9.95`, `net_amount = 93.54`, `refunds_count = 1`.

### E-9 — Registro sintético sin importe y con ambos importes (RC-4, RC-5)

Datos sintéticos (los datos reales no contienen estos casos, `impact.md` §4.1), sobre un pedido válido de 100.00 EUR:

- Registro sin `amount` ni `refund_amount`, o con `refund_amount = null`: se rechaza con `refunds,<id>,importe no valido`; `refunded_amount = 0.00`, `refunds_count = 0`.
- Registro con `refund_amount = ""` o `"  "` y sin `amount`: igual.
- Registro con `amount = 70.0` y `refund_amount = 20.0`: cuenta 20.00 (RC-4).
- Registro con `amount = 30.0` y `refund_amount = null`: cuenta 30.00 (el campo nulo no está presente, RC-5).

### E-10 — `reason` y privacidad (RC-6, RC-7)

Registro con `reason` ausente, `null`, `""` y con texto libre (por ejemplo, con un nombre propio): ninguno se rechaza y los importes son los mismos.
Ningún valor de los cinco ficheros de salida contiene el texto de `reason` (el test usa un texto con un nombre propio y comprueba los valores, no el nombre de la columna `reason` de `rejected.csv`). `output/warehouse.db` (`raw_refunds.reason`) contiene el texto tal como llegó, y cadena vacía para `null`.

### E-11 — Campos desconocidos (RC-8)

Registro con un campo extra (por ejemplo, `"channel": "web"`): se procesa igual que sin él, sin error.

### E-12 — Contrato y determinismo (RC-11)

Dos ejecuciones sobre los días 01 a 10 producen ficheros idénticos byte a byte, con las mismas columnas y el mismo orden que en KIV-101.

## 4. Aclaraciones: ambigüedades y decisiones

Cada punto de `impact.md` §4 se decide aquí. Decisiones A-1 a A-11 aprobadas por la persona responsable del proyecto.

| # | Ambigüedad | Opciones | Decisión propuesta | Motivo |
| --- | --- | --- | --- | --- |
| A-1 | Registro con `amount` y `refund_amount` a la vez. El ticket habla de renombrar, no de convivencia dentro de un registro. | (a) rechazar; (b) usar `refund_amount`; (c) usar `amount`; (d) rechazar si difieren | **(b)** `refund_amount` manda (RC-4). | El ticket presenta `refund_amount` como el nombre vigente. (a) y (d) perderían una devolución con importe claro. No hay motivo `rejected.csv` para «conflicto» y crear uno cambiaría el contrato. No ocurre en los datos actuales: la decisión es defensiva. |
| A-2 | Registro sin ningún importe, o con importe `null` o vacío. | (a) contar 0; (b) rechazar con `importe no valido`; (c) añadir un motivo nuevo | **(b)** (RC-5). | Es el motivo que RF-23 ya reserva para «importe ausente o no numérico», y `rejected.csv` es la vía de informar (RNF-4). Contar 0 ocultaría el problema, que es justo lo que ha pasado hoy. |
| A-3 | `reason`: ¿se usa en alguna salida? | (a) ignorarlo; (b) conservarlo solo en `raw_refunds`; (c) añadirlo a `rejected.csv` o a las métricas | **(b)** (RC-7). | El ticket lo describe pero no pide usarlo. La capa `raw_*` conserva los campos sin tratar, así que se puede analizar después sin cambiar contratos. Es texto libre y puede contener datos personales: no debe viajar a las salidas que consume Finanzas. Añadir columnas rompería el contrato de KIV-101. |
| A-4 | `reason` a `null`, vacío o ausente. | (a) rechazar; (b) aceptar y guardar como vacío | **(b)** (RC-6). | El ticket dice que puede venir a `null`; es un dato descriptivo, no afecta al importe. `null` se guarda como cadena vacía, igual que el resto de campos en `raw_*` (`ingest.py`). |
| A-5 | ¿Detectar el formato por fichero o por registro? | (a) por fichero (según la primera clave); (b) por registro | **(b)** (RC-3). | Evita errores si un fichero mezcla los dos formatos (p. ej. un reenvío parcial) y es más simple de probar. |
| A-6 | Importes devueltos mayores que el pedido, y neto negativo (`K-10155`, `C026`). | (a) rechazar; (b) informar | **(b)** (RC-10). | Ya decidido en RF-17 de KIV-101. El cambio de formato no las crea: las hace visibles. |
| A-7 | Revisión de cifras pasadas: 12 filas de días ya entregados cambian. | (a) congelar los días entregados; (b) recalcular y avisar | **(b)**. | Es la regla de KIV-101 (atribución al día de compra, RF-11) y ya ocurría con el formato antiguo (`impact.md` §3). Se comunicará a Finanzas en la respuesta de `KIV-102.md`. |
| A-8 | ¿Basta con que `acceptance` cubra solo hasta 2026-09-07? | (a) dejarlo; (b) ampliarlo | **(b)** (RC-12). | Con el límite actual no detectaría un fallo del formato nuevo (`impact.md` §6). Las 28 comprobaciones existentes no se tocan. |
| A-9 | Tipo del importe nuevo: ¿número o texto? | (a) solo número; (b) número o texto numérico | **(b)**, con la misma conversión a `Decimal` que `amount`. | El ticket dice «número». Los importes se conservan como el texto del fichero (`parse_float=str`), así que no cambia nada y no se pierde precisión (RNF-2). |
| A-10 | Importe cero o negativo. KIV-101 solo rechaza importes **ausentes o no numéricos** (RF-23); no dice nada de cero o negativos, y el código actual los acepta (un cero suma 1 a `refunds_count`; un negativo aumenta el neto). | (a) conservar el comportamiento actual; (b) rechazar con `importe no valido` | **(a) Comportamiento sin cambios: se conserva (decisión aprobada).** No se añade ninguna regla ni requisito. | Ninguna fuente exige rechazarlos y el ticket no cambia este aspecto. Una regla nueva cambiaría el comportamiento de KIV-101 sin que nadie la haya pedido. No aparece en los datos actuales. Queda anotado como riesgo conocido: si en el futuro se quiere rechazarlos, será un cambio propio con su ticket. |
| A-11 | Moneda ausente, `refund_id` u `order_id` ausentes, texto o `NaN` como importe, `refunded_at`. | Sin decisión nueva | Se rigen por KIV-101 sin cambios: moneda ausente → `moneda no soportada`; texto o `NaN` → `importe no valido` (RF-23); `refund_id`/`order_id` ausentes → `pedido no encontrado`. `refunded_at` sigue sin usarse en ningún cálculo (la atribución es al día de compra, RF-11). | El ticket no cambia esos campos. |
## 5. Contratos que no cambian

- `docs/data-contracts/daily_sales.md`: no depende de devoluciones.
- Contrato de `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` (KIV-101 §5): sin cambios de columnas ni de motivos.
- `docs/specs/KIV-101/spec.md` (controles C-2/C-3 y la nota «con los datos actuales solo C-3 reporta») y `docs/specs/KIV-101/plan.md` (`amount` en `raw_refunds`) describen el estado hasta 2026-09-07. Con los 10 días y este cambio, C-2 y C-3 reportan 1 y 2 registros (E-5), y `raw_refunds` gana la columna `reason`. Esta especificación declara ese desfase: los documentos de KIV-101 no se reescriben.
- Documentación a actualizar en la fase de implementación: `docs/sources.md` (describir `refunds.json` en sus dos formatos), `docs/tickets/KIV-102.md` y `docs/report.md` (sección «Cambio de esquema»).
