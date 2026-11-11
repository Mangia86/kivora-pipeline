# Memoria de la práctica · Pipeline Kivora

**Versión:** 1.0, fase 6 (cierre del proyecto), sobre la 0.5 de la fase 4; la sección 5 se añadió en la fase 5. La 0.1 se commiteó en `efe0bcc`, la 0.3 en `f37e4ee`, la 0.4 en `dcc4bbb` y la 0.5 en `b5aa5d2`; la 1.0 se commitea en la fase 6 (ver `git log`).
**Estado:** documenta el proyecto completo, de la fase 1 a la 6, con las siete secciones del apartado 6 del enunciado. Solo falta cerrar con el tag `phase-6` y el push. Cada cifra remite a una ejecución, a un commit o a un documento del repositorio.

**Historial de referencia (fases 2 a 6):**

| Commit | Contenido |
|---|---|
| `3a438a5` | Reglas de Git en `CLAUDE.md` (incluye `Co-Authored-By: Claude Code`) |
| `788010b` | Entrega 1: 17 ficheros nuevos (4 días × `customers.csv`, `orders.csv`, `payments.csv`, `refunds.json`, más `docs/tickets/KIV-101.md`). `git status` previo solo mostraba ficheros sin seguimiento: no se modificó ningún fichero preexistente |
| `950c5e3` | `docs/specs/KIV-101/spec.md` |
| `5b25630` | `docs/specs/KIV-101/plan.md`, borrador inicial tal como lo generó Claude |
| `b7513de` | `plan.md` revisado, con la sección «Revisión del plan» |
| `efe0bcc` | `docs/report.md`, versión 0.1 |
| `f37e4ee` | `Fase 2: cerrar especificacion, plan y memoria de KIV-101`: corrección de las cinco incidencias y resolución de A-9 en `spec.md`, `plan.md` y `report.md` |
| `ad71b5a` | `Fase 2: incorporar evidencia de Claude Code`: `docs/sessions/fase-2-sesion-claude.md` y nota en esta memoria (tag `phase-2`) |
| `dcc4bbb` | Fase 3: permisos, hook `kivora_guard` y subagente `kivora-reviewer` (tag `phase-3`) |
| `642e773` | Fase 4: `spec.md` y `plan.md` actualizados **antes** del código (RF-21 a RF-23, A-10, A-11, E-14, E-15, C-6, revisión 3) |
| `a77d5f4` | Fase 4: `daily_customer_metrics`, `rejected.csv` y `quality_report.json` (ingest, staging, SQL y `kivora/metrics.py`) |
| `d1a0b6e` | Fase 4: 16 tests de KIV-101 |
| `2b87363` | Fase 4: tarea `acceptance` y ampliación de `check` |
| `b5aa5d2` | Fase 4: respuesta a Finanzas en `docs/tickets/KIV-101.md` y esta memoria (v0.5) |
| `37f73ae` | Fase 4: RF-23 aprobado por el usuario en `spec.md`, `plan.md` y esta memoria |
| `20a6816` | Fase 4: sesión exportada de Claude Code, `docs/sessions/fase-4-sesion-claude.md` (tag `phase-4`) |
| `9351756` | Fase 5: entrega 2 (13 ficheros: 3 días × 4 ficheros y `docs/tickets/KIV-102.md`), en un commit propio |
| `677fc96` | Fase 5: `docs/specs/KIV-102/impact.md`, **antes** de cualquier cambio de código |
| `4642b3b`, `a644c23` | Fase 5: `spec.md` y `plan.md` de KIV-102 (el plan con su «Revisión del plan») |
| `ce57809`, `3f3cdbe` | Fase 5: 31 tests de KIV-102 (21 en rojo con el código de la fase 4) y `acceptance` ampliado (en rojo) |
| `c978007` | Fase 5: `kivora/ingest.py` lee los dos formatos de `refunds.json` (único cambio de código de producción de la fase) |
| `da786bf`, `b7b7124`, `73eebb6` | Fase 5: `docs/sources.md`, respuesta en `docs/tickets/KIV-102.md` y sección 5 de esta memoria |
| `23628be` | Fase 5: sesión exportada, `docs/sessions/fase-5-sesion-claude.md` (tag `phase-5`) |
| `6c6a4e2` | Fase 6: `docs/review.md`, revisión final con `kivora-reviewer` |
| `85a49b2`, `1a4d610` | Fase 6: `README.md` y `CLAUDE.md` actualizados |
| `ac49701` | Fase 6: la sesión de la fase 1 pasa a `docs/sessions/` (`git mv`, renombrado al 100 %) |
| *(commit de esta memoria, ver `git log`)* | Fase 6: secciones 3, 6 y 7 completas, referencias obsoletas corregidas e historial actualizado |

**Tags** (de `phase-2` a `phase-5` anotados; `phase-1` es ligero; todos publicados en `origin`): `phase-1` → `4d88adb`, `phase-2` → `ad71b5a`, `phase-3` → `dcc4bbb`, `phase-4` → `20a6816`, `phase-5` → `23628be`. `phase-6` se crea al cerrar la fase.

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

**Resuelto en la fase 4:** el caso sintético del redondeo `ROUND_HALF_UP` es el test `net_amount_with_currency_conversion_and_half_up_rounding` (medio céntimo exacto: `0.125` da `0.13`; un `float` daría `0.12`), y la mutación a `float` o a `ROUND_HALF_EVEN` hace fallar los tests (sección 3, vuelta 4, y `docs/review.md`, sección 3).

### 1.5 Decisiones de la fase 4 (implementación de KIV-101)

| # | Decisión | Quién | Dónde queda |
|---|---|---|---|
| 1 | `metric_date` en `Europe/Madrid`, coherente con el contrato de `daily_sales`. `daily_sales.sql` **no se modifica** y sigue en UTC: la diferencia es una limitación conocida | Propuesta de Claude tras medir el impacto (6 de 156 ventas cambian de día); decisión del usuario | `spec.md` RF-21, A-10, E-14; `plan.md` paso 5; respuesta a Finanzas |
| 2 | Última versión disponible de cada cliente; país vacío → `UNKNOWN` sin rellenar con versiones anteriores | Claude propuso; decisión del usuario | `spec.md` RF-22, A-11, E-15; `plan.md` paso 2b |
| 3 | Control C-6 (conciliación de ventas) y ampliación de `check.py` | Claude propuso; decisión del usuario | `spec.md` C-6; `plan.md` pasos 8 y 11 |
| 4 | Primero un commit solo de documentación (`spec.md` y `plan.md`) y después el código | Decisión del usuario | Commit `642e773`, anterior a todo el código |
| 5 | Defensa ante datos defectuosos (RF-23): devolución sobre un pedido sin pago cobrado, importes o fechas ilegibles se rechazan con motivo explícito | Propuesta de Claude, a partir de un caso que señaló el revisor independiente (hallazgos 8 y 15): evita que el pipeline falle con datos desconocidos. **Aprobada por el usuario**, que confirmó mantenerla en la especificación y en la implementación | `spec.md` RF-23 y §5.2 (siete motivos); `plan.md` paso 6 |

### 1.6 Decisiones de las fases 5 y 6

- **Fase 5 (KIV-102):** las decisiones A-1 a A-11 del nuevo formato de `refunds.json`, con quién propuso cada una y cuál fue el resultado, están en la sección 5.2. La decisión A-10 (rechazar importes cero o negativos) la propuso el agente y **no se autorizó**: KIV-101 no lo exige y se conservó el comportamiento anterior.
- **Fase 6 (revisión final):** las decisiones sobre los nueve hallazgos de `kivora-reviewer` están en `docs/review.md` y se resumen en la sección 6. Las principales, del usuario: **no modificar** `daily_sales` y `top_customers` (H1) ni la robustez ante entradas malformadas (H6), documentando ambos riesgos; no reescribir el historial por los commits antiguos sin `Co-Authored-By` (H2); conservar las cifras históricas de la respuesta de KIV-101 (H9); y no añadir `*.jsonl` a `.gitignore` (el hook ya bloquea su commit).

Decisiones de diseño derivadas: la fecha de Madrid y toda la aritmética monetaria se calculan en Python (`kivora/metrics.py`); SQL solo selecciona; `stg_orders` y `stg_customers` heredadas no se tocan; `acceptance` trabaja sobre las entregas hasta 2026-09-07 (copiadas a una carpeta temporal) para que las entregas posteriores no muevan las cifras esperadas.

---

## 2. Configuración del agente

**Estado:** implementada en la fase 3 y verificada; cerrada con el tag `phase-3` (`dcc4bbb`). Desde entonces `.claude/` no ha cambiado (`git log phase-3..HEAD -- .claude` no devuelve ningún commit). Antes de la fase 3 no existía `.claude/`, el `settings.json` de usuario solo tenía `theme` y `model`, y las reglas de `CLAUDE.md` (solo instrucciones) las repetías tú en casi cada prompt: 18 de 20 prompts de la sesión de la fase 2 repiten «no commit/push», 16 «no modifiques código/datos», 16 «no crees tags» y 3 «no ejecutes `deliver 2`».

### 2.1 Qué se ha configurado

| Fichero | Qué es |
|---|---|
| `.claude/settings.json` | Permisos (allow / ask / deny) y registro del hook |
| `.claude/hooks/kivora_guard.py` | **Mecanismo propio 1:** hook `PreToolUse` con las reglas R1 a R6 |
| `.claude/hooks/test_kivora_guard.py` | Pruebas del hook (pytest) |
| `.claude/agents/kivora-reviewer.md` | **Mecanismo propio 2:** subagente revisor de solo lectura |
| `CLAUDE.md` | Sección «Protecciones del agente (fase 3)» (instrucciones) |

No se usa nada instalado por OpenSpec. Permisos, para Bash y para PowerShell (esta máquina tiene las dos herramientas):

- **allow:** `git status/diff/log/show/ls-files/rev-parse`, `git add`, `tasks.py test/check/run/setup`, `pytest`, `python -m kivora`.
- **ask:** `git commit`, `git push`, `git tag -a`/`phase-*`, `tasks.py deliver`, y editar `.claude/**` y `CLAUDE.md`.
- **deny:** push forzado o a `upstream`, `commit --amend`, `rebase`, `reset --hard`, borrar o mover tags, editar `data/inbox/**`, `deliveries/**` y `.env`.

### 2.2 Tabla de protecciones

| Riesgo | Mecanismo | Tipo | Por qué ese tipo y no otro |
|---|---|---|---|
| Modificar `data/inbox/` o `deliveries/` (−1 punto) | deny `Edit(/data/inbox/**)` + R1 + comprobación del índice en R3 | permiso + hook | El permiso cubre Edit/Write y redirecciones, pero no `rm`, `Set-Content` ni scripts Python: lo cubre R1, que analiza las sentencias de Bash y PowerShell. R3 es la red de seguridad al commitear. Un aislamiento de SO (ficheros de solo lectura) rompería `tasks.py deliver` |
| Reescribir el historial, push forzado, push a `upstream`, borrar tags | deny + R2 | permiso + hook | Las reglas simples son declarativas; el hook entiende `git -C`, las dos shells y el remoto de destino |
| Commit, push o tag sin tu autorización | `ask` | permiso | Es una decisión humana, no un bloqueo automático: es el «solicita autorización» de `CLAUDE.md` hecho real |
| Commit sin `Co-Authored-By`, con `-a`, con `.jsonl`/`.env`/`output/`, entregas alteradas o espacios sobrantes | R3 | hook | Exige inspeccionar el mensaje y el índice; un permiso no puede |
| Código antes de especificar, sin plan revisado o sin impacto previo (puntúa en el historial) | R4 | hook | Depende del estado de Git (fase por tags y artefactos ya commiteados); solo un script lo evalúa |
| `deliver N` fuera de su fase | `ask` + R5 | permiso + hook | `tasks.py` solo exige tener el ticket 1, no la fase |
| `settings.json` inválido: sin hooks ni permisos, en silencio (verificado) | R6 + `claude doctor` en las pruebas | hook + prueba | El hook no puede protegerse de un fichero que no se carga: se impide escribirlo inválido y se valida |
| Que el agente modifique sus propias guardas | `ask` en `.claude/**` y `CLAUDE.md`; R6 por shell | permiso | Es una decisión humana |
| Cifras de spec, plan o informe que no cuadran con los datos (5 incidencias en la fase 2) | subagente `kivora-reviewer` | subagente | Verificar exige un contexto independiente y no determinista; no es un hook |
| Transcripciones de sesión en el repositorio (rutas, email, metadatos) | R3 (`*.jsonl`) + `.gitignore` | hook | El `/export` sí se versiona; el JSONL crudo no |
| Prohibiciones repetidas en cada prompt | `CLAUDE.md` | instrucción | Explica el porqué, pero no basta sola: las filas anteriores las hacen deterministas |

### 2.3 Mecanismos de extensión propios

**Hook `kivora_guard`.**

- *Problema que resuelve:* las reglas que más repetías (datos de entrada, historial, commits, orden de fases) dependían de que el agente las recordara.
- *Por qué un hook:* es determinista, lo dispara el sistema (no el modelo) y se puede probar sin modelo.
- *Qué aporta frente a pedírselo al agente:*
  - no depende de recordar ni del modelo: la sesión empezó con Nemotron y siguió con Sonnet, y las reglas valen para ambos;
  - también rige las llamadas de los subagentes (verificado: el payload trae `agent_type`);
  - falla cerrado.
- *Diseño:* analiza **sentencias** (palabra de comando, argumentos, destino de redirección, `cd`), no el texto entero. Medido sobre los comandos reales de la sesión: una regex sobre el texto completo señaló 15 de 17 comandos legítimos que mencionan `data/inbox`; el análisis por sentencias, 0 de 18.

| Regla | Qué impone |
|---|---|
| R1 | No escribir en `data/inbox/**` ni `deliveries/**` |
| R2 | Sin `--amend`, `rebase`, `reset --hard`, push forzado, push a otro remoto que no sea `origin`, ni borrar tags |
| R3 | Commit con trailer, sin `-a`, `git add` y `git commit` por separado, índice sin `.jsonl`/`.env`/`output/`, entregas intactas y en commit propio, sin espacios sobrantes |
| R4 | Código solo si lo permiten la fase (F = último `phase-N` + 1) y los artefactos de `HEAD`: F ≤ 2 denegado; F = 3 `ask`; F ≥ 4 exige spec, plan con «Revisión del plan» y ≥ 2 commits sobre el plan; F ≥ 5 exige además `impact.md` |
| R5 | `deliver 1` tras `phase-1`; `deliver 2` tras `phase-4` y con la entrega 1 recibida (el enunciado fija el orden y el cierre de la fase 4 con su tag) |
| R6 | No se escribe un `settings.json` inválido; las escrituras por shell en `.claude/**` o `CLAUDE.md` piden confirmación |

**Subagente `kivora-reviewer`.**

- *Problema:* las 5 incidencias de la fase 2 (fechas de `R-1006`, control C-2 falso, `last_purchase_date` redundante, RF-7 y RF-8 sin escenario, `CAST AS NUMERIC` presentado como equivalente a `Decimal`) las detectamos tarde y con scripts improvisados.
- *Por qué un subagente:* trabaja con contexto aislado, sin anclarse en las conclusiones del autor, y es de solo lectura (`disallowedTools: Write, Edit, NotebookEdit`; el hook R1 también le aplica).
- *Qué aporta frente a pedírselo al agente principal:* otro contexto y un procedimiento fijo (hechos frente a datos, consistencia entre documentos, cobertura, formato de hallazgos con evidencia).
- *Límite:* no es determinista.
- *Uso posterior (fases 5 y 6):* revisó `impact.md`, `spec.md`, `plan.md`, el código y la memoria de KIV-102, y el proyecto entero (`docs/review.md`). Sus hallazgos cambiaron lo escrito cada vez (secciones 5.3 y 6).

### 2.4 Cómo se ejecutan

- **Hook:** antes de cada llamada a Bash, PowerShell, Edit, Write o NotebookEdit, Claude Code lanza el comando registrado (`shell: bash`, `timeout: 15`, `"onFailure": "block"`), que usa el `python` del `.venv` y, si falta, `uv run python`. Cuesta unos 0,35–0,6 s por llamada (medido). Salida 2 bloquea y el motivo llega al agente; un JSON `permissionDecision: ask` pide confirmación.
- **Subagente:** lo invoca el agente por su descripción o tú con `@kivora-reviewer`; `/agents` lo lista.

### 2.5 Evidencia

- **Pruebas del hook:** `uv run python -m pytest .claude/hooks -q` da 34 passed en unos 49 s. Usan repositorios Git temporales y llaman al guard como Claude Code, por stdin.
- **Las pruebas fallan si se rompe una regla:** se mutó una copia del guard para R1, R2, R3, R4, R5, R6 y el fallo cerrado, y en las 7 mutaciones falló la prueba correspondiente. Con el guard original pasan.
- **Configuración:** `claude doctor` sin «Invalid settings». Los tests del proyecto siguen igual (4 passed).
- **Sesión real de Claude Code (copia aislada del proyecto, sin remotos):**
  - Seis acciones prohibidas, todas bloqueadas: escribir en `data/inbox` con Write (regla deny de permisos), `Set-Content` en `data\inbox`, `commit --amend` y `push upstream` (R2), crear `kivora/prueba.py` (R4: es fase 3, pide confirmación) y `git add && git commit` en una orden (R3).
  - Quedaron intactos los datos (mismo SHA-256 de `orders.csv`) y el historial (mismo `HEAD`).
  - Lectura de `data/inbox`, `git status` y `git add` se ejecutaron.
  - Un commit con el trailer correcto superó el guard y quedó en la regla `ask`, sin concederse al ser no interactivo; el primer intento llegó al guard con el mensaje truncado por el entrecomillado de PowerShell y R3 lo bloqueó correctamente.
- **Subagente `kivora-reviewer` (una única ejecución, a petición del usuario; la prueba prevista de dos queda reducida a una):**
  - *Montaje:* proyecto aislado con el `spec.md` de `950c5e3` y el `plan.md` de `b7513de` (las versiones anteriores a corregir las incidencias de la fase 2), los datos, el ticket, las fuentes y los contratos, más la configuración real. El agente principal (`haiku`) delegó la revisión en el subagente (`sonnet`) con un prompt que no menciona las incidencias.
  - *Resultado:* informe de 11.521 caracteres con 16 hallazgos (4 altos, 6 medios, 6 bajos), coste 0,31 USD. Detectó **las 5 incidencias conocidas** (criterio previo: al menos 4 de 5):
    1. `R-1006` está en `refunds.json` de 09-05 y 09-06, no en 09-04 y 09-05 (hallazgo 2).
    2. C-2 no falla con los datos actuales: no hay ninguna fila cliente-día con neto < 0 (hallazgo 1).
    3. `last_purchase_date` coincide siempre con `metric_date` (hallazgo 5).
    4. `K-10151` (64,00 → 58,50 EUR), `K-10060` y `K-10062` no tenían escenario (hallazgos 10 y 3).
    5. `CAST AS NUMERIC` no equivale a `Decimal` (hallazgo 7, señalado como afirmación técnica sin ejecutar).
  - *Solo lectura comprobada:* la huella SHA-256 de los 41 ficheros del proyecto y su `git status` son idénticos antes y después; el propio informe declara que solo ejecutó scripts de lectura.
  - *Hallazgos nuevos que siguen abiertos* (no estaban en nuestras listas y quedan para decidir en la fase 4):
    - **Zona horaria de `metric_date`:** la especificación usa UTC, pero `daily_sales` usa `Europe/Madrid`. `K-10053` se creó el 2026-09-01 a las 22:10 UTC, ya el día 2 en Madrid; hay 6 pedidos entre las 22:00 y las 23:59 UTC. No figura en «Aclaraciones».
    - **Versiones de clientes:** `C005` llega tres veces (09-01, 09-02 y 09-05, con el nombre cambiado en la última). Si no se toma la última versión, el join por cliente duplica sus pedidos. Falta el requisito, un escenario y un control de unicidad.
  - *Limitaciones de la prueba:* no es determinista y se hizo una sola vez. Algunos hallazgos son artefactos del montaje: dice que «la rama no tiene commits» y que no existen `kivora/` ni `deliveries/` porque el proyecto de prueba solo copia datos, documentos y configuración (hallazgos 11 y 16). Otros señalan decisiones que se tomaron después y ya están corregidas en `spec.md` (por ejemplo, A-9 sobre qué pedidos se rechazan).
- **Spikes (todos verificados, en proyectos temporales):**
  - Los hooks se ejecutan también en las llamadas de un subagente.
  - El matcher distingue `Bash` y `PowerShell`.
  - Una regla `ask` no se aprueba sola en modo `auto`.
  - Sin `"onFailure": "block"`, un hook que falla deja ejecutar el comando.
  - `claude doctor` valida el fichero pero siempre sale con código 0: hay que leer su salida.
  - Para `Write`, el filtro `if` de un hook exige `Write(...)`, no `Edit(...)`; por eso la guarda no usa `if`.

### 2.6 Límites y recuperación

- Un `settings.json` inválido desactiva todo en silencio (verificado). R6 y la prueba con `claude doctor` lo mitigan, pero no lo eliminan.
- `claude doctor` no avisa de claves desconocidas ni de herramientas inexistentes en una regla.
- El hook es una guarda, no un sandbox: evasiones por indirección (`$p='dat'+'a/inbox'`, `cmd /c del`, comodines) no las cubre ninguna regla basada en texto; R3 compensa al commitear.
- En `claude -p` sobre una carpeta no confiada se ignoran las reglas `allow` del proyecto; los hooks y los `deny`/`ask` siguen aplicando.
- **Recuperación manual (solo una persona; verificada):** poner `{"disableAllHooks": true}` en `.claude/settings.local.json` (no se versiona), corregir el fallo, validar con `claude doctor` y quitar esa línea.

### 2.7 Uso real del guard en las fases 4 a 6

- **R4 (código tras los documentos):** en la fase 5 `impact.md`, `spec.md` y `plan.md` se commitearon antes de tocar `tests/`, `kivora/` o `tasks.py` (por eso el plan incluyó la tarea de commitearlo antes de empezar los tests).
- **R1 (datos de entrada):** bloqueó una orden legítima de la fase 5 (un script que escribía un documento y mencionaba `data/inbox`). Era un falso positivo: no se esquivó con otra orden, se pidió la decisión a la persona responsable y el cambio se aplicó con la herramienta de edición. Volvió a ocurrir en la fase 6, al escribir esta memoria con un script, con el mismo tratamiento.
- **Pruebas del hook:** siguen en 34 passed en las fases 5 y 6 (sección 2.5; `docs/review.md`).

### 2.8 No verificado

- El prompt interactivo de `ask` (solo se vio que no se aprueba solo, en modo no interactivo).
- Los matchers de `Edit` y `NotebookEdit` en una sesión real (sí se probaron `Write`, `Bash` y `PowerShell`).
- Si las reglas allow reducen los fallos del clasificador del modo auto (en la sesión de la fase 2 fueron 3).
- Linux y macOS.

---

## 3. Ciclo de iteración

**Cómo se estructuró el trabajo con el agente.** En todas las fases el orden fue el mismo: leer y analizar sin modificar nada, decidir las ambigüedades (el agente propone opciones y una recomendación; decide la persona responsable), escribir la especificación y el plan, revisar con un agente independiente, escribir primero los tests y el oráculo y comprobar que fallan, implementar lo mínimo y verificar con `test`, `acceptance` y `check`. Cada commit y cada push se autorizó antes. El feedback que se pasó al agente en cada vuelta fue, según el caso: la salida de los tests, la salida del oráculo `acceptance`, la comparación con la ejecución anterior, el informe de `kivora-reviewer` y las correcciones del usuario sobre cifras y decisiones.

| Fase | Vueltas registradas | Feedback principal | Criterio de «terminado» | Detalle |
|---|---:|---|---|---|
| 1 (KIV-100) | no se llevó tabla de vueltas | Verificación de cada afirmación con archivo y línea, o con el comando que la demuestra | `docs/analysis.md`, `CLAUDE.md` y la respuesta de KIV-100, sin cambios en `kivora/`, `sql/` ni `tests/` | `docs/analysis.md` y `docs/sessions/fase-1-sesion-claude.md` |
| 2 (especificar y planificar KIV-101) | 15 | Errores de herramienta (127, 429), cifras corregidas por el usuario, 8 observaciones al plan y 5 incidencias contra los datos | Especificación y plan (borrador y revisión) commiteados sin tocar código; cifras contrastadas con `data/inbox/` | Esta sección, fase 2 |
| 3 (configurar el agente) | no se llevó tabla de vueltas | Pruebas del hook, mutaciones del guard, sesión real aislada y spikes | 34 tests del hook en verde, 7 de 7 mutaciones detectadas, `claude doctor` sin errores | Sección 2.5 |
| 4 (implementar KIV-101) | 7 | Salida de `run` frente a la spec, tests y mutaciones, `acceptance`, `check` y determinismo | `test`, `acceptance` y `check` en verde, determinismo, tests que fallan con el código roto | Esta sección, fase 4 |
| 5 (KIV-102) | 6 | Informe del revisor sobre cada documento, tests y oráculo en rojo, comparación con la línea base | 51 tests, `acceptance` 28/28 y 21/21, `check`, 14 filas cambiadas, determinismo | Sección 5.4 |
| 6 (revisión y cierre) | 7 | Informe de `kivora-reviewer` sobre el proyecto entero y verificación de cada documento antes de commitearlo | Ver la fase 6 más abajo | Esta sección, fase 6 |

### Ciclo de iteración de la fase 2 (KIV-101: especificar y planificar)

Vueltas reales, en orden.

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
- **Copia íntegra:** existe una copia de la transcripción JSONL de la sesión fuera del repositorio (en una carpeta local de copias, SHA-256 `4DB513A0D31BD500650D086044EB3794FF1A3E62D21F7BC9D1345464693EB2D4`). **No se publica**: contiene metadatos internos, rutas y datos de las peticiones.
- **Privacidad:** una búsqueda por patrones (no una lectura línea a línea) no encontró credenciales ni claves. El export contiene rutas locales, el usuario de GitHub y nombres del material del curso, aceptados por el usuario.
- **Alcance temporal:** el export termina antes del commit de esta evidencia y del tag `phase-2`.

### Ciclo de iteración de la fase 4 (KIV-101)

Vueltas reales, en orden. Criterio de «terminado»: `tasks.py test`, `tasks.py acceptance` y `tasks.py check` en verde, determinismo comprobado, tests que fallan con el código roto, `data/`, `deliveries/` y `daily_sales.sql` intactos, y `spec.md`, `plan.md` y código coherentes.

| # | Feedback que se dio | Qué cambió | Resultado |
|---|---|---|---|
| 1 | Revisión de `spec.md`, `plan.md`, KIV-100, `CLAUDE.md` e informe y petición de resolver Madrid y última versión de cliente, sin tocar nada | Una única comprobación de impacto con los datos: 6 de 156 ventas cambian de día con Madrid; solo `C005` tiene varias versiones; solo cambia E-6 | El usuario aprobó las cuatro decisiones (sección 1.5) |
| 2 | «Actualizar primero `spec.md` y `plan.md`» | RF-21 a RF-23, A-10, A-11, E-14, E-15, C-6, E-6 y E-8 con cifras verificadas, revisión 3 del plan; se limpiaron frases desactualizadas y una errata que había señalado el revisor | Commit solo de documentación `642e773` |
| 3 | Salida del primer `tasks.py run` frente a la especificación | Datos (`refunds.json`, staging con última versión), selecciones SQL y `kivora/metrics.py` | 115 filas, 3 rechazos (`R-1003`, `R-1005`, `R-1006`), solo C-3 con anomalía, `C003` y `C005` con las cifras de la spec. Commit `a77d5f4` |
| 4 | Salida de los tests y mutaciones del código real | 16 tests con datos sintéticos | 20 passed (4 heredados + 16). Seis mutaciones (join con la tabla heredada, versión más antigua, UTC en vez de Madrid, `ROUND_HALF_EVEN`, sin exigir pago cobrado, duplicados de `refund_id` sin descartar) hacen fallar al menos un test cada una. Commit `d1a0b6e` |
| 5 | Salida de `acceptance`, de `check` con una salida rota a propósito y de dos ejecuciones con la interfaz oficial | `kivora/acceptance.py`, ampliación de `kivora/check.py` y tarea en `tasks.py` | `acceptance` 28 de 28 a la primera (incluidas las cifras de E-14 calculadas a mano en la spec); `check` sale con 1 con un neto roto y con 0 al restaurar; los hashes SHA-256 de las tres salidas coinciden entre ejecuciones. Commit `2b87363` |
| 6 | Respuesta a Finanzas en lenguaje de negocio | `docs/tickets/KIV-101.md` e informe | Cifras tomadas de la salida: 156 ventas, 18.490,74 € bruto, 1.310,19 € devuelto, 17.180,55 € neto |
| 7 | El usuario aprobó RF-23 y pidió mantenerlo en la especificación y en la implementación | RF-23 queda como aprobado en `plan.md`, en el informe y en `spec.md` (que deja constancia de la aprobación) | Corrección documental; no cambia el código ni los resultados |

Nota honesta: los 16 tests y las 28 comprobaciones de `acceptance` pasaron a la primera, sin ninguna vuelta de corrección de código. Por eso se añadió la comprobación por mutación (vuelta 4): un test que pasa a la primera solo es fiable si se demuestra que falla cuando la regla se rompe.

### Ciclo de iteración de la fase 5 (KIV-102)

Seis vueltas (impacto, especificación, plan, tests en rojo, `acceptance` en rojo e implementación), cada una con el feedback que se dio y su resultado, en la sección 5.4. Criterio de «terminado»: 51 tests, `acceptance` 28/28 y 21/21, `check` con código 0, comparación con la línea base (días 1 a 7 idénticos; con los 10 días cambian exactamente 14 filas) y determinismo. La implementación pasó a la primera, pero solo tras corregir antes tres tests marcados como rojos que pasaban con el código anterior y los tests de la primera versión que fallaban por un error propio (sección 5.3).

### Ciclo de iteración de la fase 6 (revisión y cierre)

Siete vueltas, sin cambios de código. Criterio de «terminado»: `test`, `acceptance` y `check` en verde, todas las rutas y comandos citados comprobados, cada cifra recalculada, el historial y los tags verificados, y cada documento revisado por la persona responsable antes de commitearlo.

| # | Feedback que se dio | Qué cambió | Resultado |
|---|---|---|---|
| 1 | Línea base: `test`, `acceptance`, `run`, `check`, tests del guard, `settings.json` y ficheros versionados | Nada | 51 tests; `acceptance` 28/28 y 21/21; 34 tests del guard; ningún `.env`, `.jsonl`, `output/` ni base de datos versionados |
| 2 | Revisión final con `kivora-reviewer` (solo lectura): código, pruebas, resultados, documentación, configuración del agente e historial | Nada | 9 hallazgos: 1 media-alta, 4 medias, 1 baja-media y 3 bajas; ninguno alto |
| 3 | Decisión del usuario sobre cada hallazgo y redacción de `docs/review.md` | `docs/review.md` | Al verificarlo antes del commit se vio que tres hallazgos figuraban como «Hecho» sin estarlo: se corrigió. Commit `6c6a4e2` |
| 4 | Verificación del README: 21 rutas y enlaces, comandos ejecutados y cifras de referencia contra la ejecución | `README.md` | Commit `85a49b2` |
| 5 | Autorización expresa para tocar `CLAUDE.md` y comprobación de que las secciones de Git y de protecciones quedaban idénticas | `CLAUDE.md` | Commit `1a4d610` |
| 6 | Comprobación de que el renombrado lo reconoce Git al 100 % y de que el SHA-256 de la sesión no cambia | `docs/sessions/fase-1-sesion-claude.md` (movida) | Commit `ac49701` |
| 7 | Verificación de las cifras y evidencias de esta memoria | `docs/report.md` y `docs/review.md` | Commit de esta memoria (ver `git log`) |

### Evidencia de sesión de las fases 1, 2, 4 y 5

Las cuatro sesiones están en `docs/sessions/`, exportadas con `/export` y sin editar. El enunciado exige las de las fases 2, 4 y 5. En `/export` el terminal pliega las salidas de las herramientas («… +N lines», «ctrl+o to expand»): es el formato del propio export. Los resultados de cada paso están en los resúmenes de la conversación y en los commits.

| Sesión | Bytes | SHA-256 | Salidas plegadas |
|---|---:|---|---:|
| `fase-1-sesion-claude.md` | 53.760 | `63AF9FA4D4BA953229FFDCC9E4C30B32741F47407B7E4CEFFC57E1AA1EA1075E` | 12 |
| `fase-2-sesion-claude.md` | 288.930 | `278E5C99CED6C0F0C70AA1D082E83BE7046FBB37C99A3FFC202A8255BD528E84` | 87 |
| `fase-4-sesion-claude.md` | 625.230 | `199A8B48043E96F721F949C8D3B94BF116DBE142EFC749CAAFDB034987CD325F` | 184 |
| `fase-5-sesion-claude.md` | 306.642 | `EBCAF681B1647B93C45EC6BD3AEA9A00C32206276AC0A9D044BA1CC971677B8C` | 54 |

Escaneo de la sesión de la fase 5 con un script de patrones (claves de Anthropic, tokens de GitHub, cabeceras Bearer, contraseñas, correos y rutas personales): no hay secretos; solo el correo `noreply@anthropic.com` de los trailers y rutas locales con el nombre de usuario del sistema operativo, que se dejan tal cual (decisión del usuario; `docs/review.md`, H8). La sesión de la fase 6 no es exigida por el enunciado.

---

## 4. Trazabilidad

Estado en la fase 4: cada requisito tiene escenario, control, test y comprobación de `acceptance`. Tests en `tests/test_kiv101.py`: **T1** `duplicate_orders_and_versions_count_once`, **T2** `null_country_and_unknown_customer_become_unknown`, **T3** `partial_refund_is_attributed_to_the_purchase_day`, **T4** `several_refunds_on_one_order_accumulate_without_duplicating_it`, **T5** `refund_without_order_is_rejected_and_not_counted`, **T6** `net_amount_with_currency_conversion_and_half_up_rounding`, **T7** `payments_validate_the_sale_but_never_multiply_it`, **T8** `customer_versions_do_not_duplicate_orders_and_the_latest_wins`, **T9** `empty_country_in_the_latest_customer_version_is_unknown`, **T10** `metric_date_is_the_europe_madrid_date`, **T11** `rejected_records_have_an_explicit_reason`, **T12** `refund_larger_than_the_purchase_is_kept_and_flagged_by_the_controls`, **T13** `days_without_refunds_file_or_with_an_empty_list_are_fine`, **T14** `outputs_are_deterministic`, **T15** `control_c6_detects_orders_duplicated_by_a_join`, **T16** `quality_anomalies_do_not_change_the_exit_code`.

| Requisito | Escenarios | Control | Tests | `acceptance` / `check` |
|---|---|---|---|---|
| RF-1 columnas y grano | E-2, E-3, E-4, E-6 | C-1 | T3, T6 | acceptance E-2 a E-6; `check` (columnas, fechas, importes, filas repetidas) |
| RF-2 `rejected.csv` | E-5, E-8, E-11, E-13 | C-5 | T5, T11 | acceptance E-5, E-8, E-11, E-13; `check` (motivo no vacío) |
| RF-3 `quality_report.json` | — | C-1 a C-6 | T12 | acceptance C-1..C-6; `check` (estructura) |
| RF-4 EUR y dos decimales | E-10 | C-1 | T6 | acceptance E-4/E-10; `check` (dos decimales) |
| RF-5 moneda no soportada | — (los datos actuales solo tienen EUR, GBP y USD) | — | T11 | — (dato sintético) |
| RF-6 un pedido, una vez | E-1, E-7 | C-6 | T1, T7, T8 | acceptance E-1, E-7, E-15 |
| RF-7 última versión de pedido | E-12 | — | T1 | acceptance E-12 |
| RF-8 venta válida | E-8, E-13 | — | T7, T11 | acceptance E-8, E-13 |
| RF-9 pagos no multiplican | E-7 | — | T7 | acceptance E-7 |
| RF-10 `refund_id` único | E-11 | C-4 | T11 | acceptance E-11 |
| RF-11 atribución al día de compra | E-3, E-4, E-6 | — | T3, T10 | acceptance E-3, E-4, E-6 |
| RF-12 pedido inexistente | E-5 | C-5 | T5 | acceptance E-5 |
| RF-13 pedido cancelado | E-8 | C-5 | T11 | acceptance E-8 |
| RF-14 devoluciones parciales y múltiples | E-3, E-4 | C-3 | T3, T4 | acceptance E-3, E-4 |
| RF-15 país `UNKNOWN` | E-2 | — | T2, T9 | acceptance E-2 |
| RF-16 `last_purchase_date` | (se observa en todos los escenarios de métricas) | — | T10 | acceptance E-2, E-4; `check` (no posterior a `metric_date`) |
| RF-17 neto y anomalías | E-4, E-6 | C-1, C-2, C-3 | T12 | acceptance C-1..C-6 (C-3 detecta `K-10148`) |
| RF-18 determinismo | E-9 | — | T14 | acceptance E-9; hashes SHA-256 con la interfaz oficial |
| RF-19 no escribir en la entrada | — | — | — | acceptance trabaja sobre una copia; `git status` sin cambios en `data/` y `deliveries/` |
| RF-20 código de salida 0 | — | C-2, C-3 | T16 | `tasks.py run` sale con 0 con C-3 en anomalía |
| RF-21 fecha `Europe/Madrid` | E-14, E-6 | — | T10 | acceptance E-14 |
| RF-22 última versión de cliente | E-15 | C-6 | T8, T9, T15 | acceptance E-15 |
| RF-23 datos defectuosos | — (los datos actuales no los contienen) | C-5, C-6 | T11, T13 | — (dato sintético) |

**Lagunas que siguen abiertas:** RF-5 y RF-23 no tienen dato real en `data/inbox/`, por lo que solo los cubren tests con datos sintéticos; RF-19 se comprueba con `git status`, no con un test automático.

**Resultados de la verificación (fase 4):**

- `uv run python tasks.py test`: 20 passed (4 heredados y 16 nuevos).
- `uv run python tasks.py acceptance`: 28 de 28 comprobaciones.
- `uv run python tasks.py check`: OK; con un neto roto a propósito sale con 1.
- Determinismo: dos ejecuciones con `python -m kivora` dan los mismos SHA-256 en `daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json`.
- Mutaciones: 6 de 6 detectadas por los tests (sección 3).
- Cifras verificadas de la salida: 115 filas cliente-día, 32 clientes, 156 ventas, 18.490,74 EUR bruto, 1.310,19 EUR devuelto en 29 devoluciones, 17.180,55 EUR neto, 3 rechazos y solo C-3 con anomalía (`K-10148`: 101,20 EUR devueltos sobre 92,00 EUR). Con fechas UTC habría 118 filas.

**Trazabilidad de KIV-102 (fase 5).** Los requisitos RC-1 a RC-13 del nuevo formato de `refunds.json` están en la sección 5.5, cada uno con su escenario, su test de `tests/test_kiv102.py` y su comprobación de la segunda pasada de `acceptance`. Estado final del proyecto: 51 tests (4 heredados, 16 de KIV-101 y 31 de KIV-102), `acceptance` con 28 comprobaciones de KIV-101 y 21 de KIV-102, y `check` con código 0. Las lagunas de esta tabla siguen igual (RF-5 y RF-23 solo con datos sintéticos; RF-19 con `git status`); las dos mutaciones que solo detectan los tests unitarios y no `acceptance` (prioridad entre `refund_amount` y `amount`, y control C-6) están en `docs/review.md`, sección 3.

---

## 5. Cambio de esquema

Ticket KIV-102: `refunds.json` cambia de formato desde el 2026-09-08 (`amount` pasa a `refund_amount` y aparece `reason`, que puede ser `null`) y los dos formatos conviven en `data/inbox/`. Documentos de la fase: `docs/specs/KIV-102/impact.md`, `spec.md` y `plan.md`; respuesta en `docs/tickets/KIV-102.md`.

### 5.1 Cómo se analizó el impacto (antes del código)

Orden real del historial (`git log phase-4..HEAD`), con el análisis antes de cualquier cambio de código:

| Commit | Contenido |
|---|---|
| `9351756` | Entrega 2 (`tasks.py deliver 2`): 13 ficheros (3 días × 4 ficheros, más `docs/tickets/KIV-102.md`), en un commit propio |
| `677fc96` | `docs/specs/KIV-102/impact.md` (**antes** de cualquier cambio de código) |
| `4642b3b` | `docs/specs/KIV-102/spec.md` (RC-1 a RC-13, escenarios E-1 a E-12, decisiones A-1 a A-11) |
| `a644c23` | `docs/specs/KIV-102/plan.md`, con «Revisión del plan» |
| `ce57809` | `tests/test_kiv102.py`: 31 tests, 21 en rojo con el código de la fase 4 y 10 de guarda |
| `3f3cdbe` | `kivora/acceptance.py` con segunda pasada para KIV-102 (en rojo: 3/21) y ayuda de `acceptance` en `tasks.py` |
| `c978007` | `kivora/ingest.py`: lectura de los dos formatos (único cambio de código de producción) |
| `da786bf` | `docs/sources.md`: sección de `refunds.json` en sus dos formatos (no existía) |
| `b7b7124` | Respuesta en `docs/tickets/KIV-102.md` |

Método del análisis (`impact.md`), sin modificar nada del repositorio:

1. Se leyó el ticket, el código afectado, los contratos y los tests.
2. Se ejecutó el pipeline actual sobre los 10 días, con la salida fuera del repositorio, y se compararon los resultados con los de solo los días 01 a 07.
3. Se simuló la solución sobre una **copia** de los datos (renombrando `refund_amount` a `amount`) únicamente para **medir** el efecto esperado. No fue la implementación.
4. Se enumeraron los archivos afectados, los riesgos de regresión y las ambigüedades, sin inventar requisitos.

Lo que reveló (cifras reproducidas por `kivora-reviewer`):

| Medida | Con el código de la fase 4 | Con soporte del formato nuevo |
|---|---:|---:|
| Devoluciones nuevas recibidas (días 08 a 10) | 15 | 15 |
| Rechazadas como `importe no valido` | **14** | 0 |
| Registros en `rejected.csv` | 18 | 4 |
| Filas de `daily_customer_metrics.csv` que cambian | — | 14 (12 de días 01 a 07 y 2 de los días 08 y 09) |
| Controles de calidad con anomalía | solo C-3 (`K-10148`) | C-2 = 1 (`C026`, neto −10,00 €) y C-3 = 2 (`K-10148` y `K-10155`) |
| Código de salida del pipeline | 0 | 0 |

Hallazgo principal: **el fallo era silencioso**. El pipeline terminaba bien y solo el número de rechazados (de 3 a 18) delataba que se perdían 14 de las 15 devoluciones nuevas. Matiz importante: con el código anterior el control C-3 **ya señalaba una anomalía**, pero era la preexistente de KIV-101 (`K-10148`) y no tenía relación con el cambio de formato. **Ningún control detectaba las 14 devoluciones perdidas**: ni los seis controles de `quality_report.json` ni el código de salida lo reflejaban. `daily_sales.csv` y `top_customers.csv` no dependen de las devoluciones y no cambian (comprobado byte a byte).

### 5.2 Decisiones con el agente (spec KIV-102, A-1 a A-11)

El agente propuso las opciones y una decisión justificada para cada ambigüedad; la persona responsable las revisó y las aprobó o las cambió:

| Decisión | Origen | Resultado |
|---|---|---|
| A-1: con `amount` y `refund_amount` a la vez manda `refund_amount` | Propuesta del agente, aprobada | Regla defensiva, no ocurre en los datos |
| A-2: sin importe, `null` o vacío → `importe no valido`, no 0 | Preserva RF-23 de KIV-101 | Aprobada |
| A-3: `reason` solo en `raw_refunds`, ninguna salida lo publica | Propuesta del agente, aprobada | Es texto libre y puede contener datos personales |
| A-4: `reason` ausente, `null` o vacío no rechaza | Del ticket («puede venir a `null`») | Aprobada |
| A-5: el formato se decide por registro, no por fichero | Propuesta del agente, aprobada | |
| A-6, A-7: neto negativo informado; devoluciones al día de compra | Preservan RF-17 y RF-11 de KIV-101 | Aprobadas |
| A-8: `acceptance` con segunda pasada sobre los 10 días | Propuesta del agente, aprobada | |
| A-9: importe número o texto numérico | Del ticket y de `parse_float=str` | Aprobada |
| A-10: importes cero o negativos | **El agente propuso rechazarlos; la persona responsable no lo autorizó.** KIV-101 solo rechaza importes ausentes o no numéricos, y no había requisito explícito | Se conserva el comportamiento anterior; el test `test_zero_and_negative_amounts_keep_the_current_behaviour` lo fija |
| A-11: moneda ausente, `refund_id`/`order_id` ausentes, `refunded_at` | Preserva KIV-101 | Sin cambios |

La decisión A-10 es el ejemplo claro de delegar y decidir: el agente detectó un hueco real y propuso una regla; la persona responsable comprobó primero qué establecía KIV-101 y decidió no introducir una regla nueva sin requisito.

### 5.3 Revisión con un agente independiente (`kivora-reviewer`, solo lectura)

Cada documento se revisó antes de commitearlo. El revisor ejecutó el pipeline sobre copias fuera del repositorio y reprodujo las cifras:

| Documento | Hallazgos | Qué se cambió |
|---|---|---|
| `impact.md` | 1 media y 6 bajas | Desfase de la spec de KIV-101 (C-2/C-3) declarado; `docs/sources.md` pasó de «desactualizado» a «sin documentar»; dirección del error en las cifras de Finanzas; líneas de código citadas |
| `spec.md` | 5 medias y 3 bajas | RC-7 hablaba de «ninguna cabecera con `reason`» y `rejected.csv` tiene una columna `reason` (el motivo de rechazo): se reformuló para el **valor** del campo; RC-4 apuntaba a un escenario equivocado; faltaba indicar dónde se verifica cada escenario; el caso de los importes cero o negativos (A-10) |
| `plan.md` | 13 cambios (ver `plan.md`, sección 6) | **Tres tests marcados como rojos pasaban con el código actual** (el revisor los ejecutó): se reetiquetaron o se les añadieron aserciones; una frase errónea sobre los días 01 a 07; faltaba la tarea del commit del plan (regla R4 del guard) |

Errores propios, detectados y corregidos con verificación y no por suposición:

- Los primeros tests de `tests/test_kiv102.py` usaban una fecha de pedido equivocada. Fallaban en rojo, pero por una razón distinta de la esperada (`NoneType`). Se detectó al leer los **mensajes** de fallo de los 21 rojos, no solo al contarlos, y se corrigió antes del commit.
- Un test que yo había clasificado como guarda (`test_real_data_only_late_refunds_change_days_01_to_07`) en realidad dependía del cambio: se movió a los rojos.
- En la respuesta del ticket redacté una petición a Plataforma que el ticket no contempla. Se eliminó antes de commitear.
- El guard (`kivora_guard`, regla R1) bloqueó un script mío que escribía un documento y mencionaba `data/inbox`. Era un falso positivo; no se esquivó con otra orden: se pidió la decisión a la persona responsable y se aplicaron los cambios con la herramienta de edición.

### 5.4 Ciclo de la fase 5

| Vuelta | Feedback | Resultado |
|---|---|---|
| Impacto | Revisión de `kivora-reviewer` | 7 correcciones en `impact.md`; commit `677fc96` |
| Spec | Revisión + decisión sobre A-10 | 5 medias y 3 bajas aplicadas, A-10 sin cambio; commit `4642b3b` |
| Plan | Revisión (el revisor ejecutó los tests propuestos) | 13 cambios; commit `a644c23` |
| Tests en rojo | Salida de `pytest` con el código de la fase 4 | 21 rojos y 10 verdes; corregidas las fechas de tres tests; commit `ce57809` |
| Acceptance en rojo | `tasks.py acceptance` con el código actual | KIV-101 28/28 y KIV-102 3/21; contrastado con la simulación (21/21); commit `3f3cdbe` |
| Implementación | Los 31 tests, `acceptance`, `check` y comparación con la línea base | Todo en verde a la primera; commit `c978007` |

**Criterio para dar la fase por terminada:** `tasks.py test` en verde (51 pruebas: 20 de antes y 31 nuevas), `tasks.py acceptance` en verde en las dos pasadas (28/28 de KIV-101 y 21/21 de KIV-102), `tasks.py check` con código 0, los tests del guard (34) en verde, y la comparación con la línea base de la tarea 0:

- Días 01 a 07: los cinco ficheros salen idénticos byte a byte.
- Días 01 a 10: cambian exactamente 14 filas de `daily_customer_metrics.csv`; `daily_sales.csv` y `top_customers.csv` salen idénticos; dos ejecuciones dan ficheros idénticos.
- Rechazos: 4 (`R-1003`, `R-1005`, `R-1006` y `R-1034`), ninguno por `importe no valido`.
- El texto de `reason` no aparece en ninguna salida.

### 5.5 Trazabilidad de KIV-102

| Requisito | Escenario | Test (`tests/test_kiv102.py`) | `acceptance` (segunda pasada) |
|---|---|---|---|
| RC-1: leer `refund_amount` | E-1 a E-3, E-5, E-8 | `test_refund_amount_is_counted`, `test_refund_amount_converts_currency`, `test_late_refund_restates_the_purchase_day`, `test_real_data_new_refunds_change_exactly_14_rows` | las 14 filas con sus cuatro cifras |
| RC-2: el formato anterior no cambia | E-6 | `test_old_format_unchanged`, `test_real_data_old_format_days_01_to_07_unchanged`, `test_real_data_only_late_refunds_change_days_01_to_07` y los 20 tests anteriores | las 28 comprobaciones de la primera pasada |
| RC-3: formatos mezclados | E-4 | `test_both_formats_on_same_order`, `test_formats_mixed_in_same_file` | `C026 / 2026-09-06` |
| RC-4: manda `refund_amount` | E-9 | `test_refund_amount_wins_when_both_present` | — (caso sintético) |
| RC-5: importe ausente, `null` o vacío | E-9 | `test_refund_amount_used_when_amount_is_blank`, `test_null_or_blank_refund_amount_falls_back_to_amount`, `test_record_without_any_amount_is_rejected` | — (caso sintético) |
| RC-6: `reason` opcional | E-1, E-10 | `test_reason_null_blank_absent_or_text_is_accepted` (6 variantes) | `R-1033` (`reason = null`) no está en `rejected.csv` |
| RC-7: `reason` solo en `raw_refunds` | E-10 | `test_reason_is_kept_only_in_raw_refunds`, `test_real_data_reason_is_stored_in_raw_refunds` | — |
| RC-8: campos desconocidos | E-11 | `test_unknown_fields_are_ignored` | — (caso sintético) |
| RC-9: ningún `importe no valido` por el formato | E-7 | `test_real_data_rejections_and_controls` | `rejected.csv` exacto y ningún `importe no valido` |
| RC-10: controles de calidad | E-5, E-7 | `test_quality_controls_see_new_format`, `test_new_refunds_do_not_duplicate_rows`, `test_real_data_rejections_and_controls` | C-2 = 1 y C-3 = 2 |
| RC-11: contrato y determinismo | E-12 | `test_output_is_deterministic_with_both_formats`, `test_sales_outputs_do_not_depend_on_refunds` | dos ejecuciones idénticas; 164 filas únicas |
| RC-12: `acceptance` ampliado | — | — | `tasks.py acceptance`, código 0 |
| RC-13: `data/inbox/` y `deliveries/` intactos | — | `git status` sin cambios en esas carpetas | — |

**Qué demuestran los tests.** 21 de los 31 tests nuevos fallaban con el código de la fase 4 y pasan con el nuevo; los 10 restantes protegen comportamiento existente (formato anterior, rechazo sin importe, campos desconocidos, importes cero y negativos, independencia de `daily_sales`) y pasaban antes y después.

### 5.6 Qué se aprendió

- **Un cambio de formato falla en silencio.** Los controles de KIV-101 miden la coherencia de lo que se calcula, no que se calcule todo lo que llega. Por eso se añadió a `acceptance` la comprobación del número exacto de rechazados y de las filas afectadas.
- **Medir antes de decidir.** Simular la solución sobre una copia dio las cifras de Finanzas (14 filas, 12 de ellas de días ya entregados) antes de escribir una línea de código.
- **Las devoluciones tardías revisan el pasado.** Al atribuirlas al día de compra, las cifras de los días 1 a 7 de Finanzas pasan de 1.310,19 € a 1.591,15 € devueltos. Es una consecuencia de una regla ya aprobada y se explica en la respuesta del ticket.
- **Un test rojo no basta: hay que ver por qué falla.** Tres tests marcados como rojos en el plan pasaban con el código actual (lo vio el revisor al ejecutarlos) y varios tests de la primera versión fallaban por un error del propio test (la fecha del pedido); solo se vio al ejecutar y leer los mensajes de fallo.
- **El guard cumple su función y tiene falsos positivos.** Bloqueó una orden legítima; la regla del proyecto (no eludir, pedir decisión) se respetó.

### 5.7 Límites

- La sesión de la fase 5 se exportó con `/export` durante el cierre de la fase, antes del tag `phase-5`, y está en `docs/sessions/fase-5-sesion-claude.md` (commit `23628be`; huella en la sección 3).
- Las evidencias de ejecución de las tareas de la fase 5 (línea base, salidas de los tests rojos y verdes y comparaciones) están en una carpeta local de copias fuera del repositorio y no se versionan; lo que importa de ellas queda en los commits, en `docs/report.md` y en los documentos de `docs/specs/KIV-102/`.
- El tag `phase-5` (`23628be`) está publicado en `origin`.
- Riesgos que se asumen y se documentan en `docs/review.md`: `daily_sales.csv` y `top_customers.csv` no cumplen del todo su contrato (H1), y algunas entradas malformadas, como un `refunds.json` de 0 bytes, hacen terminar el pipeline con error (H6).

---

## 6. Revisión

El detalle completo, con la evidencia y la justificación de cada decisión, está en [`docs/review.md`](review.md). Aquí se resume.

**Revisor.** Subagente `kivora-reviewer`, de solo lectura y con un contexto distinto del de la sesión que escribió el código y los documentos (es el revisor independiente que exige el enunciado en la fase 6). Revisó el código, las pruebas, los resultados, la documentación, la configuración del agente, el historial y el cumplimiento del enunciado sobre el estado `23628be` (tag `phase-5`). Ejecutó el pipeline, las mutaciones y las pruebas de robustez sobre copias fuera del repositorio y no modificó nada (`git status` vacío). Resultado: **9 hallazgos** (1 media-alta, 4 medias, 1 baja-media y 3 bajas; ninguno alto).

| Id | Gravedad | Hallazgo | Decisión del usuario | Estado |
|---|---|---|---|---|
| H1 | Media-alta | `daily_sales.csv` y `top_customers.csv` no cumplen del todo su contrato (sin conversión a EUR, fecha UTC, sin última versión, joins que multiplican): 231 pedidos y 27.032,34 frente a 213 ventas y 25.072,41 € | **Rechazado el cambio de código; riesgo documentado.** Ningún ticket lo pide, lo consume otro equipo y ya estaba comunicado desde KIV-100 y KIV-101 | Documentado |
| H2 | Media | 4 commits de la fase 1 sin `Co-Authored-By` (anteriores a la regla de `3a438a5`) | **Aceptado como riesgo, sin reescribir el historial** (prohibido por el enunciado) | Documentado |
| H3 | Media | Esta memoria estaba desfasada (tags, estado, versión, historial, secciones 3, 6 y 7) | Aceptado | Hecho en esta versión |
| H4 | Media | README sin actualizar | Aceptado | Hecho (`85a49b2`) |
| H5 | Media | `CLAUDE.md` sin `acceptance`, devoluciones ni formatos de `refunds.json` | Aceptado | Hecho (`1a4d610`) |
| H6 | Baja-media | Entradas fuera de los datos actuales hacen fallar el pipeline (`refunds.json` de 0 bytes, CSV con BOM, `--inbox` inexistente) o agrupan devoluciones sin `refund_id` | **Rechazado el cambio de código; riesgo documentado.** Están fuera del «mismo tipo de problemas» del enunciado y el conjunto de motivos de `rejected.csv` es cerrado | Documentado |
| H7 | Baja | La sesión de la fase 1 estaba en `docs/sesiones/` y las demás en `docs/sessions/` | Aceptado | Hecho (`ac49701`) |
| H8 | Baja | Ruta personal en esta memoria y rutas del usuario de Windows en las sesiones | Aceptado en parte: se quita de la memoria; **las sesiones no se editan** | Hecho en esta versión |
| H9 | Baja | La respuesta de KIV-101 cita 20 pruebas y 28 comprobaciones (hoy 51 y 49) | **Rechazado el cambio:** son cifras históricas de la fase 4, y se aclara su fase en `docs/review.md` | Documentado |

**Lo que el revisor comprobó como correcto.** Todas las cifras de los tickets y de esta memoria, con un cálculo independiente en Python con `Decimal`. Los 7 casos que exige el enunciado tienen un test que falla con el código roto (mutaciones reales: sin deduplicar, sin `UNKNOWN`, devoluciones que no acumulan, pedido inexistente sin rechazar, neto que ignora devoluciones, joins que multiplican, `ROUND_HALF_EVEN`, `float`, un solo formato de `refunds.json` y otras), con dos excepciones que solo detectan los tests unitarios y no `acceptance` (la prioridad entre `refund_amount` y `amount`, y el control C-6). También comprobó la robustez ante otras fechas, cambios de hora, un día sin ficheros y campos vacíos; el determinismo; los tags y el orden de las fases; que `data/inbox/` y `deliveries/` son iguales a las entregas; y la configuración del agente (el hook bloqueó una orden de prueba). No pudo verificar `claude doctor`, línea por línea los miles de líneas de documentos y sesiones, qué mide el script automático de corrección ni la atribución de los commits de la fase 1 (`docs/review.md`, sección 4).

**Revisiones anteriores con el mismo revisor** (sección 5 de `docs/review.md`):

| Revisión | Hallazgos | Efecto |
|---|---|---|
| Plan de KIV-101, fase 2 | 5 incidencias de cifras (sección 1.4) | Corregidas en `spec.md`, `plan.md` y esta memoria |
| `spec.md` y `plan.md` de KIV-101, fase 4 | Un caso no previsto que dio lugar a RF-23 | Incorporado antes del código |
| `impact.md`, `spec.md` y `plan.md` de KIV-102 | 1 media y 6 bajas; 5 medias y 3 bajas; 13 cambios (tres tests en rojo que pasaban) | Aplicados antes de commitear cada documento (sección 5.3) |
| Código y memoria de KIV-102 | 0 altos y 0 medios; 2 bajos | Sin cambios necesarios |

Los hallazgos se aplicaron o se rechazaron con motivo, y lo aceptado se corrigió en commits propios de la fase 6 (`85a49b2`, `1a4d610`, `ac49701` y esta memoria).

---

## 7. Qué harías distinto

Cada punto parte de un hecho que consta en el repositorio.

1. **Fijar las reglas de Git antes del primer commit.** Los 4 commits de la fase 1 no llevan `Co-Authored-By` porque la regla se estableció después (`3a438a5`) y no se puede reescribir el historial (H2). Pondría el trailer, el idioma de los mensajes y las reglas de commits en `CLAUDE.md` el primer día.
2. **Abrir el cambio de `daily_sales` como ticket propio al cerrar KIV-100.** El análisis de la fase 1 ya había documentado sus defectos y se llegó a la revisión final con el riesgo abierto (H1). Habría pedido entonces la decisión a Dirección Comercial, en lugar de arrastrar una limitación conocida durante cuatro fases.
3. **Ver por qué falla cada test rojo antes de darlo por bueno.** En la fase 5 tres tests marcados como rojos en el plan pasaban con el código actual, y varios tests de la primera versión fallaban por un error propio y no por el motivo esperado (secciones 5.3 y 5.6). Ejecutaría y leería los mensajes de fallo antes de etiquetarlos.
4. **Actualizar la memoria al cerrar cada fase, con una lista de comprobación.** La revisión final encontró referencias obsoletas (tags «todavía no creados», estados «pendiente de commit», secciones 3, 6 y 7 sin completar; H3). Al cerrar cada fase repasaría la cabecera, la tabla de historial, los estados y las referencias cruzadas.
5. **Decidir en la especificación qué hacer con entradas malformadas.** Un `refunds.json` vacío o un CSV con BOM hacen fallar el pipeline (H6). Habría añadido un escenario de «fichero vacío o malformado» a la especificación de KIV-101 y decidido entonces si se tolera o se informa.
6. **Afinar el guard para distinguir mencionar de escribir.** La regla R1 bloqueó órdenes legítimas en las fases 5 y 6 porque nombraban `data/inbox` mientras escribían un documento (sección 2.7). No había riesgo para los datos, pero obligó a parar y pedir una decisión. Añadiría una prueba de ese caso al guard.
7. **Mantener fuera de los documentos las rutas con el nombre de usuario del sistema.** La memoria y las sesiones las contienen (H8). Las sesiones deben ir sin editar, pero la memoria no tendría que haberlas incluido.

**Lo que mantendría.** Analizar el impacto antes de tocar código (en la fase 5 permitió dar las cifras de Finanzas antes de escribir una línea); los tests y el oráculo en rojo antes de implementar; un revisor independiente sobre cada documento antes de commitearlo (cada vez encontró algo que cambió lo escrito); y un guard que impone de forma determinista las reglas que antes había que repetir en cada prompt.
