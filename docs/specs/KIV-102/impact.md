# KIV-102 · Análisis de impacto del nuevo formato de `refunds.json`

- **Fase:** 5. Análisis previo al código: no se ha modificado `kivora/`, `sql/`, `tests/` ni `tasks.py`.
- **Estado del repositorio analizado:** commit `9351756` (entrega 2 recibida) sobre `phase-4` (`20a6816`).
- **Fuente de los hechos:** ejecuciones del pipeline actual sobre una copia de los datos, fuera del repositorio,
  y lectura de código, tests y documentos. Cada cifra indica de dónde sale.

## 1. Qué ha cambiado (ticket KIV-102 y datos)

| Aspecto | Formato anterior (días 01–07) | Formato nuevo (días 08–10) |
| --- | --- | --- |
| Importe | `amount` | `refund_amount` |
| Motivo | no existe | `reason`: texto libre o `null` |
| Resto de campos | `refund_id`, `order_id`, `refunded_at`, `currency` | igual |

Evidencia en los datos (`deliveries/delivery-2/` coincide con lo recibido en `data/inbox/2026-09-08..10`):

- 15 devoluciones nuevas en 3 ficheros. Las 15 traen exactamente las claves `currency, order_id, reason, refund_amount, refund_id, refunded_at`
  y ninguna trae `amount`.
- 1 de las 15 trae `reason: null` (`R-1033`). Las otras 14 traen texto (`talla incorrecta`, `cambio de opinión`, …).
- Monedas: 12 EUR, 2 GBP, 1 USD. No hay monedas nuevas respecto a `data/reference/fx_rates.csv`.
- En `data/inbox/` conviven los dos formatos (ticket): los ficheros 01–07 usan `amount`, los 08–10 usan `refund_amount`.
  No hay ningún fichero con ambos campos a la vez.

## 2. Qué pasa hoy con los datos nuevos (código sin tocar)

`kivora/ingest.py:14` fija `REFUND_COLUMNS = [..., "amount", ...]` y `ingest.py:32` hace
`"" if r.get(c) is None else str(r.get(c))`. Para un registro nuevo `r.get("amount")` es `None` y se guarda `""`;
`reason` se descarta sin aviso. En `kivora/metrics.py:to_eur` un importe vacío lanza `Reject("importe no valido")`.

Resultado medido (pipeline completo sobre los 10 días, `--out` fuera del repositorio):

| Medida | Solo días 01–07 | Días 01–10 (hoy) |
| --- | ---: | ---: |
| Salida del pipeline | código 0 | código 0 |
| Registros en `rejected.csv` | 3 | **18** |
| Rechazos `importe no valido` | 0 | **14** (`R-1032`, `R-1033`, `R-1035` … `R-1046`) |
| `R-1034` (pedido `K-19998` inexistente) | — | rechazada como `pedido no encontrado` (correcto, ver 4.3) |
| Filas de `daily_customer_metrics.csv` | 115 | 164 |
| Controles de calidad con anomalía | `refunded_not_exceeds_gross_per_order` | solo ese mismo (el resto, en verde) |

Conclusiones:

1. **Fallo silencioso.** El pipeline termina con código 0 y los controles de calidad siguen casi iguales: ninguno detecta que 14 de las 15 devoluciones
   nuevas se han perdido. Solo se nota en la cifra de rechazos de la salida por consola y en `rejected.csv`.
2. **Las devoluciones nuevas se ignoran en las métricas.** Las 14 devoluciones atribuibles no suman a `refunded_amount` ni a `refunds_count`.
3. **`daily_sales.csv` y `top_customers.csv` no dependen de las devoluciones** (`sql/daily_sales.sql` y `sql/top_customers.sql` no leen `raw_refunds`).
   Comprobado: con y sin el arreglo simulado de abajo, ambos ficheros son idénticos byte a byte. No se ven afectados.

## 3. Efecto esperado al soportar el formato nuevo (simulación)

Para cuantificar el efecto se creó una copia de `data/inbox/` fuera del repositorio, renombrando `refund_amount` a `amount` y quitando `reason`,
y se ejecutó el mismo pipeline. Es solo una simulación para medir; no es la solución.

| Medida | Hoy (sin soporte) | Con soporte (simulado) |
| --- | ---: | ---: |
| Registros en `rejected.csv` | 18 | 4 (`R-1003`, `R-1005`, `R-1006`, `R-1034`) |
| Filas de `daily_customer_metrics.csv` | 164 | 164 (no cambia el número de filas) |
| Filas cuyo `refunded_amount` cambia | — | **14** (una por cada devolución atribuible) |
| de ellas, de días **ya entregados a Finanzas** (01–07) | — | **12** |
| de ellas, de los días nuevos (08–09) | — | 2 (`C007 / 09-08`, `C031 / 09-09`) |
| `net_amount_not_negative_anomaly` | 0 | **1** (`C026 / 2026-09-06`: bruto 80.00, devuelto 90.00, neto −10.00) |
| `refunded_not_exceeds_gross_per_order` | 1 | **2** (la ya conocida `K-10148` y `K-10155`) |

Las devoluciones se atribuyen al día de compra del pedido (regla de KIV-101, `kivora/metrics.py`, `build`). Por eso las devoluciones del 8 al 10
modifican filas de días 02 a 09.

**Respuesta a la pregunta de Finanzas** («¿afecta a las cifras que ya os damos?»):

- Con el código actual, **sí**: se pierden 14 devoluciones y `refunded_amount` queda infraestimado y `net_amount` sobrestimado en 14 filas cliente-día (no hay ningún caso en sentido contrario).
- Al corregirlo, los importes ya entregados de 12 filas de los días 01–07 cambian, **aunque no cambien los pedidos**. No es un error: son devoluciones tardías atribuidas a su día de compra.
  Finanzas debe saber que las cifras de días pasados se revisan cuando llegan devoluciones posteriores. Esto ya ocurría con el formato antiguo: `R-1014` y `R-1015` (fichero del 2026-09-04) devuelven los pedidos `K-10001` y `K-10008`, del 2026-09-01.
- `daily_sales` y `top_customers` no cambian por este ticket.

## 4. Ambigüedades y decisiones pendientes (no se deciden aquí)

Se listan solo las que el ticket y los datos no resuelven; la decisión va en `spec.md`.

1. **Convivencia de los dos formatos.** El ticket dice que conviven, pero no dice qué hacer si un registro trae `amount` y `refund_amount` a la vez, o ninguno de los dos.
   En los datos actuales no ocurre ni una cosa ni la otra; el pipeline recibirá datos que no conocemos (`assignment.md` §3.2).
2. **Qué hacer con `reason`.** El ticket lo describe, pero no dice si alguna salida debe usarlo. El contrato de `daily_customer_metrics` (KIV-101) no lo contiene.
   Es texto libre: puede traer datos personales. Opciones: ignorarlo, conservarlo en `warehouse.db` o añadirlo a una salida.
   Añadir columnas a las salidas cambia el contrato de KIV-101. No se puede dar por pedido.
3. **`reason` a `null`, vacío o con espacios.** El ticket solo dice que puede venir a `null`. No debe provocar rechazo (es opcional); falta definir cómo se guarda.
4. **`R-1034`.** El pedido `K-19998` no existe en ningún día. Ya se rechaza como `pedido no encontrado` con el código actual (mismo comportamiento que `R-1003` en KIV-101). No es un efecto del cambio de formato.
5. **Importe devuelto superior al pedido (`K-10155`) y neto negativo (`C026`).** Se detectan con los controles C-2 y C-3 de KIV-101, que ya existían. El cambio de formato no los crea:
   los hace visibles al leer devoluciones antes perdidas. Decisión de KIV-101 (RF-17): se informa y no se oculta. No se propone cambiarla.
6. **Revisión de cifras pasadas.** Hay que decir a Finanzas, en la respuesta del ticket, que las filas de días pasados cambian (ver §3).

## 5. Archivos afectados

| Archivo | Afectación | Evidencia |
| --- | --- | --- |
| `kivora/ingest.py:14,22-35` | **Cambia.** Lee `amount`; no conoce `refund_amount` ni `reason`. | §2 |
| `sql/staging.sql:63-76` | Afectado si se añade `reason` a `raw_refunds`; las columnas se arrastran por `stg_refunds_ranked`, `stg_refunds` y `stg_refunds_dup`. | lectura del SQL |
| `sql/daily_customer_metrics.sql` (`kpi_refunds`, `kpi_rejected`) | Solo si se decide propagar `reason`. Si no, no cambia. | lectura del SQL |
| `kivora/metrics.py` | No necesita cambios si la ingesta entrega `amount` ya normalizado. Los controles se reutilizan. | §3 |
| `kivora/check.py` | No depende del nombre del campo (lee las salidas). Los datos nuevos activan C-2 y C-3, pero `check` no las convierte en error. | `check.py:37-62` |
| `kivora/acceptance.py` | **No se ve afectado, pero debe seguir verde:** limita la ejecución a `LAST_DAY = "2026-09-07"` y ya incluye la comprobación `refunded_amount`/`net_amount` de esos días. `tasks.py acceptance` pasa hoy con 28/28. | ejecución del 2026-11-09 |
| `tests/test_kiv101.py:37,86` | El helper `refund(...)` escribe `amount`. Los 16 tests actuales siguen válidos para el formato antiguo y no se tocan. Hacen falta tests nuevos para `refund_amount`, `reason` y la convivencia. | lectura de tests |
| `tests/test_pipeline.py` | Sin relación con devoluciones. | lectura de tests |
| `docs/sources.md` | **Sin documentar:** no menciona `refunds.json` en ningún formato (ni el antiguo ni el nuevo). Hay que documentar los dos. | `docs/sources.md` |
| `docs/specs/KIV-101/spec.md:48` | Dice que KIV-102 «no se aborda aquí»: sigue siendo cierto y no se modifica. | lectura |
| `docs/specs/KIV-101/spec.md` (controles C-2/C-3, E-4 y nota «con los datos actuales, solo C-3 detecta K-10148») | **Quedará desfasada sobre los 10 días:** con soporte del formato nuevo, C-2 falla (`C026`) y C-3 tiene 2 pedidos. Sigue siendo cierta para los días hasta 2026-09-07, que es lo que comprueba `acceptance`. No se reescribe (registro de la fase 4): la spec de KIV-102 lo declara. | revisión de `kivora-reviewer` |
| `docs/specs/KIV-101/plan.md:24,214` | Describe `amount` como columna de `raw_refunds`. Es un registro histórico de la fase 4: no se reescribe; la spec de KIV-102 declara el cambio. | lectura |
| `docs/data-contracts/daily_sales.md` | Sin cambios: no depende de devoluciones. | §2.3 |
| `docs/tickets/KIV-102.md` | Hay que rellenar «Notas del equipo de datos» y «Respuesta». | ticket |
| `docs/report.md` | Hay que completar la sección «Cambio de esquema». | `assignment.md` §6 |

No se tocan `data/inbox/` ni `deliveries/`. La interfaz de ejecución no cambia.

## 6. Riesgos de regresión y cómo detectarlos

| Riesgo | Cómo se detecta |
| --- | --- |
| Cobertura del formato nuevo: `acceptance` solo ejecuta hasta 2026-09-07 y no detectaría un fallo con `refund_amount`. | Tests nuevos con escenarios concretos (pedidos reales de los días 08–10) en la spec de KIV-102. |
| Romper el formato antiguo (días 01–07) al leer `refund_amount`. | Las filas de los días 01–07 solo pueden cambiar por devoluciones nuevas (los 14 casos del §3). Los 20 tests actuales y `tasks.py acceptance` (28/28) deben seguir en verde. |
| Que un registro sin ninguno de los dos campos se cuente como importe 0 en silencio. | Test nuevo: debe aparecer en `rejected.csv` con motivo. |
| Que `reason` (texto libre) acabe en una salida sin que esté pedido. | Revisión de `daily_customer_metrics.csv` y `rejected.csv` contra el contrato de KIV-101. |
| Que cambien `daily_sales.csv` o `top_customers.csv`. | Comparación byte a byte antes/después (como en §3). |

## 7. Línea base de la ejecución actual

| Comprobación | Resultado |
| --- | --- |
| `uv run python tasks.py test` | 20 passed |
| `uv run python tasks.py acceptance` | 28/28 comprobaciones superadas |
| `python -m kivora` sobre los 10 días | código 0, 164 métricas, 18 rechazados |
| `tasks.py check` | no se ejecutó: lee `output/`, que no se regeneró para no tocar la carpeta del repositorio. Se ejecutará con el código nuevo. |

## 8. Conclusión

El cambio es pequeño en código (la ingesta) pero de efecto alto en datos: sin corregirlo se pierden 14 de las 15 devoluciones nuevas **sin que ningún control lo detecte**
y con código de salida 0. Al corregirlo cambian 14 filas, 12 de ellas de días ya entregados. Quedan por decidir en `spec.md` los puntos 1, 2 y 3 del §4.
No hace falta modificar `metrics.py`, `check.py`, `acceptance.py` ni los contratos existentes.
