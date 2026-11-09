"""Tests of KIV-101: daily_customer_metrics.csv, rejected.csv and quality_report.json.

They use small synthetic inboxes, so each test checks one rule and would fail if that rule were broken.
"""

import csv
import itertools
import json
import sqlite3
from decimal import Decimal

from kivora import metrics
from kivora.__main__ import main
from kivora.pipeline import run

ORDER_COLS = ["order_id", "customer_id", "created_at", "updated_at", "status", "currency", "total_amount"]
PAYMENT_COLS = ["payment_id", "order_id", "paid_at", "method", "status", "amount"]
CUSTOMER_COLS = ["customer_id", "name", "country", "signup_date"]
_ids = itertools.count(1)


def order(order_id, customer="C1", created="2026-09-01T10:00:00Z", updated=None, status="confirmed",
          currency="EUR", total="10.00"):
    return {"order_id": order_id, "customer_id": customer, "created_at": created, "updated_at": updated or created,
            "status": status, "currency": currency, "total_amount": total}


def pay(order_id, status="captured", amount="10.00"):
    return {"payment_id": f"P-{next(_ids)}", "order_id": order_id, "paid_at": "2026-09-01T10:01:00Z",
            "method": "card", "status": status, "amount": amount}


def customer(customer_id="C1", country="ES", name="Ana"):
    return {"customer_id": customer_id, "name": name, "country": country, "signup_date": "2025-01-01"}


def refund(refund_id, order_id, amount, currency="EUR"):
    return {"refund_id": refund_id, "order_id": order_id, "refunded_at": "2026-09-05T12:00:00Z",
            "amount": amount, "currency": currency}


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class Result:
    def __init__(self, out):
        self.out = out

    def read(self, name):
        with open(self.out / name, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    @property
    def metrics(self):
        return self.read("daily_customer_metrics.csv")

    @property
    def rejected(self):
        return {(r["source"], r["record_id"], r["reason"]) for r in self.read("rejected.csv")}

    @property
    def checks(self):
        report = json.loads((self.out / "quality_report.json").read_text(encoding="utf-8"))
        return {c["name"]: (c["passed"], c["failed_records"]) for c in report["checks"]}

    def row(self, date, customer_id):
        rows = [r for r in self.metrics if r["metric_date"] == date and r["customer_id"] == customer_id]
        assert len(rows) <= 1, f"fila repetida para {date}/{customer_id}"
        return rows[0] if rows else None


def run_pipeline(tmp_path, days, out="out"):
    """days = {"2026-09-01": {"orders": [...], "payments": [...], "customers": [...], "refunds": [...] or None}}"""
    inbox = tmp_path / "inbox"
    for day, content in days.items():
        folder = inbox / day
        folder.mkdir(parents=True)
        write_csv(folder / "orders.csv", ORDER_COLS, content.get("orders", []))
        write_csv(folder / "payments.csv", PAYMENT_COLS, content.get("payments", []))
        write_csv(folder / "customers.csv", CUSTOMER_COLS, content.get("customers", []))
        if content.get("refunds") is not None:  # days without refunds do not bring the file
            (folder / "refunds.json").write_text(json.dumps(content["refunds"]), encoding="utf-8")
    reference = tmp_path / "reference"
    reference.mkdir(exist_ok=True)
    write_csv(reference / "fx_rates.csv", ["currency", "rate_to_eur"],
              [{"currency": "EUR", "rate_to_eur": "1.0"}, {"currency": "GBP", "rate_to_eur": "1.17"},
               {"currency": "USD", "rate_to_eur": "0.92"}])
    run(inbox, reference, tmp_path / out)
    return Result(tmp_path / out)


def test_duplicate_orders_and_versions_count_once(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="10.00"), order("K-1", total="10.00")],
                       "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-02": {"orders": [order("K-1", updated="2026-09-02T09:00:00Z", total="20.00")]},
    })
    row = result.row("2026-09-01", "C1")
    assert row["orders_count"] == "1" and row["gross_amount"] == "20.00"  # latest version, once


def test_null_country_and_unknown_customer_become_unknown(tmp_path):
    result = run_pipeline(tmp_path, {"2026-09-01": {
        "orders": [order("K-1", "C1"), order("K-2", "C2")], "payments": [pay("K-1"), pay("K-2")],
        "customers": [customer("C1", country="")]}})  # C1 without country, C2 without a customers row
    assert result.row("2026-09-01", "C1")["country"] == "UNKNOWN"
    assert result.row("2026-09-01", "C2")["country"] == "UNKNOWN"  # the sale is not lost


def test_partial_refund_is_attributed_to_the_purchase_day(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="100.00")], "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 30.0)]}})
    row = result.row("2026-09-01", "C1")
    assert (row["gross_amount"], row["refunded_amount"], row["net_amount"], row["refunds_count"]) == \
        ("100.00", "30.00", "70.00", "1")
    assert result.row("2026-09-05", "C1") is None


def test_several_refunds_on_one_order_accumulate_without_duplicating_it(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="100.00")], "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 10.0), refund("R-2", "K-1", 15.5)]}})
    row = result.row("2026-09-01", "C1")
    assert (row["orders_count"], row["refunded_amount"], row["net_amount"], row["refunds_count"]) == \
        ("1", "25.50", "74.50", "2")


def test_refund_without_order_is_rejected_and_not_counted(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1")], "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-05": {"refunds": [refund("R-9", "K-999", 25.0)]}})
    assert ("refunds", "R-9", "pedido no encontrado") in result.rejected
    assert result.row("2026-09-01", "C1")["refunded_amount"] == "0.00"


def test_net_amount_with_currency_conversion_and_half_up_rounding(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", "C1", currency="USD", total="100.00"),
                                  order("K-2", "C2", total="0.125"),  # exact half cent: a float would give 0.12
                                  order("K-3", "C3", currency="GBP", total="10.00")],
                       "payments": [pay("K-1"), pay("K-2"), pay("K-3")],
                       "customers": [customer("C1"), customer("C2"), customer("C3")]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 60.0, "USD")]}})
    c1 = result.row("2026-09-01", "C1")
    assert (c1["gross_amount"], c1["refunded_amount"], c1["net_amount"]) == ("92.00", "55.20", "36.80")
    assert result.row("2026-09-01", "C2")["gross_amount"] == "0.13"
    assert result.row("2026-09-01", "C3")["gross_amount"] == "11.70"


def test_payments_validate_the_sale_but_never_multiply_it(tmp_path):
    result = run_pipeline(tmp_path, {"2026-09-01": {
        "orders": [order("K-1", "C1", total="50.00"), order("K-2", "C2")],
        "payments": [pay("K-1", amount="20.00"), pay("K-1", amount="30.00"), pay("K-1", "failed", "50.00"),
                     pay("K-2", "failed")],  # K-2 has no captured payment
        "customers": [customer("C1"), customer("C2")]}})
    row = result.row("2026-09-01", "C1")
    assert row["orders_count"] == "1" and row["gross_amount"] == "50.00"  # order total, not the sum of payments
    assert result.row("2026-09-01", "C2") is None  # not a sale...
    assert not any(source == "orders" for source, _, _ in result.rejected)  # ...but not a rejection either


def test_customer_versions_do_not_duplicate_orders_and_the_latest_wins(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", created="2026-09-01T10:00:00Z")], "payments": [pay("K-1")],
                       "customers": [customer(country="ES", name="Ana")]},
        "2026-09-02": {"customers": [customer(country="ES", name="Ana Ruiz")]},
        "2026-09-03": {"orders": [order("K-2", created="2026-09-03T10:00:00Z")], "payments": [pay("K-2")],
                       "customers": [customer(country="FR", name="Ana Ruiz")]}})
    rows = result.metrics
    assert [(r["metric_date"], r["orders_count"], r["country"]) for r in rows] == \
        [("2026-09-01", "1", "FR"), ("2026-09-03", "1", "FR")]  # one row per order and the latest country
    assert result.checks["orders_reconcile_with_valid_sales"] == (True, 0)


def test_empty_country_in_the_latest_customer_version_is_unknown(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1")], "payments": [pay("K-1")], "customers": [customer(country="ES")]},
        "2026-09-02": {"customers": [customer(country="")]}})
    assert result.row("2026-09-01", "C1")["country"] == "UNKNOWN"


def test_metric_date_is_the_europe_madrid_date(tmp_path):
    cases = {"C1": ("2026-07-01T21:59:59Z", "2026-07-01"), "C2": ("2026-07-01T22:00:00Z", "2026-07-02"),  # UTC+2
             "C3": ("2026-12-01T22:59:59Z", "2026-12-01"), "C4": ("2026-12-01T23:00:00Z", "2026-12-02")}  # UTC+1
    orders = [order(f"K-{c}", c, created=created) for c, (created, _) in cases.items()]
    result = run_pipeline(tmp_path, {
        "2026-07-01": {"orders": orders, "payments": [pay(o["order_id"]) for o in orders],
                       "customers": [customer(c) for c in cases]},
        "2026-12-05": {"refunds": [refund("R-1", "K-C2", 4.0)]}})
    for c, (_, expected) in cases.items():
        assert result.row(expected, c) is not None, f"{c} debería estar el {expected}"
    assert result.row("2026-07-02", "C2")["refunded_amount"] == "4.00"  # refunds follow the order's Madrid date
    assert result.row("2026-07-02", "C2")["last_purchase_date"] == "2026-07-02"


def test_rejected_records_have_an_explicit_reason(tmp_path):
    orders = [order("K-1", "C1", status="cancelled"), order("K-2", "C2"), order("K-3", "C3"),
              order("K-4", "C4", currency="JPY"), order("K-5", "C5", total="abc"),
              order("K-6", "C6", created="no-es-una-fecha")]
    payments = [pay("K-1"), pay("K-2", "failed"), pay("K-3"), pay("K-4"), pay("K-5"), pay("K-6")]
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": orders, "payments": payments, "customers": [customer(f"C{i}") for i in range(1, 7)]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 1.0), refund("R-2", "K-2", 2.0), refund("R-3", "K-3", 3.0),
                                   refund("R-4", "K-3", 4.0, "JPY"), refund("R-5", "K-3", "abc"),
                                   refund("R-6", "K-4", 6.0)]},
        "2026-09-06": {"refunds": [refund("R-3", "K-3", 3.0)]}})
    assert result.rejected == {
        ("refunds", "R-1", "pedido cancelado"), ("refunds", "R-2", "pedido sin pago cobrado"),
        ("refunds", "R-3", "refund_id duplicado"), ("refunds", "R-4", "moneda no soportada"),
        ("refunds", "R-5", "importe no valido"), ("refunds", "R-6", "moneda no soportada"),
        ("orders", "K-4", "moneda no soportada"), ("orders", "K-5", "importe no valido"),
        ("orders", "K-6", "fecha no valida")}  # cancelled and unpaid ORDERS are not rejections (A-9)
    assert result.row("2026-09-01", "C3")["refunded_amount"] == "3.00"  # the first R-3 counts once
    assert result.checks["orders_reconcile_with_valid_sales"] == (True, 0)
    assert result.checks["all_rejected_records_have_reason"] == (True, 0)


def test_refund_larger_than_the_purchase_is_kept_and_flagged_by_the_controls(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="50.00")], "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 80.0)]}})
    row = result.row("2026-09-01", "C1")
    assert (row["refunded_amount"], row["net_amount"]) == ("80.00", "-30.00")  # reported, not hidden
    assert result.checks["net_amount_not_negative_anomaly"] == (False, 1)
    assert result.checks["refunded_not_exceeds_gross_per_order"] == (False, 1)
    assert result.checks["net_amount_equals_gross_minus_refunded"] == (True, 0)
    report = json.loads((result.out / "quality_report.json").read_text(encoding="utf-8"))
    assert all(set(c) == {"name", "passed", "failed_records"} for c in report["checks"])


def test_days_without_refunds_file_or_with_an_empty_list_are_fine(tmp_path):
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1")], "payments": [pay("K-1")], "customers": [customer()]},  # no file
        "2026-09-02": {"refunds": []}})  # empty list
    assert result.row("2026-09-01", "C1")["refunds_count"] == "0" and result.rejected == set()


def test_outputs_are_deterministic(tmp_path):
    days = {"2026-09-01": {"orders": [order("K-1"), order("K-2", "C2", currency="USD")],
                           "payments": [pay("K-1"), pay("K-2")], "customers": [customer(), customer("C2")]},
            "2026-09-05": {"refunds": [refund("R-1", "K-1", 3.0), refund("R-9", "K-0", 1.0)]}}
    first = run_pipeline(tmp_path / "a", days)
    second = run_pipeline(tmp_path / "b", days)
    for name in metrics.OUTPUTS:
        assert (first.out / name).read_bytes() == (second.out / name).read_bytes()


def test_control_c6_detects_orders_duplicated_by_a_join(tmp_path):
    result = run_pipeline(tmp_path, {"2026-09-01": {"orders": [order("K-1")], "payments": [pay("K-1")],
                                                    "customers": [customer()]}})
    conn = sqlite3.connect(result.out / "warehouse.db")
    conn.execute("INSERT INTO kpi_valid_orders SELECT * FROM kpi_valid_orders")  # what a bad join would do
    _, _, checks = metrics.build(conn)
    conn.close()
    assert dict(checks)["orders_reconcile_with_valid_sales"] == 1


def test_quality_anomalies_do_not_change_the_exit_code(tmp_path):
    run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="50.00")], "payments": [pay("K-1")], "customers": [customer()]},
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 80.0)]}}, out="first")
    code = main(["--inbox", str(tmp_path / "inbox"), "--reference", str(tmp_path / "reference"),
                 "--out", str(tmp_path / "second")])
    assert code == 0
    assert Decimal(Result(tmp_path / "second").row("2026-09-01", "C1")["net_amount"]) < 0
