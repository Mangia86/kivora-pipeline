# Fuentes de datos

La tienda online de Kivora deja cada día una carpeta en `data/inbox/` con el
nombre del día (`data/inbox/2026-09-01/`). Cada carpeta trae los registros
nuevos o modificados de ese día, no una foto completa.

Todas las marcas de tiempo vienen en **UTC**, en formato ISO 8601 con `Z`
(`2026-09-01T22:10:00Z`). Los importes usan punto decimal.

`data/inbox/` es lo que envía la tienda y **no se modifica nunca**: los
problemas del origen se resuelven en el pipeline.

## `orders.csv`

| Campo | Descripción |
| --- | --- |
| `order_id` | Identificador del pedido |
| `customer_id` | Cliente |
| `created_at` | Momento en que se hizo el pedido (UTC) |
| `updated_at` | Momento de la última modificación del pedido (UTC) |
| `status` | `confirmed` o `cancelled` |
| `currency` | Moneda del pedido (ISO 4217) |
| `total_amount` | Importe total, en la moneda del pedido |

Cuando un pedido cambia, la tienda lo vuelve a enviar el día del cambio, con
el mismo `order_id` y un `updated_at` posterior.

## `customers.csv`

| Campo | Descripción |
| --- | --- |
| `customer_id` | Identificador del cliente |
| `name` | Nombre |
| `country` | País (ISO 3166-1 alfa-2). Puede venir vacío |
| `signup_date` | Fecha de alta |

Trae las altas y las modificaciones del día.

## `payments.csv`

| Campo | Descripción |
| --- | --- |
| `payment_id` | Identificador del pago |
| `order_id` | Pedido al que corresponde |
| `paid_at` | Momento del intento de pago (UTC) |
| `method` | `card`, `paypal` o `bizum` |
| `status` | `captured` (cobrado) o `failed` |
| `amount` | Importe del pago, en la moneda del pedido |

Un pedido puede tener más de un pago.

## `refunds.json`

Lista JSON de devoluciones del día. Los días sin devoluciones no traen el
fichero (en los datos actuales, del 2026-09-01 al 2026-09-03). Una misma
devolución puede aparecer en más de un día con el mismo `refund_id`.

Este fichero **cambió de formato el 2026-09-08** (ticket KIV-102, aviso de
Plataforma). Los ficheros anteriores no se reenvían, así que en `data/inbox/`
**conviven los dos formatos**. Un fichero entero usa uno u otro, pero el
pipeline decide el formato registro a registro.

| Campo | Formato anterior (2026-09-04 a 2026-09-07) | Formato nuevo (desde 2026-09-08) |
| --- | --- | --- |
| `refund_id` | Identificador de la devolución | igual |
| `order_id` | Pedido al que corresponde | igual |
| `refunded_at` | Momento de la devolución (UTC) | igual |
| `amount` | Importe devuelto, en la moneda del pedido | **ya no existe** |
| `refund_amount` | no existe | Importe devuelto, en la moneda del pedido (número) |
| `currency` | Moneda (ISO 4217) | igual |
| `reason` | no existe | Motivo de la devolución, en texto libre. Puede venir a `null` |

Cómo se leen (`kivora/ingest.py`, especificación `docs/specs/KIV-102/spec.md`):

- El importe de cada registro es `refund_amount` si está informado y, si no,
  `amount`. Un campo está informado cuando existe y no es `null` ni está en
  blanco. Si vienen los dos, manda `refund_amount`. Esto no ocurre en los datos
  actuales: es una regla defensiva.
- Un registro sin ningún importe informado se rechaza en `rejected.csv` con el
  motivo `importe no valido`. No se cuenta como una devolución de importe 0.
- Los importes cero o negativos no se rechazan: se tratan como cualquier otro
  importe (comportamiento anterior, sin cambios).
- `reason` es opcional. Su valor se conserva solo en la tabla intermedia
  `raw_refunds` de `output/warehouse.db` (`null` se guarda como cadena vacía) y
  **no aparece en ninguna salida**: es texto libre y puede contener datos
  personales.
- Los campos desconocidos se ignoran.
- La conversión a euros, la atribución al día de compra del pedido y el resto de
  reglas de las devoluciones no cambian con el formato: están en
  `docs/specs/KIV-101/spec.md`.

Ejemplos reales:

```json
{"refund_id": "R-1013", "order_id": "K-10155", "refunded_at": "2026-09-07T14:30:00Z", "amount": 70.0, "currency": "EUR"}
{"refund_id": "R-1033", "order_id": "K-10214", "refunded_at": "2026-09-08T12:12:00Z", "refund_amount": 10.0, "currency": "EUR", "reason": null}
```

## `data/reference/fx_rates.csv`

Tabla fija de tipos de cambio a euros.

| Campo | Descripción |
| --- | --- |
| `currency` | Moneda (ISO 4217) |
| `rate_to_eur` | Euros por unidad de la moneda: `importe_eur = importe × rate_to_eur` |
