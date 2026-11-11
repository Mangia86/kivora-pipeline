# Revisión final del proyecto Kivora (fase 6)

- **Estado revisado:** commit `23628be` (tag `phase-5`), con los tags `phase-1` a `phase-5` publicados en `origin`.
- **Revisor:** subagente `kivora-reviewer` (`.claude/agents/kivora-reviewer.md`), de **solo lectura** y con un contexto distinto del de la sesión que escribió el código y los documentos. Es el revisor independiente que exige el enunciado (fase 6).
- **Método:** el revisor leyó el enunciado, `CLAUDE.md` y `README.md`, y comprobó código, pruebas, resultados, documentación, configuración del agente, historial y entrega. Ejecutó el pipeline y las mutaciones sobre copias fuera del repositorio (`--out`, `TEMP` y `--basetemp` externos), y no modificó nada: `git status` quedó vacío.
- **Quién decide:** la persona responsable del proyecto. Las decisiones de esta tabla son suyas; el agente propuso una recomendación para cada una.
- **Línea base previa a la revisión (tarea 0 de la fase 6):** 51 tests en verde, `tasks.py acceptance` con KIV-101 28/28 y KIV-102 21/21, `run` y `check` con código 0, 34 tests del guard en verde, `.claude/settings.json` válido y ningún `.env`, `.jsonl`, `output/` ni base de datos versionados.

## 1. Tabla de hallazgos

Gravedad según el revisor. Los hallazgos H1 a H9 los encontró `kivora-reviewer`. **H10 lo detectó después el agente de la sesión, al verificar el cierre de la fase 6** (revisando el reflog), y no lo vio el revisor.

| Id | Encontrado por | Gravedad | Hallazgo | Decisión | Motivo | Dónde se resuelve |
|---|---|---|---|---|---|---|
| H1 | kivora-reviewer | Media-alta | `daily_sales.csv` y `top_customers.csv` siguen incumpliendo el contrato de `daily_sales` (sin conversión a EUR, fecha UTC, sin última versión del pedido, joins que multiplican pedidos con varios pagos) | **Rechazado el cambio de código: se documenta el riesgo** | Ver §2.1 | Esta tabla y sección 6 de `docs/report.md` |
| H2 | kivora-reviewer | Media | 4 commits de la fase 1 (`38e412b`, `4e5b067`, `4d88adb`, `f8df7c9`) no llevan `Co-Authored-By` | **Aceptado como riesgo: se documenta, sin reescribir el historial** | Ver §2.2 | Esta tabla y sección 6 de `docs/report.md` |
| H3 | kivora-reviewer | Media | `docs/report.md` desfasado: tags, estado, sesión de la fase 5, versión, tabla de historial | **Aceptado** | La memoria debe ser coherente con el repositorio | Tarea 6 (memoria) |
| H4 | kivora-reviewer | Media | `README.md` sin actualizar | **Aceptado** | Es un entregable obligatorio de la fase 6 | Tarea 3 (README) |
| H5 | kivora-reviewer | Media | `CLAUDE.md` sin `acceptance`, devoluciones, salidas de KIV-101 ni formatos de `refunds.json` | **Aceptado** | Un `CLAUDE.md` debe servir a una sesión nueva | Tarea 4 (`CLAUDE.md`, con confirmación expresa) |
| H6 | kivora-reviewer | Baja-media | Casos límite de robustez fuera de los datos actuales: `refunds.json` vacío, CSV con BOM, `--inbox` inexistente, devoluciones sin `refund_id` | **Rechazado el cambio de código: se documenta el riesgo** | Ver §2.3 | Esta tabla y sección 6 de `docs/report.md` |
| H7 | kivora-reviewer | Baja | La sesión de la fase 1 está en `docs/sesiones/` y las demás en `docs/sessions/` | **Aceptado** | Unificar evita problemas de mayúsculas entre sistemas | Tarea 5 (`git mv`), resuelto en `ac49701` |
| H8 | kivora-reviewer | Baja | La memoria versiona la ruta de una carpeta local de copias que incluye el nombre de usuario de Windows; las sesiones contienen rutas con ese mismo usuario | **Aceptado en parte** | Ver §2.4 | Tarea 6 (memoria); las sesiones no se editan |
| H9 | kivora-reviewer | Baja | La respuesta de `docs/tickets/KIV-101.md` dice «20 pruebas» y «28 comprobaciones», y hoy hay 51 y 49 | **Rechazado el cambio: se conservan las cifras históricas y se aclara su fase** | Ver §2.5 | Esta sección |
| H10 | Agente de la sesión (verificación de cierre, reflog) | Media | En la fase 1 se hizo un `commit --amend` sobre un commit que ya estaba en `origin` (`38e412b` pasó a `4e5b067`) y se reconcilió con un merge (`f8df7c9`) | **Aceptado como riesgo: se documenta, sin reescribir el historial** | Ver §2.6 | Esta tabla y secciones 6 y 7 de `docs/report.md` |

## 2. Detalle, evidencia y justificación

### 2.1 H1 · `daily_sales` y `top_customers` frente a su contrato (media-alta)

**Evidencia** (revisor, y comprobada también en esta sesión):

- El contrato (`docs/data-contracts/daily_sales.md`) exige `sales_date` en hora de `Europe/Madrid`, `gross_amount` en EUR, la **última versión** de cada pedido y la exclusión de cancelados o sin pago cobrado.
- `sql/daily_sales.sql` y `sql/staging.sql` no lo cumplen: suman `total_amount` sin convertir de moneda, calculan la fecha en UTC, aplican `DISTINCT` sobre la fila completa y unen con `stg_payments` y `stg_customers` de una forma que puede multiplicar o descartar pedidos.
- Con los 10 días de `data/inbox/`, `daily_sales.csv` suma **231 pedidos y 27.032,34**, mientras que el cálculo independiente (última versión, tipos de cambio, un pago cobrado basta) da **213 ventas y 25.072,41 €**, que es también lo que da `daily_customer_metrics.csv`. Cifras de `daily_sales.csv` comprobadas en esta sesión: 51 filas, 231 pedidos y 27.032,34.
- No es un hallazgo nuevo. El análisis de la fase 1 ya lo documentó (`docs/analysis.md`, secciones 3.1 y 4.3: conversión de moneda, zona horaria y deduplicación), la especificación de KIV-101 lo declaró limitación conocida (A-10 y RF-21) y la respuesta a Finanzas en `docs/tickets/KIV-101.md` lo comunica y propone un cambio aparte, y la memoria (`docs/report.md`, sección 1.5, decisión 1) registra que `daily_sales.sql` «no se modifica».

**Decisión: no modificar el pipeline. Se documenta el riesgo.**

**Justificación:**

1. **Ningún ticket ni requisito lo pide.** KIV-100 pedía entender y documentar el pipeline («en esta fase no se modifica código»). KIV-101 pide tres ficheros nuevos y el enunciado (§3.1) solo exige esos tres explícitamente. KIV-102 solo cambia el formato de `refunds.json`.
2. **Es una salida que consume otro equipo** (Dirección Comercial). Cambiar sus cifras sin ticket ni acuerdo introduciría una revisión de números que nadie ha pedido, que es justo el tipo de efecto que se avisó a Finanzas de evitar.
3. **Objetivo del proyecto:** terminar sin modificar innecesariamente el pipeline. Un cambio aquí tocaría `sql/`, tests y `acceptance`, con spec, plan y fase propios.
4. **Riesgo asumido y conocido:** si un corrector mide `daily_sales.csv` con datos desconocidos, el resultado no cumplirá el contrato. Se asume porque ese incumplimiento ya está documentado y comunicado desde la fase 1.

**Si se quisiera corregir:** sería un cambio aparte, con su propia especificación (`docs/specs/`), tests que fallen con el código actual, impacto sobre Dirección Comercial y commits propios. No se hace en esta práctica.

### 2.2 H2 · Commits de la fase 1 sin `Co-Authored-By` (media)

**Evidencia.** De los 34 commits, 27 llevan `Co-Authored-By`. Los 7 que no lo llevan:

| Commit | Contenido | Origen |
|---|---|---|
| `a882ccf`, `849b81e`, `443c977` | Commit inicial, proyecto y revisión del enunciado | Plantilla del profesor |
| `38e412b` | `Phase 1: analyze pipeline and document KIV-100` | Fase 1 |
| `4e5b067` | `Fase 1: análisis del pipeline y documentación de KIV-100` | Fase 1 |
| `4d88adb` | `Documentar sesión de Claude Code de la fase 1` (tag `phase-1`) | Fase 1 |
| `f8df7c9` | `Integrar historial remoto de la fase 1` (único merge del repositorio) | Fase 1 |

**Decisión: documentarlo, sin reescribir el historial.**

**Justificación:**

1. **Cronología.** Las reglas de Git de `CLAUDE.md` (mensajes en español, trailer `Co-Authored-By`, commits pequeños) se establecieron en `3a438a5`, que es posterior al tag `phase-1` (`4d88adb` es su ancestro). Esos commits son anteriores a la regla.
2. **Reescribir está prohibido.** El enunciado (§3.4) y `CLAUDE.md` prohíben reescribir la historia (`amend`, `rebase` y push forzado). Los tags `phase-N` existentes deben conservarse, y `phase-1` ya está publicado.
3. **Todos los commits posteriores a `3a438a5` llevan el trailer.** Se comprobó en la fase 5: los 11 commits de esa fase lo llevan.
4. **No se puede atribuir con certeza** si los commits de la fase 1 los escribió el agente o la persona (lo infiere el revisor por el mensaje y la fase). Se documenta tal como es.

### 2.3 H6 · Robustez ante entradas fuera de los datos actuales (baja-media)

**Evidencia** (revisor, ejecuciones sintéticas fuera del repositorio):

| Caso | Resultado |
|---|---|
| `refunds.json` de 0 bytes | Código 1 (`JSONDecodeError`) |
| `refunds.json` que no es una lista | Código 1 (`ValueError`, intencionado) |
| CSV con BOM | Código 1 (`KeyError`) |
| `--inbox` inexistente | Código 1 (`FileNotFoundError`) |
| Devoluciones sin `refund_id` (vacío o `null`) | Se agrupan como un único id y las siguientes se rechazan como `refund_id duplicado` |

Funcionan sin fallos: otras fechas (incluidos los cambios de hora de 2027), un día sin ficheros, `refunds.json` igual a `[]`, campos vacíos (cada pedido o devolución va a `rejected.csv` con motivo), moneda en minúsculas, importe con coma, determinismo, y ningún valor o id fijo en el código de producción.

**Decisión: no modificar el pipeline. Se documentan como límites conocidos.**

**Justificación:**

1. **Fuera del tipo de datos esperado.** El enunciado dice que los datos desconocidos tienen «el mismo formato y el mismo tipo de problemas» que los del repositorio: duplicados, nulos, devoluciones sin pedido, monedas distintas. Ningún caso de la tabla aparece en los datos actuales.
2. **El conjunto de motivos de `rejected.csv` es cerrado** (siete valores, KIV-101 §5.2). Rechazar las devoluciones sin `refund_id` exigiría un motivo nuevo y cambiar el contrato.
3. **Cada cambio requiere spec, tests y verificación,** y el objetivo es no modificar innecesariamente el pipeline. El riesgo (entradas malformadas) se detecta además con un código de salida distinto de 0 y un mensaje, no con un resultado erróneo silencioso, salvo el caso de las devoluciones sin `refund_id`, que se anota expresamente.

**Si se quisiera cubrir alguno,** el de menor riesgo sería tratar un `refunds.json` vacío como una lista vacía.

### 2.4 H8 · Datos personales en la memoria y en las sesiones (baja)

**Evidencia.** `docs/report.md` (secciones 5.7 y de evidencia de sesión) nombra la ruta completa de una carpeta local de copias (con el nombre de usuario de Windows). Las sesiones exportadas contienen rutas del tipo `C:\Users\<usuario>\...` (aproximadamente 24 veces en la de la fase 2, 66 en la de la fase 4 y 19 en la de la fase 5). El revisor no encontró claves, tokens, contraseñas ni correos reales (solo `noreply@anthropic.com` del trailer). El único dato personal es el nombre de usuario del sistema operativo.

**Decisión: aceptado en parte.**

- **`docs/report.md`:** se quitará la ruta personal y se sustituirá por «una carpeta local fuera del repositorio» (tarea 6). Es texto escrito por el agente y no hay motivo para publicarlo.
- **Sesiones exportadas:** **no se editan.** El enunciado exige exportarlas «sin editar». El nombre de usuario del sistema operativo no es un secreto ni identifica a nadie más allá de un nombre de cuenta local, y las sesiones de las fases 2 y 4 ya lo contienen y ya están publicadas.

### 2.5 H9 · Cifras de pruebas en la respuesta de KIV-101 (baja)

**Evidencia.** `docs/tickets/KIV-101.md` (respuesta) dice «`uv run python tasks.py test` (20 pruebas)» y «`acceptance` (28 comprobaciones)». Hoy hay 51 pruebas y 49 comprobaciones de `acceptance`.

**Decisión: conservar las cifras históricas. No se modifica el ticket.**

**Aclaración de fase:**

| Cifra | Corresponde a | Cifra actual (fase 5) |
|---|---|---|
| 20 pruebas | Fase 4 (cierre de KIV-101): 4 de `test_pipeline.py` y 16 de `test_kiv101.py` | 51 (los 20 anteriores y 31 de `tests/test_kiv102.py`) |
| 28 comprobaciones de `acceptance` | Fase 4: primera pasada, días hasta 2026-09-07 | 49: la misma primera pasada (28) y 21 de la segunda pasada de KIV-102 |

**Justificación:** la respuesta a Finanzas es un documento fechado de la fase 4 y esas cifras eran verdaderas entonces. Las cifras actuales están en `docs/tickets/KIV-102.md` y en la sección 5 de `docs/report.md`. Reescribir una respuesta histórica borraría la trazabilidad de cada fase.

### 2.6 H10 · `amend` de la fase 1 sobre un commit ya publicado (media)

**Cómo se detectó.** No lo encontró `kivora-reviewer`. Lo detectó el agente de la sesión al verificar el cierre de la fase 6: el reflog local tiene una entrada `commit (amend)`, y `git log` muestra el único merge del repositorio (el que ya cita H2).

**Evidencia** (`git reflog` y `git log`, hora local del 2026-11-05):

| Hora | Commit | Qué ocurrió |
|---|---|---|
| 20:28 | `38e412b` | `commit: Phase 1: analyze pipeline and document KIV-100` (mensaje en inglés) |
| 20:28 | `4e5b067` | `commit (amend): Fase 1: análisis del pipeline y documentación de KIV-100` (mismo contenido, mensaje en español) |
| 20:41 | `4d88adb` | `Documentar sesión de Claude Code de la fase 1` (tag `phase-1`) |
| 20:44 | `f8df7c9` | `merge origin/master: Merge made by the 'ours' strategy`. Padres: `4d88adb` y `38e412b` |
| 20:59 | `3a438a5` | **Primer commit con las reglas de Git de `CLAUDE.md`** |

El `38e412b` original ya estaba en `origin/master` (el merge se hizo contra `origin/master`). Hoy **los dos commits, `38e412b` y `4e5b067`, son alcanzables desde `origin/master`**, es decir, no se ha eliminado ningún commit publicado. Desde `3a438a5` hasta hoy el reflog no contiene ningún otro `amend`, `rebase` ni `reset`.

**Decisión: aceptado como riesgo. Se documenta y no se reescribe el historial.**

**Justificación:**

1. **Ocurrió antes de establecer las reglas de Git.** El `amend` es de las 20:28 y las reglas que prohíben reescribir el historial (`3a438a5`) son de las 20:59, en la fase 2. No incumple una regla que todavía no existía, aunque sí es lo que esas reglas evitan después.
2. **El historial se reconcilió, no se reescribió después.** La divergencia entre el commit publicado y el corregido se resolvió con un commit de integración (`f8df7c9`). No se ha eliminado ningún commit publicado y la historia de `origin` se conserva entera. Por eso conviven en el historial el commit en inglés y el corregido en español.
3. **No se va a reescribir.** El enunciado (§3.4) y `CLAUDE.md` prohíben reescribir la historia (`amend`, `rebase` y push forzado), y `phase-1` ya está publicado. Deshacerlo exigiría reescribir, que es peor que dejarlo documentado.
4. **Relación con H2.** Los mismos cuatro commits de la fase 1 (`38e412b`, `4e5b067`, `4d88adb` y `f8df7c9`) son los que no llevan `Co-Authored-By`: tienen la misma causa, que la fase 1 es anterior a las reglas.

**Límite de la evidencia.** El reflog es local de este clon: confirma el `amend` y la fecha, pero no puede demostrar por sí solo que nunca hubo un empuje forzado. Lo que sí se comprueba es que los dos commits siguen en `origin/master`.

## 3. Lo que el revisor verificó como correcto

- **Cifras:** todas las de los tickets KIV-101 y KIV-102 y de `docs/report.md`, con un cálculo independiente en Python con `Decimal`, sin reutilizar el código del repositorio:
  - Días 1 a 7: 156 ventas, 18.490,74 € brutos, 29 devoluciones por 1.310,19 €, 17.180,55 € netos y 115 filas.
  - Días 1 a 10: 213 ventas, 25.072,41 € brutos, 43 devoluciones por 1.642,04 €, 23.430,37 € netos y 164 filas.
  - Rechazos: `R-1003`, `R-1005`, `R-1006` y `R-1034`.
- **Pruebas y mutaciones:** los 7 casos que exige el enunciado tienen un test que falla con el código roto. Se aplicaron mutaciones reales (sin deduplicar, sin `UNKNOWN`, devoluciones que no acumulan, pedido inexistente sin rechazar, neto que ignora devoluciones, joins que multiplican, `ROUND_HALF_EVEN`, tipo de cambio ignorado, float, un solo formato de `refunds.json`, `refund_id` sin deduplicar y control C-3 desactivado) y las detectan los tests y `acceptance`. Dos mutaciones solo las detectan los tests unitarios y no `acceptance`: la prioridad entre `refund_amount` y `amount` y el control C-6, porque no hay datos reales que las ejerciten. `acceptance` es una señal de parada fiable para lo que cubre.
- **Robustez:** otras fechas, cambio de hora, día sin ficheros, `refunds.json` igual a `[]`, campos vacíos, determinismo, sin valores fijos en el código de producción y sin escrituras en `--inbox`.
- **Entrega:**
  - Tags `phase-1` a `phase-5` en orden y sobre el último commit de cada fase.
  - Spec y plan antes del código en las fases 2, 4 y 5; plan revisado antes de implementar; impacto antes del código en la fase 5.
  - Sin reescrituras de historial.
  - `data/inbox/` y `deliveries/` coinciden con las entregas.
  - Sin secretos ni ficheros prohibidos versionados.
  - Interfaz de ejecución intacta.
- **Configuración del agente:** `.claude/settings.json` válido, hook `kivora_guard` funcionando (bloqueó una orden de prueba) con sus 34 tests, y subagente de solo lectura.

## 4. Lo que el revisor no pudo verificar

- `claude doctor` y la carga real del hook por Claude Code (solo ejecutó el guard por entrada estándar y observó un bloqueo).
- Línea por línea los miles de líneas de `docs/analysis.md`, las especificaciones y las sesiones exportadas: verificó cifras e identificadores citados, tags e historial.
- Qué mide el script automático de corrección sobre `daily_sales.csv` y con qué datos desconocidos se ejecuta (relacionado con H1).
- La atribución exacta de los commits de la fase 1 sin trailer (H2).

## 5. Revisiones anteriores del proyecto

El mismo subagente revisó cada documento principal antes de commitearlo. Estas revisiones ya están registradas en la memoria (secciones 1 y 5) y se resumen aquí.

| Revisión | Hallazgos | Resultado |
|---|---|---|
| Plan de KIV-101 (fase 2) | 5 incidencias de cifras que no cuadraban con los datos | Corregidas en `spec.md`, `plan.md` y `report.md` (commit `f37e4ee`) |
| `spec.md` y `plan.md` de KIV-101 (fase 4, antes del código) | Entre otros, un caso no previsto señalado por el revisor independiente (devolución sobre un pedido sin pago cobrado, que dio lugar a RF-23; hallazgos 8 y 15 de la memoria) | Incorporados antes del código (commit `642e773`) |
| `impact.md` de KIV-102 | 1 media y 6 bajas | Aplicadas antes de commitear (commit `677fc96`) |
| `spec.md` de KIV-102 | 5 medias y 3 bajas | Aplicadas, salvo una regla sobre importes cero o negativos que no se autorizó (A-10) (commit `4642b3b`) |
| `plan.md` de KIV-102 | 13 cambios, entre ellos tres tests marcados como rojos que pasaban con el código actual | Aplicados antes de commitear (commit `a644c23`) |
| Código y memoria de KIV-102 (fase 5) | 0 altas y 0 medias; 2 bajas | Sin cambios necesarios: un caso límite coherente con la spec y una etiqueta cosmética de `acceptance` |
| **Revisión final del proyecto (esta)** | 9 hallazgos del revisor (1 media-alta, 4 medias, 1 baja-media y 3 bajas) y 1 más (H10, media) detectado en la verificación de cierre | Ver §1 |

## 6. Estado de aplicación de los cambios aceptados

| Hallazgo | Cambio | Archivo | Estado |
|---|---|---|---|
| H3 | Actualizar cabecera, estado, historial y referencias obsoletas | `docs/report.md` | Hecho (tarea 6, memoria v1.0) |
| H4 | Reescribir el README | `README.md` | Hecho (commit `85a49b2`) |
| H5 | Añadir `acceptance`, devoluciones, salidas de KIV-101 y formatos de `refunds.json` | `CLAUDE.md` | Hecho (commit `1a4d610`, con confirmación expresa) |
| H7 | Mover la sesión de la fase 1 a `docs/sessions/` | `docs/sesiones/fase-1-sesion-claude.md` | **Resuelto** (commit `ac49701`: `git mv`, renombrado al 100 %, SHA-256 idéntico) |
| H8 | Quitar la ruta personal de la memoria; no editar las sesiones | `docs/report.md` | Hecho (tarea 6, memoria v1.0); las sesiones no se editaron |
| H1, H2, H6, H9, H10 | Documentados en este archivo; sin cambios de código, de historial ni del ticket | `docs/review.md` | Hecho en este documento |
| H1, H2, H6 | Resumir los riesgos asumidos en la sección 6 de la memoria | `docs/report.md` | Hecho (tarea 6, memoria v1.0: sección 6) |
| H10 | Referencia en las secciones 6 y 7 de la memoria | `docs/report.md` | Hecho (cierre de la fase 6) |

Fuera de esta revisión queda, por decisión expresa, no añadir `*.jsonl` a `.gitignore` (el hook del guard ya bloquea su commit).
