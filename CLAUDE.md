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
- El historial de Git es parte de la entrega: commits frecuentes, sin reescribir
  historia, y un tag `phase-N` al cerrar cada fase.

## Cómo se sabe que un trabajo está terminado

- `python tasks.py test` pasa (código de salida 0).
- `python tasks.py check` pasa sobre `output/`.
- El resultado cumple los contratos de datos en
  `docs/data-contracts/` (por ejemplo, `daily_sales.md`).
- Se han documentado las decisiones y las pruebas en `docs/`.
