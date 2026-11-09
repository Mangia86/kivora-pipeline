"""KIV-101: daily_customer_metrics.csv, rejected.csv and quality_report.json.

sql/daily_customer_metrics.sql only selects records (money travels as text). Here, with decimal.Decimal:
the conversion to EUR, the Europe/Madrid date, the aggregation, the net amount and the quality controls.
Specification: docs/specs/KIV-101/spec.md (RNF-2: no float or SQLite arithmetic for money; RF-21: Madrid).
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
CENT = Decimal("0.01")
METRIC_COLUMNS = ["metric_date", "customer_id", "country", "orders_count", "gross_amount",
                  "refunded_amount", "net_amount", "refunds_count", "last_purchase_date"]
REJECTED_COLUMNS = ["source", "record_id", "reason"]
OUTPUTS = ["daily_customer_metrics.csv", "rejected.csv", "quality_report.json"]


class Reject(Exception):
    """A record that cannot be used: it goes to rejected.csv with this reason."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def load_rates(conn):
    rates = {}
    for currency, rate in conn.execute("SELECT currency, rate_to_eur FROM ref_fx_rates"):
        try:
            value = Decimal((rate or "").strip())
        except InvalidOperation:
            continue
        if value.is_finite() and (currency or "").strip():
            rates[currency.strip().upper()] = value
    return rates


def to_eur(amount, currency, rates):
    """Amount (text) in `currency` to EUR with two decimals, ROUND_HALF_UP."""
    rate = rates.get((currency or "").strip().upper())
    if rate is None:
        raise Reject("moneda no soportada")
    try:
        value = Decimal((amount or "").strip())
    except InvalidOperation:
        raise Reject("importe no valido") from None
    if not value.is_finite():
        raise Reject("importe no valido")
    return (value * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def madrid_date(created_at):
    """Date of a UTC timestamp in Europe/Madrid (summer time included)."""
    try:
        moment = datetime.fromisoformat((created_at or "").strip().replace("Z", "+00:00"))
    except ValueError:
        raise Reject("fecha no valida") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(MADRID).date().isoformat()


def money(value):
    return f"{value:.2f}"


def build(conn):
    """Return (metric rows, rejected rows, quality checks) from the kpi_* tables."""
    rates = load_rates(conn)
    rejected = [(source, record_id or "", reason)
                for source, record_id, reason in conn.execute("SELECT source, record_id, reason FROM kpi_rejected")]

    sales, order_info, order_rejects = [], {}, {}
    rejected_orders = 0
    for order_id, customer_id, created_at, currency, total, country in conn.execute(
            "SELECT order_id, customer_id, created_at, currency, total_amount, country "
            "FROM kpi_valid_orders ORDER BY order_id"):
        try:
            sale = (order_id, customer_id or "", madrid_date(created_at), to_eur(total, currency, rates), country)
        except Reject as exc:
            rejected.append(("orders", order_id or "", exc.reason))
            order_rejects[order_id] = exc.reason
            rejected_orders += 1
            continue
        sales.append(sale)  # one entry per row read: a duplicated join row would be counted (and caught by C-6)
        order_info[order_id] = sale

    refunds = []
    for refund_id, order_id, currency, amount in conn.execute(
            "SELECT refund_id, order_id, currency, amount FROM kpi_refunds ORDER BY refund_id"):
        if order_id in order_rejects:  # its order could not be used, so the refund cannot be attributed
            rejected.append(("refunds", refund_id or "", order_rejects[order_id]))
            continue
        try:
            refunds.append((refund_id, order_id, to_eur(amount, currency, rates)))
        except Reject as exc:
            rejected.append(("refunds", refund_id or "", exc.reason))

    cells = defaultdict(lambda: {"orders": 0, "gross": Decimal("0.00"), "refunded": Decimal("0.00"),
                                 "refunds": 0, "country": "UNKNOWN"})
    purchase_dates = defaultdict(set)
    for _, customer_id, date, eur, country in sales:
        cell = cells[(date, customer_id)]
        cell["orders"] += 1
        cell["gross"] += eur
        cell["country"] = country
        purchase_dates[customer_id].add(date)
    refunded_per_order = defaultdict(lambda: Decimal("0.00"))
    for refund_id, order_id, eur in refunds:
        _, customer_id, date, _, _ = order_info[order_id]  # refunds go to the purchase day of their order
        cell = cells[(date, customer_id)]
        cell["refunded"] += eur
        cell["refunds"] += 1
        refunded_per_order[order_id] += eur

    rows = []
    for (date, customer_id), cell in sorted(cells.items()):
        last = max(d for d in purchase_dates[customer_id] if d <= date)
        rows.append({"metric_date": date, "customer_id": customer_id, "country": cell["country"],
                     "orders_count": cell["orders"], "gross_amount": money(cell["gross"]),
                     "refunded_amount": money(cell["refunded"]), "net_amount": money(cell["gross"] - cell["refunded"]),
                     "refunds_count": cell["refunds"], "last_purchase_date": last})

    expected_sales = conn.execute("SELECT n FROM kpi_valid_count").fetchone()[0]
    accounted = sum(r["orders_count"] for r in rows) + rejected_orders
    rejected.sort()
    checks = [
        ("net_amount_equals_gross_minus_refunded",
         sum(1 for r in rows if Decimal(r["gross_amount"]) - Decimal(r["refunded_amount"]) != Decimal(r["net_amount"]))),
        ("net_amount_not_negative_anomaly", sum(1 for r in rows if Decimal(r["net_amount"]) < 0)),
        ("refunded_not_exceeds_gross_per_order",
         sum(1 for order_id, total in refunded_per_order.items() if total > order_info[order_id][3])),
        ("no_duplicate_refund_ids", len(refunds) - len({refund_id for refund_id, _, _ in refunds})),
        ("all_rejected_records_have_reason", sum(1 for _, _, reason in rejected if not reason)),
        ("orders_reconcile_with_valid_sales", abs(expected_sales - accounted)),
    ]
    return rows, rejected, checks


def write_outputs(out, rows, rejected, checks):
    with open(out / "daily_customer_metrics.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=METRIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with open(out / "rejected.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(REJECTED_COLUMNS)
        writer.writerows(rejected)
    report = {"checks": [{"name": name, "passed": failed == 0, "failed_records": failed} for name, failed in checks]}
    with open(out / "quality_report.json", "w", encoding="utf-8", newline="") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


def run(conn, out):
    """Build and write the three KIV-101 outputs. Quality anomalies never change the exit code."""
    rows, rejected, checks = build(conn)
    write_outputs(out, rows, rejected, checks)
    return {"rows": len(rows), "rejected": len(rejected), "failed_checks": [n for n, failed in checks if failed]}
