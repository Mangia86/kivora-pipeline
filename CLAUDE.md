# Kivora pipeline

Pipeline diario de ventas de la tienda online Kivora.

## Qué hace

Lee las entregas diarias de `data/inbox/` (pedidos, clientes y pagos), las carga
en SQLite, aplica transformaciones SQL y escribe tablas de negocio en `output/`:
`daily_sales.csv` y `top_customers.csv`. La base intermedia es
`output/warehouse.db`.

## Comandos (interfaz de ejecución, no se puede cambiar)

- Ejecutar el pipeline:
  `uv run python -m kivora --inbox data/inbox --reference data/reference --out output`
  (equivalente a `python tasks.py run`).
- Ejecutar los tests:
  `uv run python tasks.py test` (usa pytest, no unittest).
- Comprobaciones básicas de salida:
  `uv run python tasks.py check`.
- Recibir una entrega de la tienda:
  `uv run python tasks.py deliver N` (N = 1 o 2).
- Borrar `output/`:
  `uv run python tasks.py reset`.

## Reglas del proyecto

- `data/inbox/` y `deliveries/` **no se modifican nunca**. Los problemas de los
  datos se resuelven en el pipeline.
- Los importes **no** vienen todos en euros: hay pedidos en USD y GBP. Se
  convierten a EUR con `data/reference/fx_rates.csv`.
- Las consultas SQL están en `sql/`, no en `queries/`.
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
- `uv run python tasks.py check` pasa sobre `output/`.
- El resultado cumple los contratos de datos en
  `docs/data-contracts/` (por ejemplo, `daily_sales.md`).
- Se han documentado las decisiones y las pruebas en `docs/`.
