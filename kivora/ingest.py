"""Load the raw sources into SQLite, as text, without cleaning anything."""

import csv
import json
from pathlib import Path

SOURCES = {
    "orders": ["order_id", "customer_id", "created_at", "updated_at", "status",
               "currency", "total_amount"],
    "customers": ["customer_id", "name", "country", "signup_date"],
    "payments": ["payment_id", "order_id", "paid_at", "method", "status", "amount"],
}
# refunds.json is a list of objects; amounts are kept as the text they have in the file.
REFUND_COLUMNS = ["refund_id", "order_id", "refunded_at", "amount", "currency"]


def _create(conn, table, columns):
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"CREATE TABLE {table} ({', '.join(c + ' TEXT' for c in columns)})")


def _load_refunds(conn, day):
    """Load `refunds.json` of one day (days without refunds do not bring the file)."""
    path = day / "refunds.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        # parse_float/parse_int keep the number exactly as written (no binary floats for money)
        refunds = json.load(fh, parse_float=str, parse_int=str)
    if not isinstance(refunds, list):
        raise ValueError(f"{path}: se esperaba una lista JSON de devoluciones")
    rows = [[("" if r.get(c) is None else str(r.get(c))) for c in REFUND_COLUMNS] + [day.name]
            for r in refunds if isinstance(r, dict)]
    placeholders = ", ".join("?" for _ in range(len(REFUND_COLUMNS) + 1))
    conn.executemany(f"INSERT INTO raw_refunds VALUES ({placeholders})", rows)


def load_inbox(conn, inbox):
    """One raw_<source> table per source, with the day folder in `_day`."""
    for name, columns in SOURCES.items():
        _create(conn, f"raw_{name}", columns + ["_day"])
    _create(conn, "raw_refunds", REFUND_COLUMNS + ["_day"])
    days = sorted(p for p in Path(inbox).iterdir() if p.is_dir())
    for day in days:
        for name, columns in SOURCES.items():
            path = day / f"{name}.csv"
            if not path.exists():
                continue
            with open(path, encoding="utf-8", newline="") as fh:
                rows = [[row[c] for c in columns] + [day.name] for row in csv.DictReader(fh)]
            placeholders = ", ".join("?" for _ in range(len(columns) + 1))
            conn.executemany(f"INSERT INTO raw_{name} VALUES ({placeholders})", rows)
        _load_refunds(conn, day)
    conn.commit()
    return [d.name for d in days]


def load_reference(conn, reference):
    _create(conn, "ref_fx_rates", ["currency", "rate_to_eur"])
    with open(Path(reference) / "fx_rates.csv", encoding="utf-8", newline="") as fh:
        rows = [[row["currency"], row["rate_to_eur"]] for row in csv.DictReader(fh)]
    conn.executemany("INSERT INTO ref_fx_rates VALUES (?, ?)", rows)
    conn.commit()
