# Memoria de la práctica · Pipeline Kivora

**Versión:** 0.3, cierre de la fase 2 (KIV-101: especificación y plan). La 0.1 se commiteó en `efe0bcc`; esta versión incorpora la corrección de las cinco incidencias detectadas y la resolución de los tres puntos que quedaron abiertos (A-9, `stg_orders_latest` y aclaraciones de las decisiones 2 y 10).
**Estado:** solo documenta lo ocurrido hasta la fase 2. Las secciones que dependen de las fases 3 a 6 están marcadas como **PENDIENTE** y no contienen resultados ni decisiones inventados.

**Historial de referencia (fase 2):**

| Commit | Contenido |
|---|---|
| `3a438a5` | Reglas de Git en `CLAUDE.md` (incluye `Co-Authored-By: Claude Code`) |
| `788010b` | Entrega 1: 17 ficheros nuevos (4 días × `customers.csv`, `orders.csv`, `payments.csv`, `refunds.json`, más `docs/tickets/KIV-101.md`). `git status` previo solo mostraba ficheros sin seguimiento: no se modificó ningún fichero preexistente |
| `950c5e3` | `docs/specs/KIV-101/spec.md` |
| `5b25630` | `docs/specs/KIV-101/plan.md`, borrador inicial tal como lo generó Claude |
| `b7513de` | `plan.md` revisado, con la sección «Revisión del plan» |
| `efe0bcc` | `docs/report.md`, versión 0.1 |
| `f37e4ee` | `Fase 2: cerrar especificacion, plan y memoria de KIV-101`: corrección de las cinco incidencias y resolución de A-9 en `spec.md`, `plan.md` y `report.md` |
| *(commit de evidencia, ver `git log`)* | `Fase 2: incorporar evidencia de Claude Code`: `docs/sessions/fase-2-sesion-claude.md` y nota en esta memoria |

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
| 2 | Cada `order_id` cuenta una vez; versión más reciente por `updated_at`, con criterio determinista en empates | RF-6, RF-7, E-12 (sin entrada propia en «Aclaraciones», por decisión del usuario) |
| 3 | Cada `refund_id` cuenta una vez; los duplicados se informan en `rejected.csv` | RF-10, A-2, E-11 |
| 4 | Devoluciones de pedidos inexistentes: rechazadas con motivo explícito | RF-12, A-3, E-5 |
| 5 | Pedidos cancelados no son venta; sus devoluciones se rechazan | RF-8, RF-13, A-4, E-8 |
| 6 | Los pagos `captured` validan la venta pero no multiplican importe ni pedidos; se usa `total_amount` | RF-9, A-5, E-7 |
| 7 | Clientes sin país → `UNKNOWN`; no se pierden ventas | RF-15, A-6, E-2 |
| 8 | `last_purchase_date` = última compra válida hasta `metric_date` | RF-16, A-7 (con el grano vigente coincide con `metric_date` en todas las filas; ver 1.4) |
| 9 | Conversión a EUR con `fx_rates.csv`, `Decimal` y redondeo consistente (ampliada después: todo cálculo monetario en Python con `Decimal`, ver 1.4) | RF-4, RF-5, RNF-2, A-8, E-10 |
| 10 | No ocultar devoluciones que superen lo comprado; señalar la anomalía con un control de calidad | RF-17, C-2 (por cliente-día), C-3 (por pedido) (sin entrada propia en «Aclaraciones», por decisión del usuario) |

### 1.3 Plan de implementación: generación y revisión

- **Borrador:** Claude lo generó a partir de `spec.md` y `assignment.md` (8 pasos) y se commiteó sin cambios (`5b25630`).
- **Revisión:** el usuario aportó 8 observaciones; Claude las aplicó en `b7513de` (el commit inicial no se tocó). Cada una está desarrollada en `plan.md`, sección 8. La revisión 2 de cierre de fase (cinco incidencias posteriores) está en `plan.md`, sección 9, y en 1.4.

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

### 1.4 Incidencias detectadas al redactar la versión 0.1 y su resolución

Al preparar la versión 0.1 se contrastaron `spec.md` y `plan.md` con los datos reales y se detectaron cinco incidencias. El usuario decidió cómo resolverlas y las correcciones se aplicaron en `spec.md`, `plan.md` y este informe.

| # | Incidencia (verificada con los datos) | Decisión del usuario | Dónde queda |
|---|---|---|---|
| 1 | `R-1006` figuraba en los `refunds.json` de 09-04 y 09-05; está en los de **2026-09-05 y 2026-09-06** | Corregir las fechas de E-11 a las de los ficheros reales | `spec.md` E-11 (que además añade el bruto de `C028 / 2026-09-04`, 196.69) |
| 2 | C-2 se presentaba como fallida con los datos actuales: el -9.20 era el neto del pedido `K-10148` (92.00 comprados, 101.20 devueltos), no de un cliente-día. Con los datos actuales hay 118 filas cliente-día y **ninguna** con neto negativo | Corregir la afirmación y mantener C-2 para detectar casos futuros | `spec.md` §8 (C-2 pasa; solo C-3 falla con `K-10148`; C-4 también aclarado: `R-1006` se deduplica antes del cálculo), E-4; `plan.md` paso 8 y sección 5 |
| 3 | Con el grano «una fila por cliente-día con compra», `last_purchase_date = metric_date` en todas las filas | Mantener el grano; no añadir filas de días sin compras; documentar la coincidencia | `spec.md` RF-16, contrato (§5.1) y A-7 («Consecuencia reconocida»); `plan.md` paso 5 |
| 4 | El plan admitía `CAST ... AS NUMERIC` de SQLite como alternativa a `Decimal` | Todo cálculo monetario en Python con `Decimal`; no presentar `CAST AS NUMERIC` como equivalente | `spec.md` RNF-2 y §6.4; `plan.md` cabecera, pasos 2, 5 y 8, tabla de archivos (nuevo `kivora/metrics.py`), tests 13 y 14, observación 1 corregida, sección 9 |
| 5 | RF-7 y RF-8 no tenían escenario de aceptación | Añadir escenarios con datos reales | `spec.md` **E-12** (`K-10151`, `K-10060`) y **E-13** (`K-10062`); `plan.md` pasos 9 y 10 |

Cifras de los escenarios nuevos (verificadas con un cálculo sobre `data/inbox/`):

- **E-12:** `K-10151` pasa de 64.00 EUR (2026-09-04) a 58.50 EUR (`updated_at` 2026-09-05T09:12:00Z); su pago `P-30161` es de 64.00. `C010 / 2026-09-04`: 2 pedidos, bruto 258.32 (`K-10076` 199.82 + `K-10151` 58.50), devuelto 99.91, neto 158.41, 1 devolución; `C010 / 2026-09-05`: 1 pedido, 41.55. `K-10060` llega en dos días con filas idénticas: `C021 / 2026-09-02` 1 pedido, bruto 78.68, devuelto 39.34, neto 39.34; `C021` no tiene fila el 2026-09-03.
- **E-13:** `K-10062` (`C024`, 99.00 EUR) tiene dos pagos `failed`; `C024 / 2026-09-02`: 1 pedido, bruto 197.51 (solo `K-10020`).

**Tres puntos que quedaron abiertos y se resolvieron después:**

| Punto | Origen | Decisión del usuario | Dónde queda |
|---|---|---|---|
| Tabla `stg_orders_latest` | Propuesta de Claude al aplicar la decisión 4 (no pedida expresamente): crear una tabla nueva en lugar de reescribir `stg_orders` | Mantenerla y conservar `stg_orders` sin cambios, para no alterar `daily_sales` y `top_customers` (cuyos defectos, KIV-100, quedan fuera de KIV-101) | `plan.md` paso 2 y sección 9 |
| **A-9**: ¿deben aparecer en `rejected.csv` los pedidos cancelados (`K-10149`) o sin pago cobrado (`K-10062`)? El ticket habla de «un registro por cada pedido o devolución que no se ha podido usar» | Detectada por Claude al escribir E-13; recomendación de Claude: no rechazarlos | **No.** Son estados de negocio válidos, aunque no cuenten como ventas. Las devoluciones que no puedan procesarse siguen rechazándose | `spec.md` RF-2, §5.2 (motivos cerrados a cuatro), §6.5, E-8, E-13 y A-9; `plan.md` paso 6 |
| Aclaraciones de las decisiones 2 y 10 | Señalado por Claude: están como requisitos (RF-7, RF-17) pero no como entradas A-n | No hacen falta entradas nuevas en «Aclaraciones»: ya están documentadas en RF-7 y RF-17 | Sin cambios en `spec.md` |

Para eliminar contradicciones con A-9 se ajustó también `spec.md` §5.2: la lista de ejemplos de `reason` incluía `cliente no encontrado`, que contradecía RF-15 (un cliente sin país o inexistente se conserva con `UNKNOWN`), y `source` admitía `payments` y `customers`, que nunca se rechazan.

**Pendiente para la fase 4:** comprobar empíricamente que ningún importe pasa por coma flotante y fijar el caso sintético del test de redondeo `ROUND_HALF_UP`.

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
| 12 | Redacción de la memoria 0.1 | Contraste con los datos reales de `spec.md` y `plan.md` | Se detectaron cinco incidencias (sección 1.4). La memoria 0.1 se commiteó con autorización del usuario: `efe0bcc` |
| 13 | Decisiones sobre las cinco incidencias | El usuario fijó la resolución de cada una (sección 1.4) | Antes de escribir los escenarios nuevos se recalcularon con `uv run python -I` las cifras de `K-10151`, `K-10060`, `K-10062` y las filas de `C010`, `C021` y `C024`; coincidieron con los valores usados |
| 14 | Corrección de `spec.md`, `plan.md` y `report.md` | Comprobación de consistencia entre los tres documentos y con `assignment.md` | Aplicada; Claude pidió autorización antes de commitear (`CLAUDE.md`) y señaló tres puntos abiertos (A-9, `stg_orders_latest`, aclaraciones de las decisiones 2 y 10) |
| 15 | Resolución de los tres puntos abiertos | El usuario decidió cada uno (sección 1.4) y autorizó el commit | Se actualizaron los tres documentos, se eliminó la contradicción de `spec.md` §5.2 con RF-15 y se commiteó con el mensaje indicado por el usuario |

Nota verificable: tras los errores de las vueltas 4 y 7, el contexto posterior (`/context`) indica que la sesión pasó a usar el modelo `claude-sonnet-5-5`; antes, el modelo indicado era `nvidia/nemotron-3.5-super-vl:free`.

### Evidencia de sesión de la fase 2

- **Cómo se obtuvo:** con `/export docs/sessions/fase-2-sesion-claude.md` de Claude Code, sin editar el resultado (288.930 bytes, 4.874 líneas, SHA-256 `278E5C99CED6C0F0C70AA1D082E83BE7046FBB37C99A3FFC202A8255BD528E84`).
- **Qué cubre:** mensajes anteriores y posteriores al cambio de modelo de NVIDIA Nemotron a Claude Sonnet: el primer prompt de la sesión, los errores de la primera etapa, la retoma tras el 429 y el propio `/export`. El archivo no etiqueta el modelo de cada mensaje; solo su cabecera indica el modelo inicial. Los mensajes escritos por el usuario aparecen en él.
- **Límites:** no es una transcripción completa sin recortes. El terminal recorta automáticamente algunas salidas de herramientas (89 marcadores `… +N lines`, que ocultan 1.861 líneas), varios errores figuran con la redacción del terminal y no con el texto original de la herramienta, y el mensaje de vuelta del subagente no aparece.
- **Copia íntegra:** existe una copia de la transcripción JSONL de la sesión fuera del repositorio (`~/kivora-backups/`, SHA-256 `4DB513A0D31BD500650D086044EB3794FF1A3E62D21F7BC9D1345464693EB2D4`). **No se publica**: contiene metadatos internos, rutas y datos de las peticiones.
- **Privacidad:** una búsqueda por patrones (no una lectura línea a línea) no encontró credenciales ni claves. El export contiene rutas locales, el usuario de GitHub y nombres del material del curso, aceptados por el usuario.
- **Alcance temporal:** el export termina antes del commit de esta evidencia y del tag `phase-2`.

---

## 4. Trazabilidad

Estado en la fase 2: existen requisitos (`spec.md`), escenarios de aceptación (E-1 a E-13), controles de calidad (C-1 a C-5) y pasos del plan. **Todavía no existen tests ni la tarea `acceptance`**: la columna de verificación es **PENDIENTE (fase 4)** para todas las filas. Las cifras de los escenarios se calcularon sobre `data/inbox/` (7 días).

| Requisito | Escenarios | Control de calidad | Paso del plan | Test / `acceptance` |
|---|---|---|---|---|
| RF-1 columnas y grano | E-2, E-3, E-4, E-6 | C-1 | 5 | PENDIENTE |
| RF-2 `rejected.csv` (solo devoluciones no procesables y moneda no soportada; no pedidos cancelados ni sin pago, A-9) | E-5, E-8, E-11, E-13 | C-5 | 6 | PENDIENTE |
| RF-3 `quality_report.json` | — (sin escenario propio) | C-1 a C-5 | 8 | PENDIENTE |
| RF-4 EUR y dos decimales (con `Decimal` en Python, RNF-2) | E-10 | C-1 | 5, 10 (test 13) | PENDIENTE |
| RF-5 moneda no soportada | — (los datos actuales solo tienen EUR, GBP y USD, todas en la tabla) | — | 6 | PENDIENTE (requerirá dato sintético) |
| RF-6 un pedido, una vez | E-1, E-7 | — | 2, 3 | PENDIENTE |
| RF-7 última versión por `updated_at` y desempate | E-12 (también E-8) | — | 2, 10 (test 11) | PENDIENTE |
| RF-8 venta válida | E-8, E-13 | — | 5, 10 (test 12) | PENDIENTE |
| RF-9 pagos no multiplican | E-7 | — | 3, 5 | PENDIENTE |
| RF-10 `refund_id` único | E-11 | C-4 | 4, 6 | PENDIENTE |
| RF-11 atribución al día de compra | E-3, E-4, E-6 | — | 5 | PENDIENTE |
| RF-12 pedido inexistente | E-5 | C-5 | 6 | PENDIENTE |
| RF-13 pedido cancelado | E-8 | C-5 | 6 | PENDIENTE |
| RF-14 devoluciones parciales y múltiples | E-3, E-4 | C-3 | 5 | PENDIENTE |
| RF-15 país `UNKNOWN` | E-2 | — | 5 | PENDIENTE |
| RF-16 `last_purchase_date` | Sin escenario propio por diseño: con el grano vigente coincide con `metric_date` en todas las filas (se observa en todos los escenarios de métricas) | — | 5 | PENDIENTE |
| RF-17 neto y anomalías | E-4, E-6 | C-1, C-2 (hoy 0 fallos; test con datos sintéticos), C-3 (hoy 1 fallo: `K-10148`) | 5, 8, 10 (test 14) | PENDIENTE |
| RF-18 determinismo | E-9 | — | 9, 10 | PENDIENTE |
| RF-19 no escribir en la entrada | — | — | — | PENDIENTE |
| RF-20 código de salida 0 | — | C-2, C-3 (no bloquean) | 8 | PENDIENTE |

**Lagunas de cobertura que siguen abiertas:** RF-3, RF-19 y RF-20 no tienen escenario de aceptación propio; RF-5 (moneda no soportada) no aparece en los datos actuales y requerirá un dato sintético. De los 158 pedidos únicos, 156 son venta; los dos que no lo son son `K-10149` (E-8) y `K-10062` (E-13). Las lagunas de RF-7 y RF-8 se cerraron con E-12 y E-13.

**Cifras verificadas de los escenarios** (nivel cliente-día salvo indicación): `C009 / 09-01` 1 pedido, 45.90; `C017 / 09-06` 1 pedido, 23.10; `C007 / 09-01` 2 pedidos, 246.66 bruto, 41.51 devuelto, 205.15 neto; `C020 / 09-01` 72.77 / 21.83 / 50.94; `C022 / 09-04` 3 pedidos, 325.17 / 126.02 / 199.15, 3 devoluciones; `C003 / 09-01` 3 pedidos, 446.64 / 74.53 / 372.11; `C018 / 09-04` 245.70; `C006 / 09-06` 134.50; `C028 / 09-04` 196.69 / 12.00; `C010 / 09-04` 258.32 / 99.91 / 158.41; `C021 / 09-02` 78.68 / 39.34 / 39.34; `C024 / 09-02` 197.51. Por pedido: `K-10148` 92.00 EUR comprados y 101.20 EUR devueltos (`R-1004` 55.20 + `R-1009` 46.00).

---

## 5. Cambio de esquema

**PENDIENTE (fase 5).** Todavía no se ha recibido la entrega 2 ni el ticket KIV-102; no hay análisis de impacto.

---

## 6. Revisión

**PENDIENTE (fase 6).** `docs/review.md` no existe. La revisión realizada en la fase 2 es la del plan (sección 1.3 y `plan.md`, sección 8), aportada por el usuario; no sustituye a la revisión con un revisor independiente exigida en la fase 6.

---

## 7. Qué harías distinto

**PENDIENTE.** Se redactará al cerrar la práctica, con la experiencia de las fases 3 a 6.
