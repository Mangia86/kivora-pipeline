# Kivora pipeline

Pipeline diario de ventas de la tienda online Kivora.

## Qué hace

Lee las entregas diarias de `data/inbox/` (pedidos, clientes, pagos y devoluciones),
las carga en SQLite, aplica transformaciones SQL y Python y escribe tablas de negocio
en `output/`: `daily_sales.csv` y `top_customers.csv` (heredadas),
`daily_customer_metrics.csv`, `rejected.csv` y `quality_report.json` (KIV-101). La
base intermedia es `output/warehouse.db`. Estado: KIV-100, KIV-101 y KIV-102 cerrados
(10 días en `data/inbox/`).

## Comandos (interfaz de ejecución, no se puede cambiar)

- Ejecutar el pipeline:
  `uv run python -m kivora --inbox data/inbox --reference data/reference --out output`
  (equivalente a `python tasks.py run`).
- Ejecutar los tests:
  `uv run python tasks.py test` (usa pytest, no unittest).
- Comprobaciones básicas de salida:
  `uv run python tasks.py check`.
- Oráculo de aceptación: `uv run python tasks.py acceptance` (dos pasadas: 28
  comprobaciones de KIV-101 con los días hasta 2026-09-07 y 21 de KIV-102 con todos
  los días; código 0 solo si pasan todas).
- Recibir una entrega de la tienda:
  `uv run python tasks.py deliver N` (N = 1 o 2; ya están recibidas las dos).
- Borrar `output/`:
  `uv run python tasks.py reset`.

## Reglas del proyecto

- `data/inbox/` y `deliveries/` **no se modifican nunca**. Los problemas de los
  datos se resuelven en el pipeline.
- Los importes **no** vienen todos en euros: hay pedidos en USD y GBP. Se
  convierten a EUR con `data/reference/fx_rates.csv`.
- Las consultas SQL están en `sql/`, no en `queries/`.
- **`refunds.json` tiene dos formatos que conviven** (`docs/sources.md`): hasta
  2026-09-07 el importe es `amount`; desde 2026-09-08 es `refund_amount` y llega
  `reason` (texto libre o `null`). El formato se decide por registro; manda
  `refund_amount`; sin importe, el registro va a `rejected.csv` (`importe no valido`).
  `reason` solo se guarda en `raw_refunds` y no se publica en ninguna salida.
- Contrato de las salidas de KIV-101: `docs/specs/KIV-101/spec.md`, sección 5. Cambios
  de KIV-102 (formato de `refunds.json`): `docs/specs/KIV-102/`.
- Limitación conocida y aceptada: `daily_sales.csv` y `top_customers.csv` no cumplen del
  todo su contrato (ver `docs/review.md`, H1). No se tocan sin un ticket y una
  especificación propios; las cifras fiables están en `daily_customer_metrics.csv`.
- Para cambiar el pipeline: impacto, especificación y plan commiteados antes del código;
  tests y `acceptance` en rojo con el código anterior; después, la implementación mínima.

## Reglas de Git

- El historial debe reflejar el progreso real del desarrollo.
- Realiza commits pequeños, reales y frecuentes durante cada fase.
- Los commits realizados como agente conservan la línea `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- Los mensajes de commit se escriben en español.
- No reescribas el historial: no uses `amend`, no hagas `rebase` para modificar commits publicados ni `push --force`.
- Solicita autorización antes de ejecutar commits y push.
- Conserva los tags `phase-N` existentes y crea nuevos únicamente al cerrar cada fase.
- No modifiques nunca `data/inbox/` ni `deliveries/`, salvo la incorporación de entregas mediante el procedimiento indicado en `assignment.md`.

## Protecciones del agente (fase 3)

- `.claude/settings.json` fija los permisos (qué se pregunta y qué se deniega) y registra el hook `kivora_guard`
  (`.claude/hooks/kivora_guard.py`), que **bloquea antes de ejecutar**: escribir en `data/inbox/` o `deliveries/`;
  reescribir el historial (`--amend`, `rebase`, `reset --hard`, push forzado, push a un remoto que no sea `origin`, borrar
  tags); commits sin `Co-Authored-By`, con `-a`, junto a `git add` en la misma orden o con `.jsonl`/`.env`/`output/` en el
  índice; tocar `kivora/`, `sql/`, `tests/` o `tasks.py` antes de que lo permitan la fase y los documentos ya commiteados
  (spec, plan revisado, impacto); `tasks.py deliver N` fuera de su fase; dejar `settings.json` inválido.
- Haz `git add` y `git commit` en órdenes separadas y con el trailer dentro de `-m`.
- Si el guard bloquea algo, no lo eludas con otra orden: explica el motivo y pide la decisión a la persona.
- Tras redactar spec, plan, report o código, pide una revisión independiente al subagente `kivora-reviewer` (solo lectura).
- Probar el guard: `uv run python -m pytest .claude/hooks -q`. Validar la configuración: `claude doctor`.
- Recuperación (solo una persona): `{"disableAllHooks": true}` en `.claude/settings.local.json` (no se versiona); corregir,
  validar con `claude doctor` y quitar esa línea.

## Cómo se sabe que un trabajo está terminado

- `uv run python tasks.py test` pasa (código de salida 0).
- `uv run python tasks.py acceptance` pasa en sus dos pasadas (código de salida 0).
- `uv run python tasks.py check` pasa sobre `output/`.
- Los tests nuevos fallan con el código anterior y pasan con el nuevo; los de las fases
  anteriores siguen en verde (sin regresiones).
- Dos ejecuciones sobre los mismos datos dan ficheros idénticos, y un cambio no altera
  las salidas que no le corresponden (comparar con la ejecución anterior).
- El resultado cumple los contratos de datos en
  `docs/data-contracts/` (por ejemplo, `daily_sales.md`) y en `docs/specs/`.
- Se han documentado las decisiones y las pruebas en `docs/`, y el cambio ha pasado por
  una revisión independiente de `kivora-reviewer`.
