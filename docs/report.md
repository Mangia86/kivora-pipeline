# Memoria de la práctica · Pipeline Kivora

**Versión:** 0.5, fase 4 (implementación de KIV-101) añadida sobre la 0.4 de la fase 3. La 0.1 se commiteó en `efe0bcc`, la 0.3 en `f37e4ee` y la 0.4 en `dcc4bbb`.
**Estado:** documenta lo ocurrido hasta la fase 4 (implementación, pruebas y trazabilidad completas; pendiente de cerrar con el tag `phase-4`). Las secciones que dependen de las fases 5 y 6 están marcadas como **PENDIENTE** y no contienen resultados ni decisiones inventados.

**Historial de referencia (fases 2 a 4):**

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
| *(commit de documentación, ver `git log`)* | Fase 4: respuesta a Finanzas en `docs/tickets/KIV-101.md` y esta memoria (v0.5) |

Los tags `phase-1`, `phase-2` y `phase-3` existen; `phase-4` **todavía no está creado**.

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

### 1.5 Decisiones de la fase 4 (implementación de KIV-101)

| # | Decisión | Quién | Dónde queda |
|---|---|---|---|
| 1 | `metric_date` en `Europe/Madrid`, coherente con el contrato de `daily_sales`. `daily_sales.sql` **no se modifica** y sigue en UTC: la diferencia es una limitación conocida | Propuesta de Claude tras medir el impacto (6 de 156 ventas cambian de día); decisión del usuario | `spec.md` RF-21, A-10, E-14; `plan.md` paso 5; respuesta a Finanzas |
| 2 | Última versión disponible de cada cliente; país vacío → `UNKNOWN` sin rellenar con versiones anteriores | Claude propuso; decisión del usuario | `spec.md` RF-22, A-11, E-15; `plan.md` paso 2b |
| 3 | Control C-6 (conciliación de ventas) y ampliación de `check.py` | Claude propuso; decisión del usuario | `spec.md` C-6; `plan.md` pasos 8 y 11 |
| 4 | Primero un commit solo de documentación (`spec.md` y `plan.md`) y después el código | Decisión del usuario | Commit `642e773`, anterior a todo el código |
| 5 | Defensa ante datos defectuosos (RF-23): devolución sobre un pedido sin pago cobrado, importes o fechas ilegibles se rechazan con motivo explícito | **Claude, sin aprobación explícita**: cierra un caso que señaló el revisor independiente (hallazgos 8 y 15) y evita que el pipeline falle con datos desconocidos | `spec.md` RF-23 y §5.2 (siete motivos); `plan.md` paso 6. **Pendiente de confirmación del usuario** |

Decisiones de diseño derivadas: la fecha de Madrid y toda la aritmética monetaria se calculan en Python (`kivora/metrics.py`); SQL solo selecciona; `stg_orders` y `stg_customers` heredadas no se tocan; `acceptance` trabaja sobre las entregas hasta 2026-09-07 (copiadas a una carpeta temporal) para que las entregas posteriores no muevan las cifras esperadas.

---

## 2. Configuración del agente

**Estado:** implementada en la fase 3 y verificada; pendiente de commit y del tag `phase-3`. Antes de la fase 3 no existía `.claude/`, el `settings.json` de usuario solo tenía `theme` y `model`, y las reglas de `CLAUDE.md` (solo instrucciones) las repetías tú en casi cada prompt: 18 de 20 prompts de la sesión de la fase 2 repiten «no commit/push», 16 «no modifiques código/datos», 16 «no crees tags» y 3 «no ejecutes `deliver 2`».

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
- *Límite:* no es determinista. Se reutiliza como revisor independiente en la fase 6.

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

### 2.7 No verificado

- El prompt interactivo de `ask` (solo se vio que no se aprueba solo, en modo no interactivo).
- Los matchers de `Edit` y `NotebookEdit` en una sesión real (sí se probaron `Write`, `Bash` y `PowerShell`).
- Si las reglas allow reducen los fallos del clasificador del modo auto (en la sesión de la fase 2 fueron 3).
- Linux y macOS.

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

Nota honesta: los 16 tests y las 28 comprobaciones de `acceptance` pasaron a la primera, sin ninguna vuelta de corrección de código. Por eso se añadió la comprobación por mutación (vuelta 4): un test que pasa a la primera solo es fiable si se demuestra que falla cuando la regla se rompe.

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

---

## 5. Cambio de esquema

**PENDIENTE (fase 5).** Todavía no se ha recibido la entrega 2 ni el ticket KIV-102; no hay análisis de impacto.

---

## 6. Revisión

**PENDIENTE (fase 6).** `docs/review.md` no existe. La revisión realizada en la fase 2 es la del plan (sección 1.3 y `plan.md`, sección 8), aportada por el usuario; no sustituye a la revisión con un revisor independiente exigida en la fase 6.

---

## 7. Qué harías distinto

**PENDIENTE.** Se redactará al cerrar la práctica, con la experiencia de las fases 3 a 6.
