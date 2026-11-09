# Plan KIV-102 · Soporte del nuevo formato de `refunds.json`

- **Entrada:** `docs/specs/KIV-102/spec.md` (RC-1 a RC-13, E-1 a E-12, A-1 a A-11) e `impact.md`.
- **Orden de trabajo:** primero tests y oráculo en rojo con el código actual, después la implementación mínima, después la documentación.
- **Restricciones (CLAUDE.md):** no se modifican `data/inbox/` ni `deliveries/`; la interfaz de ejecución no cambia; commits pequeños y en español con
  `Co-Authored-By: Claude Code <noreply@anthropic.com>`; `git add` y `git commit` en órdenes separadas; sin `amend`, `rebase` ni push forzado;
  autorización previa para cada commit y push; el tag `phase-5` solo al cerrar la fase.
- **Guard:** el código solo se puede tocar cuando `impact.md`, `spec.md` y este plan estén commiteados (`kivora_guard`, regla R4).

## 1. Cambio de diseño (mínimo)

Solo cambia la ingesta. `kivora/ingest.py` decide, **por registro**, el importe efectivo (A-1, A-5) y guarda `reason` en `raw_refunds`:

- Importe presente = clave existente con valor distinto de `null` y de cadena vacía o de solo espacios (RC-5). El `0` y `"0"` cuentan como presentes (el rechazo o no de cero es la decisión A-10: comportamiento sin cambios).
- Importe efectivo = `refund_amount` si está presente; si no, `amount` si está presente; si no, cadena vacía (el pipeline ya la rechaza como `importe no valido`, RF-23).
- `raw_refunds` pasa a tener las columnas `refund_id, order_id, refunded_at, amount, currency, reason, _day`. `amount` contiene el importe efectivo.
- `reason`: texto sin tratar; `null` o ausente se guarda como cadena vacía (RC-6, RC-7).
- Campos desconocidos se ignoran (RC-8: ya ocurre, porque solo se leen las columnas conocidas).

No cambian `sql/staging.sql` (nombra sus columnas, así que `reason` no se propaga), `sql/daily_customer_metrics.sql`, `kivora/metrics.py`, `kivora/check.py` ni ningún contrato. `tasks.py` solo cambia en la cadena de ayuda de `acceptance` (ver tarea 2).
Cambia además `kivora/acceptance.py` (RC-12).

## 2. Tareas

Cada tarea indica qué archivos toca, cómo se verifica y qué commit genera. Las tareas 1 a 3 no tocan código de producción.

### Tarea 0 · Línea base (sin cambios en el repositorio)

- Guardar, fuera del repositorio (scratchpad), las salidas actuales sobre los 10 días (`--out` temporal) y sobre los días 01 a 07, para comparar después.
- **Verificación:** `uv run python tasks.py test` → 20 passed; `uv run python tasks.py acceptance` → 28/28; `uv run python -m pytest .claude/hooks -q` verde.
- Sin commit.

### Tarea 0b · Commit de este plan (antes de tocar `tests/`)

- Tras la revisión de `kivora-reviewer` (sección «Revisión del plan» al final), commit de `docs/specs/KIV-102/plan.md` con autorización previa: `git add` y `git commit` en órdenes separadas.
- Es necesario para el guard: con `plan.md` sin commitear, la regla R4 pide confirmación al tocar `tests/` o `kivora/`.
- **Commit:** `Fase 5: planificar el soporte del nuevo formato de refunds.json (KIV-102)`.

### Tarea 1 · Tests nuevos en rojo (`tests/test_kiv102.py`)

Archivo nuevo. Reutiliza los helpers de `tests/test_kiv101.py` (`run_pipeline`, `order`, `pay`, `customer`, `Result`) importándolos, sin modificar ese archivo. Los tests con `refund_amount` usan un helper local `refund_v2(...)`. Cada test indica si debe fallar con el código actual (**ROJO**) o proteger comportamiento que ya existe (**GUARDA**: pasa antes y después, y falla si se rompe la regla).

| Test | RC / escenario | Qué comprueba | Antes del código |
| --- | --- | --- | --- |
| `test_refund_amount_is_counted` | RC-1 / E-1 | Pedido de 100.00 EUR con una devolución `refund_amount = 30.0`: `refunded_amount = 30.00`, `net_amount = 70.00`, `refunds_count = 1`, sin rechazo | ROJO (hoy: `importe no valido`) |
| `test_refund_amount_converts_currency` | RC-1 / E-2, E-3 | Devolución en USD (36.65 → 33.72 EUR) y en GBP (31.5 → 36.86 EUR) con los tipos del test | ROJO |
| `test_both_formats_on_same_order` | RC-3 / E-4 | Dos devoluciones del mismo pedido en días distintos, una con `amount` y otra con `refund_amount`: se acumulan; `refunds_count = 2` | ROJO |
| `test_formats_mixed_in_same_file` | RC-3 | Un mismo `refunds.json` con un registro de cada formato: se cuentan los dos | ROJO |
| `test_refund_amount_wins_when_both_present` | RC-4 / E-9 | `amount = 70.0` y `refund_amount = 20.0`: cuenta 20.00 | ROJO |
| `test_null_or_blank_refund_amount_falls_back_to_amount` | RC-5 / E-9 | `refund_amount = null`, `""` o `"  "` con `amount = 30.0`: cuenta 30.00. Protege contra una implementación que prefiera `refund_amount` aunque sea nulo | GUARDA (pasa hoy porque el código solo lee `amount`) |
| `test_refund_amount_used_when_amount_is_blank` | RC-5 / E-9 | `amount = ""` o `null` con `refund_amount = 20.0`: cuenta 20.00 | ROJO |
| `test_record_without_any_amount_is_rejected` | RC-5 / E-9 | Sin ningún importe, o con `refund_amount = null`/`""` y sin `amount`: `rejected.csv` contiene `refunds,<id>,importe no valido` y no suma | GUARDA |
| `test_reason_null_blank_absent_or_text_is_accepted` | RC-6 / E-10 | `reason` ausente, `null`, `""` y con texto: mismos importes, ningún rechazo | ROJO indirecto (con `refund_amount` falla hoy por `importe no valido`, no por `reason`; la parte con `amount` es GUARDA) |
| `test_reason_is_kept_only_in_raw_refunds` | RC-7 / E-10 | `raw_refunds.reason` existe en `warehouse.db` con el texto, y `""` para `null`; el texto (con un nombre propio) no aparece en ningún valor de los cinco ficheros de salida | ROJO (hoy no existe la columna) |
| `test_unknown_fields_are_ignored` | RC-8 / E-11 | Registro con `"channel": "web"`: se procesa igual | GUARDA |
| `test_old_format_unchanged` | RC-2 / E-6 | Escenario del formato anterior con cifras fijas: igual que antes | GUARDA |
| `test_new_refunds_do_not_duplicate_rows` | RC-1, RC-10 | Con varios pagos `captured` y tres devoluciones nuevas sobre el mismo pedido, la fila cliente-día es única, C-6 pasa **y** `refunded_amount`/`refunds_count` valen lo esperado (el rojo viene de estas dos últimas aserciones; la unicidad y C-6 protegen la ausencia de duplicidades tras los joins) | ROJO |
| `test_quality_controls_see_new_format` | RC-10 / E-5 | Devolución de 90 sobre un pedido de 80: C-2 y C-3 informan `failed_records = 1` y el neto es −10.00 (no se oculta) | ROJO |
| `test_output_is_deterministic_with_both_formats` | RC-11 / E-12 | Dos ejecuciones con los dos formatos: los cinco ficheros son idénticos byte a byte, con las mismas columnas y con las cifras esperadas | La parte de determinismo es GUARDA (hoy el rechazo también es determinista); el test falla hoy solo por las cifras esperadas (RC-1). RC-11 se verifica además con la comparación con la línea base de la tarea 3 |
| `test_real_data_days_08_to_10` | RC-1, RC-9, E-1 a E-8 | Ejecuta el pipeline sobre `data/inbox/` (solo lectura: el pipeline nunca escribe en `--inbox`) con `--out` en `tmp_path` y comprueba las cifras reales de E-1 a E-8, los 4 rechazos exactos, 164 filas y que `daily_sales.csv`/`top_customers.csv` no dependen de las devoluciones | ROJO |

- **ROJO y GUARDA.** La spec (§2) dice que cada test nuevo debe fallar con el código de la fase 4. Se interpreta así: cada **cambio** de la spec (RC-1, RC-3, RC-4, RC-5 en la parte nueva, RC-6, RC-7, RC-10) tiene al menos un test ROJO, que es lo que pide `assignment.md` («tests que fallen con el código anterior y pasen con el nuevo»). Los GUARDA son pruebas de regresión explícitas (RC-2, RC-5 sin importe, RC-8, determinismo): pasan antes y después y fallarían si se rompiera la regla. Irán en una sección aparte del archivo y se citarán como regresión, no como prueba del cambio.
- **Verificación de la tarea:** `uv run python -m pytest tests/test_kiv102.py -q` con el código actual: deben fallar exactamente los marcados ROJO y pasar los GUARDA. Se guarda la salida como evidencia (se citará en `docs/report.md`). Si un test ROJO pasa, es un test que no sirve y se corrige.
- **Regresión:** `uv run python tasks.py test` sigue pasando los 20 tests anteriores (los nuevos fallan a propósito).
- **Commit:** `Fase 5: añadir tests de KIV-102 (en rojo con el código actual)`.

### Tarea 2 · Oráculo `acceptance` ampliado (en rojo) — `kivora/acceptance.py`

- Conservar la primera pasada tal cual (días hasta `LAST_DAY = "2026-09-07"`, las 28 comprobaciones) para que sigan siendo comparables con KIV-101.
- Añadir una segunda pasada sobre **todos** los días de `data/inbox/` (copiados a otro directorio temporal, sin escribir en `data/inbox/`; el pipeline se ejecuta dos veces como en la primera) con una función `scenarios_kiv102(...)` que comprueba E-1 a E-8 con valores esperados fijos: `rejected.csv` exacto (4 filas), 164 filas, **las 14 filas cambiadas** con sus valores concretos (`refunded_amount`, `net_amount`, `refunds_count`), `R-1033` (`reason = null`) ausente de `rejected.csv`, `C026` con neto −10.00, controles C-2 = 1 y C-3 = 2, y determinismo byte a byte.
- Se instancia un `Oracle` por pasada y se imprimen **dos resúmenes** («28/28» de KIV-101 y «n/n» de KIV-102), para que el criterio de las 28 comprobaciones siga siendo observable (RC-12).
- Código de salida 0 solo si pasan las dos pasadas. Se actualiza la docstring y la descripción de `tasks.py acceptance` en el mismo commit; `tasks.py` solo cambia en la cadena de ayuda de la función `acceptance` (no cambia la interfaz).
- **Verificación:** con el código de ingesta actual, `uv run python tasks.py acceptance` imprime las 28 de KIV-101 en OK y las nuevas en FAIL, y termina con código 1 (rojo esperado).
- **Commit:** `Fase 5: ampliar acceptance con los escenarios de KIV-102 (en rojo)`.

### Tarea 3 · Implementación mínima — `kivora/ingest.py`

- Añadir `reason` a las columnas de `raw_refunds` y una función auxiliar `_refund_amount(record)` con la regla de §1 (por registro). `REFUND_COLUMNS` pasa a `["refund_id", "order_id", "refunded_at", "amount", "currency", "reason"]`, y `_load_refunds` rellena `amount` con el importe efectivo y `reason` con el texto o cadena vacía.
- Se mantienen `parse_float=str` y `parse_int=str` (importes sin binarios flotantes, RNF-2) y la comprobación de lista JSON.
- No se toca ningún otro archivo de `kivora/` ni `sql/`.
- **Verificación:**
  1. `uv run python -m pytest tests/test_kiv102.py -q` → todos en verde.
  2. `uv run python tasks.py test` → los 20 anteriores más los nuevos, código 0.
  3. `uv run python tasks.py acceptance` → 28/28 de KIV-101 y todas las nuevas, código 0.
  4. `uv run python tasks.py run` y `uv run python tasks.py check` → código 0. `quality_report.json` con C-2 = 1 y C-3 = 2 (anomalías informadas, código 0).
  5. Comparación con la línea base de la tarea 0 (RC-2, RC-11): ejecutando solo los días 01 a 07, la salida es **idéntica** a la anterior (las devoluciones nuevas están en los ficheros de los días 08 a 10); ejecutando los 10 días, cambian exactamente 14 filas de `daily_customer_metrics.csv` (12 con fecha ≤ 2026-09-07, las de E-6, y 2 con fecha 08 y 09); `daily_sales.csv` y `top_customers.csv` son idénticos; dos ejecuciones dan ficheros idénticos.
  6. `git diff --stat` solo muestra `kivora/ingest.py`; `git status` no muestra `data/inbox/` ni `deliveries/` (RC-13).
- **Commit:** `Fase 5: leer refund_amount y reason en la ingesta de devoluciones (KIV-102)`.

### Tarea 4 · Documentación de las fuentes — `docs/sources.md`

- Añadir la sección de `refunds.json` (hoy no existe) con los dos formatos: tabla de campos, desde cuándo rige el nuevo (2026-09-08), que conviven en `data/inbox/`, que `reason` puede ser `null`, y las reglas de la spec (A-1, A-2, A-3, A-10).
- **Verificación:** cada campo y regla citado se comprueba contra `ingest.py` y la spec; los nombres de campos coinciden con `data/inbox/` (comando `grep` sobre los ficheros de los días 07 y 08).
- **Commit:** `Fase 5: documentar los dos formatos de refunds.json en sources.md`.

### Tarea 5 · Respuesta al ticket — `docs/tickets/KIV-102.md`

- Rellenar «Notas del equipo de datos» (decisiones A-1 a A-11 resumidas) y «Respuesta» en lenguaje de negocio para Plataforma y Finanzas: qué ha cambiado, que no se perdían avisos pero sí devoluciones (14 de 15), que al corregirlo cambian 14 filas, 12 de días ya entregados, y por qué (devoluciones atribuidas al día de compra); qué anomalías nuevas se ven (`C026` el 2026-09-06, `K-10155`); que `daily_sales` y `top_customers` no cambian; y que `reason` no se publica.
- No se inventa ninguna cifra: todas salen de `impact.md`, la spec y la ejecución de la tarea 3.
- **Verificación:** cada cifra de la respuesta se contrasta con la salida real de `uv run python tasks.py run`.
- **Commit:** `Fase 5: responder a Plataforma y Finanzas en KIV-102`.

### Tarea 6 · Memoria — `docs/report.md`, sección 5

- Sustituir el «PENDIENTE (fase 5)» de la sección 5 «Cambio de esquema»: cómo se analizó el impacto antes del código (orden de commits), qué reveló (fallo silencioso: código de salida 0 y ningún control lo detecta), cómo se revisó con `kivora-reviewer`, qué se decidió y qué se aprendió, con una tabla de trazabilidad RC → escenario → test → comprobación de `acceptance`.
- Se actualiza también la línea «Estado» del encabezado (hoy dice que documenta hasta la fase 4). No se modifican otras secciones (la 6 y la 7 siguen pendientes para la fase 6).
- **Verificación:** hashes de commit citados comprobados con `git log`; cifras iguales a las de `impact.md`.
- **Commit:** `Fase 5: documentar el cambio de esquema en la memoria`.

### Tarea 7 · Cierre de la fase

- `uv run python tasks.py test`, `uv run python tasks.py acceptance` y `uv run python tasks.py check` en verde; `uv run python -m pytest .claude/hooks -q` en verde.
- `git log --oneline --name-status` desde `phase-4`: entrega → impacto → spec → plan → tests → acceptance → ingest → docs; ningún commit de código antes de `plan.md`.
- Árbol limpio y sincronizado con `origin/master` tras el push autorizado.
- **Tag `phase-5`** sobre el último commit de la fase, solo con autorización. Sin `amend`, sin `rebase`, sin push forzado.

## 3. Archivos afectados

| Archivo | Acción | Tarea |
| --- | --- | --- |
| `tests/test_kiv102.py` | Crear | 1 |
| `kivora/acceptance.py` | Modificar (segunda pasada) | 2 |
| `tasks.py` | Solo la cadena de ayuda de `acceptance` | 2 |
| `kivora/ingest.py` | Modificar | 3 |
| `docs/sources.md` | Modificar | 4 |
| `docs/tickets/KIV-102.md` | Rellenar | 5 |
| `docs/report.md` | Modificar la sección 5 y la línea «Estado» | 6 |
| `sql/*.sql`, `kivora/metrics.py`, `kivora/check.py`, `tests/test_kiv101.py`, `tests/test_pipeline.py` | **No se tocan** | — |
| `data/inbox/`, `deliveries/` | **No se tocan** (RC-13) | — |

## 4. Trazabilidad requisito → verificación

| Requisito | Escenario | Test (`tests/test_kiv102.py`) | `acceptance` (segunda pasada) |
| --- | --- | --- | --- |
| RC-1 | E-1, E-2, E-3, E-5, E-8 | `test_refund_amount_is_counted`, `test_refund_amount_converts_currency`, `test_real_data_days_08_to_10` | E-1 a E-3, E-5, E-8 |
| RC-2 | E-6 | `test_old_format_unchanged`, y los 20 tests anteriores | 28 comprobaciones de la primera pasada; filas de los días 01 a 07 |
| RC-3 | E-4 | `test_both_formats_on_same_order`, `test_formats_mixed_in_same_file` | E-4 (`C026`) |
| RC-4 | E-9 | `test_refund_amount_wins_when_both_present` | — (sintético) |
| RC-5 | E-9 | `test_null_or_blank_refund_amount_falls_back_to_amount`, `test_record_without_any_amount_is_rejected` | — (sintético) |
| RC-6 | E-1, E-10 | `test_reason_null_blank_absent_or_text_is_accepted` | E-1 (`R-1033`, `reason = null`) |
| RC-7 | E-10 | `test_reason_is_kept_only_in_raw_refunds` | — |
| RC-8 | E-11 | `test_unknown_fields_are_ignored` | — (sintético) |
| RC-9 | E-7 | `test_real_data_days_08_to_10` | E-7 (4 rechazos, ninguno `importe no valido`) |
| RC-10 | E-5, E-7 | `test_quality_controls_see_new_format`, `test_new_refunds_do_not_duplicate_rows` | E-5 (C-2 = 1, C-3 = 2) |
| RC-11 | E-12 | `test_output_is_deterministic_with_both_formats` | determinismo de la segunda pasada |
| RC-12 | — | — | `tasks.py acceptance` con código 0 |
| RC-13 | — | `git status` / `git diff` en la tarea 3 | — |

## 5. Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Que un test «rojo» pase con el código actual y no sirva | La tarea 1 exige ejecutarlos antes del código y comparar con la tabla ROJO/GUARDA. |
| Cambiar cifras de KIV-101 | Comparación con la línea base (tarea 3, punto 5) y primera pasada de `acceptance` intacta. |
| Que `reason` (texto libre) llegue a una salida | Test con texto con un nombre propio sobre los cinco ficheros (RC-7). |
| Que `acceptance` quede atado a cifras de los datos actuales | Son valores esperados del oráculo; el pipeline no los contiene (como en KIV-101). Los datos desconocidos se cubren con tests sintéticos. |
| Que el guard bloquee una orden legítima | Se usa `Edit` y órdenes separadas; si hay bloqueo, se explica y se pide decisión. No se esquiva. |

## 6. Revisión del plan

Revisado con `kivora-reviewer` (solo lectura). Ejecutó los tests propuestos con el código actual para comprobar qué falla y qué pasa. No halló problemas graves; las cifras citadas y la cobertura de RC-1 a RC-13 son correctas.

| # | Observación del revisor | Cambio en el plan |
| --- | --- | --- |
| 1 | `test_null_or_blank_refund_amount_falls_back_to_amount` pasa con el código actual (solo lee `amount`): no es ROJO | Reetiquetado como GUARDA y añadido `test_refund_amount_used_when_amount_is_blank` (ROJO) |
| 2 | `test_new_refunds_do_not_duplicate_rows` pasaba hoy con solo comprobar unicidad y C-6 | Añadidas aserciones de `refunded_amount` y `refunds_count`, de donde viene el rojo |
| 3 | `test_output_is_deterministic_with_both_formats` no es ROJO por el determinismo (el rechazo también es determinista) | Aclarado: el determinismo es GUARDA y el rojo viene de las cifras; RC-11 se verifica además con la línea base |
| 4 | El rojo de `test_reason_null_…` es indirecto | Anotado en la tabla |
| 5 | La spec dice «cada test nuevo debe fallar»; el plan incluye GUARDA | Explicado en la tarea 1 (ROJO por cada cambio, GUARDA como regresión en sección aparte) |
| 6 | «Sobre los días 01 a 07 solo difieren 12 filas» era incorrecto: con solo 01 a 07 la salida es idéntica | Reescrito el punto 5 de la tarea 3 |
| 7 | Contradicción sobre `tasks.py` | Corregida en §1 |
| 8 | Faltaba el commit de `plan.md` antes de tocar `tests/` (regla R4 del guard) | Añadida la tarea 0b |
| 10 | La salida de `acceptance` mezclaría las dos pasadas | Un `Oracle` por pasada y dos resúmenes |
| 11, 13 | El oráculo debe listar las 14 filas con valores y comprobar que `R-1033` no se rechaza | Añadido en la tarea 2 |
| 12 | Copia innecesaria de `data/inbox/` en el test | Eliminada |
| 15 | La línea «Estado» de `report.md` | Incluida en la tarea 6 |
| 16 | El `0` debe contar como importe presente | Anotado en §1 |

Decisión (aprobada por la persona responsable): la spec (§2) dice «cada test nuevo debe fallar con el código de la fase 4». El plan lo interpreta como «cada cambio tiene un test rojo»; los tests GUARDA protegen el comportamiento existente. No se modifica `spec.md` por esta distinción.
