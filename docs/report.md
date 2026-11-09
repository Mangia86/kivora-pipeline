# Memoria de la práctica · Pipeline Kivora

**Versión:** 0.1, redactada al cierre de la fase 2 (KIV-101: especificación y plan).
**Estado:** solo documenta lo ocurrido hasta la fase 2. Las secciones que dependen de las fases 3 a 6 están marcadas como **PENDIENTE** y no contienen resultados ni decisiones inventados.

**Historial de referencia (fase 2):**

| Commit | Contenido |
|---|---|
| `3a438a5` | Reglas de Git en `CLAUDE.md` (incluye `Co-Authored-By: Claude Code`) |
| `788010b` | Entrega 1: 17 ficheros nuevos (4 días × `customers.csv`, `orders.csv`, `payments.csv`, `refunds.json`, más `docs/tickets/KIV-101.md`). `git status` previo solo mostraba ficheros sin seguimiento: no se modificó ningún fichero preexistente |
| `950c5e3` | `docs/specs/KIV-101/spec.md` |
| `5b25630` | `docs/specs/KIV-101/plan.md`, borrador inicial tal como lo generó Claude |
| `b7513de` | `plan.md` revisado, con la sección «Revisión del plan» |

El tag `phase-1` existe; `phase-2` **todavía no está creado**.

---

## 1. Decisiones con el agente

### 1.1 Quién propuso qué

- **Claude** analizó el ticket, los datos de `data/inbox/` y el pipeline, y propuso los requisitos funcionales, 8 ambigüedades (con opciones, consecuencias y recomendación), escenarios de aceptación y controles de calidad.
- **El usuario** tomó las 10 decisiones funcionales de la tabla siguiente. Ocho coinciden con la recomendación de Claude (A-1 a A-8 del análisis). Las decisiones 2 (versiones de pedido) y 10 (devolución mayor que lo comprado) y la exigencia de `Decimal` (decisión 9) las incorporó el usuario.
- Antes de redactar `spec.md`, Claude contrastó las 10 decisiones con `assignment.md`, `README.md` y `KIV-101.md` y no encontró contradicciones.
- El criterio concreto de desempate de la decisión 2 (conservar la primera aparición en orden cronológico de días) lo fijó Claude en `spec.md` (RF-7); el usuario solo pidió «un criterio determinista».

### 1.2 Las 10 decisiones funcionales aprobadas

| # | Decisión del usuario | Dónde queda en `spec.md` |
|---|---|---|
| 1 | Las devoluciones se atribuyen a la fecha de compra original para calcular el neto de ese día | RF-11, A-1 |
| 2 | Cada `order_id` cuenta una vez; versión más reciente por `updated_at`, con criterio determinista en empates | RF-6, RF-7 (sin entrada propia en «Aclaraciones») |
| 3 | Cada `refund_id` cuenta una vez; los duplicados se informan en `rejected.csv` | RF-10, A-2, E-11 |
| 4 | Devoluciones de pedidos inexistentes: rechazadas con motivo explícito | RF-12, A-3, E-5 |
| 5 | Pedidos cancelados no son venta; sus devoluciones se rechazan | RF-8, RF-13, A-4, E-8 |
| 6 | Los pagos `captured` validan la venta pero no multiplican importe ni pedidos; se usa `total_amount` | RF-9, A-5, E-7 |
| 7 | Clientes sin país → `UNKNOWN`; no se pierden ventas | RF-15, A-6, E-2 |
| 8 | `last_purchase_date` = última compra válida hasta `metric_date` | RF-16, A-7 |
| 9 | Conversión a EUR con `fx_rates.csv`, `Decimal` y redondeo consistente | RF-4, RF-5, RNF-2, A-8, E-10 |
| 10 | No ocultar devoluciones que superen lo comprado; señalar la anomalía con un control de calidad | RF-17, C-2, C-3 (sin entrada propia en «Aclaraciones») |

### 1.3 Plan de implementación: generación y revisión

- **Borrador:** Claude lo generó a partir de `spec.md` y `assignment.md` (8 pasos) y se commiteó sin cambios (`5b25630`).
- **Revisión:** el usuario aportó 8 observaciones; Claude las aplicó en `b7513de` (el commit inicial no se tocó). Cada una está desarrollada en `plan.md`, sección 8.

| # | Observación del usuario | Corrección aplicada por Claude | Justificación |
|---|---|---|---|
| 1 | Evitar `REAL` en cálculos monetarios | Importes como texto en staging; conversión y redondeo con `Decimal` (`ROUND_HALF_UP`) | `REAL` es coma flotante binaria |
| 2 | Deduplicar `order_id` por `updated_at` con desempate determinista | Versión más reciente; empate → primera aparición cronológica | Determinismo (RF-7, RF-18) |
| 3 | Conservar duplicados de `refund_id` en `rejected.csv` | `stg_refunds` deduplica para el cálculo; las repeticiones van a `rejected.csv` | El ticket pide saber qué registros no cuadran |
| 4 | Diferenciar las 3 salidas obligatorias de las heredadas | Paso 7 enumera 3 salidas nuevas + 2 heredadas (`daily_sales.csv`, `top_customers.csv`) | Evitar sustituir salidas existentes |
| 5 | Separar anomalías de calidad de errores bloqueantes | C-1, C-4, C-5 consistencia; C-2, C-3 anomalías que no bloquean (código de salida 0) | RF-20 |
| 6 | No usar cantidades fijas de los datos actuales como reglas | Cifras solo como ejemplos de verificación | Datos futuros desconocidos (RNF-3) |
| 7 | Definir sin ambigüedad qué se rechaza | 4 motivos cerrados: `pedido no encontrado`, `pedido cancelado`, `refund_id duplicado`, `moneda no soportada` | Trazabilidad (RNF-4) |
| 8 | Evitar multiplicación de importes en joins | Pagos con `EXISTS`/`IN`; devoluciones agregadas por `order_id` antes de unir | RF-9, RF-14, E-7 |

### 1.4 Puntos abiertos detectados al redactar esta memoria

Al preparar este informe se contrastaron `spec.md` y `plan.md` con los datos reales. **No se han corregido** (esta tarea solo crea `report.md`); quedan pendientes de decisión del usuario antes de cerrar la fase:

1. **`spec.md` E-11 y plan:** `R-1006` aparece en los `refunds.json` de **2026-09-05 y 2026-09-06**, no en los de 09-04 y 09-05 como dice el escenario. Verificado leyendo los ficheros y con un cálculo.
2. **`spec.md` C-2 (y `plan.md` paso 8):** el ejemplo `C022 / 2026-09-04 (net = -9.20)` mezcla el pedido `K-10148` (92.00 EUR comprados, 101.20 EUR devueltos) con el agregado cliente-día. A nivel cliente-día **ningún neto es negativo con los datos actuales** (118 filas, 0 con neto < 0; `C022 / 2026-09-04` tiene neto 199.15, como dice el propio E-4). Con los datos actuales C-2 daría `failed_records = 0` y solo C-3 detecta `K-10148`. El plan afirma que C-2 y C-3 reportan fallos: es incorrecto para C-2.
3. **`last_purchase_date` (decisión 8):** como el grano definido es «una fila por cliente-día con al menos un pedido válido», en todas las filas `last_purchase_date = metric_date`. La decisión del usuario es válida, pero no produce información distinta de `metric_date` salvo que se decida emitir filas de días sin compra.
4. **`plan.md`, observación 1:** propone «`CAST ... AS NUMERIC` en SQLite (evitando `REAL`)». Está **sin verificar** que SQLite no guarde esos valores como coma flotante; además el plan no fija dónde se calcula con `Decimal` (SQL no lo tiene). Debe decidirse y comprobarse en la fase 4.
5. **«Aclaraciones» de `spec.md`:** tiene 8 entradas (A-1 a A-8); las decisiones 2 y 10 solo aparecen como requisitos, no como aclaración.

---

## 2. Configuración del agente

**PENDIENTE (fase 3).** Aún no se han configurado permisos en `.claude/settings.json` ni mecanismos de extensión, y no existe la tabla de protecciones.

Único antecedente de la fase 2: `CLAUDE.md` incluye reglas de Git (commits pequeños y frecuentes, mensajes en español, sin `amend`/`rebase`/`push --force`, **solicitar autorización antes de commit y push**, conservar el `Co-Authored-By`, no tocar `data/inbox/` ni `deliveries/`). Es una protección de tipo instrucción; su evaluación y la comparación con permisos o hooks se hará en la fase 3.

---

## 3. Ciclo de iteración

Vueltas reales de la fase 2, en orden. El recuento y el criterio de «terminado» de la fase de implementación son **PENDIENTES (fase 4)**.

| # | Qué ocurrió | Feedback / causa | Resultado |
|---|---|---|---|
| 1 | `deliver 1` y comprobación de la entrega | Instrucción del usuario: verificar rama, árbol limpio, HEAD `3a438a5` y tag `phase-1` | 17 ficheros nuevos, sin modificaciones previas; commit `788010b` |
| 2 | Primer script de análisis con `python3` | `python3: command not found` (código 127) | Se pasó a `uv run python` |
| 3 | Análisis completo de datos | Salida de 35.6 KB demasiado larga; la lectura del fichero guardado se denegó por estar fuera del directorio de trabajo | El usuario pidió repetir con cálculos resumidos |
| 4 | Intento de análisis resumido | La herramienta Bash no pudo clasificar el comando («temporarily unavailable (timed out)») | Se repitió tras el mensaje del usuario |
| 5 | Análisis presentado al usuario | El usuario señaló que el cálculo de `C003` era inconsistente y que se mezclaban cifras por pedido con cifras por cliente-día (`C022`) | Se pidió recalcular los escenarios distinguiendo ambos niveles |
| 6 | Recálculo de escenarios | Error de comillas en el comando Python (`unexpected EOF while looking for matching '"'`, código 2) | Se reescribió el script |
| 7 | Reintento del recálculo | Error **429** (el harness informó «rate-limited»); el usuario pidió continuar | Se reejecutó con éxito |
| 8 | Verificación de importes | Una cifra calculada a mano para `C022` no coincidía con el script | Depuración con `uv run python`: `K-10070` 165.49 + `K-10079` 67.68 + `K-10148` 92.00 = 325.17 EUR (la cifra manual era errónea). Se confirmó también que `C007 / 2026-09-01` son `K-10009` y `K-10066` (el análisis previo citaba pedidos equivocados). Un intento de escribir un script en `/tmp` fue rechazado por la herramienta; se usó `uv run python` por entrada estándar |
| 9 | Redacción de `spec.md` | Decisiones del usuario + importes verificados; `git diff --check` limpio | Commit `950c5e3` |
| 10 | Plan inicial | Petición del usuario: commit «sin revisarlo ni corregirlo» | Commit `5b25630` |
| 11 | Revisión del plan | 8 observaciones del usuario; `git diff --check` detectó un espacio final en la línea 319 | Corregido antes de commitear; commit `b7513de` |
| 12 | Redacción de esta memoria | Contraste con los datos reales de `spec.md` y `plan.md` | Se verificaron y registraron los puntos abiertos de la sección 1.4 |

Nota verificable: tras los errores de las vueltas 4 y 7, el contexto posterior (`/context`) indica que la sesión pasó a usar el modelo `claude-sonnet-5-5`; antes, el modelo indicado era `nvidia/nemotron-3.5-super-vl:free`.

---

## 4. Trazabilidad

Estado en la fase 2: existen requisitos (`spec.md`), escenarios de aceptación (E-1 a E-11), controles de calidad (C-1 a C-5) y pasos del plan. **Todavía no existen tests ni la tarea `acceptance`**: la columna de verificación es **PENDIENTE (fase 4)** para todas las filas. Las cifras de los escenarios se calcularon sobre `data/inbox/` (7 días).

| Requisito | Escenarios | Control de calidad | Paso del plan | Test / `acceptance` |
|---|---|---|---|---|
| RF-1 columnas y grano | E-2, E-3, E-4, E-6 | C-1 | 5 | PENDIENTE |
| RF-2 `rejected.csv` | E-5, E-8, E-11 | C-5 | 6 | PENDIENTE |
| RF-3 `quality_report.json` | — (sin escenario propio) | C-1 a C-5 | 8 | PENDIENTE |
| RF-4 EUR y dos decimales | E-10 | C-1 | 5 | PENDIENTE |
| RF-5 moneda no soportada | — (los datos actuales solo tienen EUR, GBP y USD, todas en la tabla) | — | 6 | PENDIENTE (requerirá dato sintético) |
| RF-6 un pedido, una vez | E-1, E-7 | — | 2, 3 | PENDIENTE |
| RF-7 última versión por `updated_at` | E-8 (parcial) | — | 2 | PENDIENTE (ver laguna 1) |
| RF-8 venta válida | E-8 | — | 5 | PENDIENTE (ver laguna 2) |
| RF-9 pagos no multiplican | E-7 | — | 3, 5 | PENDIENTE |
| RF-10 `refund_id` único | E-11 | C-4 | 4, 6 | PENDIENTE |
| RF-11 atribución al día de compra | E-3, E-4, E-6 | — | 5 | PENDIENTE |
| RF-12 pedido inexistente | E-5 | C-5 | 6 | PENDIENTE |
| RF-13 pedido cancelado | E-8 | C-5 | 6 | PENDIENTE |
| RF-14 devoluciones parciales y múltiples | E-3, E-4 | C-3 | 5 | PENDIENTE |
| RF-15 país `UNKNOWN` | E-2 | — | 5 | PENDIENTE |
| RF-16 `last_purchase_date` | — | — | 5 | PENDIENTE (ver punto abierto 3) |
| RF-17 neto y anomalías | E-4, E-6 | C-1, C-2, C-3 | 5, 8 | PENDIENTE |
| RF-18 determinismo | E-9 | — | 9, 10 | PENDIENTE |
| RF-19 no escribir en la entrada | — | — | — | PENDIENTE |
| RF-20 código de salida 0 | — | C-2, C-3 (no bloquean) | 8 | PENDIENTE |

**Lagunas de cobertura detectadas (datos reales ya verificados, sin escenario en `spec.md`):**

1. **RF-7:** `K-10151` (cliente `C010`) cambia de 64.00 EUR (2026-09-04) a 58.50 EUR (`updated_at` 2026-09-05T09:12:00Z). Con la última versión, `C010 / 2026-09-04` tiene `gross_amount` = 258.32 (`K-10076` 199.82 + `K-10151` 58.50). Además, `K-10060` llega idéntico en dos días distintos (caso de empate de `updated_at`).
2. **RF-8:** de 158 pedidos únicos, 156 son venta; los dos que no lo son son `K-10149` (cancelado, cubierto por E-8) y `K-10062` (estado `confirmed`, pero sus dos pagos `P-30066` y `P-30067` son `failed`), este último sin escenario.
3. **RF-3, RF-16, RF-19, RF-20** sin escenario de aceptación propio.

**Cifras verificadas de los escenarios** (nivel cliente-día salvo indicación): `C009 / 09-01` 1 pedido, 45.90; `C017 / 09-06` 1 pedido, 23.10; `C007 / 09-01` 2 pedidos, 246.66 bruto, 41.51 devuelto, 205.15 neto; `C020 / 09-01` 72.77 / 21.83 / 50.94; `C022 / 09-04` 3 pedidos, 325.17 / 126.02 / 199.15, 3 devoluciones; `C003 / 09-01` 3 pedidos, 446.64 / 74.53 / 372.11; `C018 / 09-04` 245.70; `C006 / 09-06` 134.50; `C028 / 09-04` 196.69 / 12.00. Por pedido: `K-10148` 92.00 EUR comprados y 101.20 EUR devueltos (`R-1004` 55.20 + `R-1009` 46.00).

---

## 5. Cambio de esquema

**PENDIENTE (fase 5).** Todavía no se ha recibido la entrega 2 ni el ticket KIV-102; no hay análisis de impacto.

---

## 6. Revisión

**PENDIENTE (fase 6).** `docs/review.md` no existe. La revisión realizada en la fase 2 es la del plan (sección 1.3 y `plan.md`, sección 8), aportada por el usuario; no sustituye a la revisión con un revisor independiente exigida en la fase 6.

---

## 7. Qué harías distinto

**PENDIENTE.** Se redactará al cerrar la práctica, con la experiencia de las fases 3 a 6.
