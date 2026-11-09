"""Basic checks on output/ (python tasks.py check)."""

import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

OUTPUT = Path("output")
EXPECTED = {
    "daily_sales.csv": ["sales_date", "country", "orders_count", "gross_amount"],
    "top_customers.csv": ["customer_id", "orders_count", "gross_amount"],
}
# KIV-101 outputs (docs/specs/KIV-101/spec.md, section 5).
METRIC_COLUMNS = ["metric_date", "customer_id", "country", "orders_count", "gross_amount",
                  "refunded_amount", "net_amount", "refunds_count", "last_purchase_date"]
REJECTED_COLUMNS = ["source", "record_id", "reason"]
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MONEY = re.compile(r"-?\d+\.\d{2}")


def _read(name, columns, problems):
    path = OUTPUT / name
    if not path.exists():
        problems.append(f"falta {path}: ejecuta antes python tasks.py run")
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in columns if c not in (reader.fieldnames or [])]
        if missing:
            problems.append(f"{name}: faltan columnas {missing}")
            return None
        return list(reader)


def check_metrics(problems):
    rows = _read("daily_customer_metrics.csv", METRIC_COLUMNS, problems)
    seen = set()
    for line, row in enumerate(rows or [], start=2):
        where = f"daily_customer_metrics.csv:{line}"
        for column in ("metric_date", "last_purchase_date"):
            if not DATE.fullmatch(row[column]):
                problems.append(f"{where}: {column} no es AAAA-MM-DD ({row[column]!r})")
        for column in ("gross_amount", "refunded_amount", "net_amount"):
            if not MONEY.fullmatch(row[column]):
                problems.append(f"{where}: {column} no es un importe con dos decimales ({row[column]!r})")
        for column in ("orders_count", "refunds_count"):
            if not row[column].isdigit():
                problems.append(f"{where}: {column} no es un entero >= 0 ({row[column]!r})")
        try:  # a negative net_amount is a business anomaly reported by C-2, not a format error
            if Decimal(row["gross_amount"]) - Decimal(row["refunded_amount"]) != Decimal(row["net_amount"]):
                problems.append(f"{where}: net_amount != gross_amount - refunded_amount")
        except InvalidOperation:
            pass
        if row["last_purchase_date"] > row["metric_date"]:
            problems.append(f"{where}: last_purchase_date posterior a metric_date")
        key = (row["metric_date"], row["customer_id"])
        if key in seen:
            problems.append(f"{where}: fila repetida para {key}")
        seen.add(key)


def check_rejected(problems):
    for line, row in enumerate(_read("rejected.csv", REJECTED_COLUMNS, problems) or [], start=2):
        if not row["reason"].strip():
            problems.append(f"rejected.csv:{line}: reason vacio")


def check_quality_report(problems):
    path = OUTPUT / "quality_report.json"
    if not path.exists():
        problems.append(f"falta {path}: ejecuta antes python tasks.py run")
        return
    try:
        checks = json.loads(path.read_text(encoding="utf-8"))["checks"]
    except (ValueError, KeyError, TypeError):
        problems.append("quality_report.json: no tiene la forma {\"checks\": [...]}")
        return
    if not isinstance(checks, list) or len(checks) < 2:
        problems.append("quality_report.json: hacen falta al menos dos controles")
        return
    for item in checks:
        if not (isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("passed"), bool)
                and isinstance(item.get("failed_records"), int) and item["failed_records"] >= 0
                and item["passed"] == (item["failed_records"] == 0)):
            problems.append(f"quality_report.json: control mal formado: {item!r}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    problems = []
    for name, columns in EXPECTED.items():
        path = OUTPUT / name
        if not path.exists():
            problems.append(f"falta {path}: ejecuta antes python tasks.py run")
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in columns if c not in (reader.fieldnames or [])]
            if missing:
                problems.append(f"{name}: faltan columnas {missing}")
                continue
            for line, row in enumerate(reader, start=2):
                if float(row["gross_amount"]) < 0:
                    problems.append(f"{name}:{line}: gross_amount negativo")
    check_metrics(problems)
    check_rejected(problems)
    check_quality_report(problems)
    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        return 1
    print("OK: output/ tiene los ficheros, columnas y formatos esperados (incluidas las salidas de KIV-101)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
