"""Tests of KIV-102: refunds.json changes its format (`amount` -> `refund_amount`, new field `reason`).

Specification: docs/specs/KIV-102/spec.md (RC-1 .. RC-13, scenarios E-1 .. E-12). Plan: docs/specs/KIV-102/plan.md.

Two kinds of tests, as agreed in the plan:
  * RED tests: they prove the change. They fail with the phase-4 code and pass with the new ingestion.
  * GUARD tests: they protect behaviour that already exists (old format, rejections, unknown fields,
    amounts equal to zero or negative, independence of the sales outputs). They pass before and after the
    change and would fail if that behaviour were broken.
They reuse the helpers of tests/test_kiv101.py (synthetic inboxes) and, for the real data, run the pipeline on
data/inbox read-only: the pipeline never writes to --inbox, the outputs go to a temporary directory.
"""

import contextlib
import io
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from kivora.pipeline import run
from test_kiv101 import Result, customer, order, pay, refund, run_pipeline

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
REFERENCE = ROOT / "data" / "reference"
OUTPUTS = ["daily_sales.csv", "top_customers.csv", "daily_customer_metrics.csv", "rejected.csv", "quality_report.json"]
ABSENT = object()  # the `reason` key is not in the record


def refund_v2(refund_id, order_id, amount, currency="EUR", reason=None, **extra):
    """A refund in the new format (`refund_amount` and `reason`)."""
    record = {"refund_id": refund_id, "order_id": order_id, "refunded_at": "2026-09-08T12:00:00Z",
              "refund_amount": amount, "currency": currency}
    if reason is not ABSENT:
        record["reason"] = reason
    record.update(extra)
    return record


def base_day(total="100.00", customer_id="C1", order_id="K-1", created="2026-09-01T10:00:00Z"):
    return {"orders": [order(order_id, customer_id, created=created, total=total)], "payments": [pay(order_id)],
            "customers": [customer(customer_id)]}


def figures(row):
    return (row["gross_amount"], row["refunded_amount"], row["net_amount"], row["refunds_count"])


def run_real(inbox, out):
    with contextlib.redirect_stdout(io.StringIO()):
        run(inbox, REFERENCE, out)
    return Result(out)


@pytest.fixture(scope="module")
def real10(tmp_path_factory):
    """The pipeline over every day of data/inbox (01 to 10), read-only."""
    return run_real(INBOX, tmp_path_factory.mktemp("real10") / "out")


@pytest.fixture(scope="module")
def real07(tmp_path_factory):
    """The pipeline over days 01 to 07 only (old format), copied to a temporary inbox."""
    tmp = tmp_path_factory.mktemp("real07")
    for day in sorted(p for p in INBOX.iterdir() if p.is_dir() and p.name <= "2026-09-07"):
        shutil.copytree(day, tmp / "inbox" / day.name)
    return run_real(tmp / "inbox", tmp / "out")


# ---------------------------------------------------------------------------------------------------------------
# RED tests: they prove the change
# ---------------------------------------------------------------------------------------------------------------

def test_refund_amount_is_counted(tmp_path):  # RC-1, E-1
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-08": {"refunds": [refund_v2("R-1", "K-1", 30.0, reason=None)]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "30.00", "70.00", "1")
    assert not any(record == "R-1" for _, record, _ in result.rejected)


def test_refund_amount_converts_currency(tmp_path):  # RC-1, E-2, E-3 (test rates: USD 0.92, GBP 1.17)
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", "C1", currency="USD", total="61.08"),
                                  order("K-2", "C2", currency="GBP", total="210.00")],
                       "payments": [pay("K-1"), pay("K-2")], "customers": [customer("C1"), customer("C2")]},
        "2026-09-08": {"refunds": [refund_v2("R-1", "K-1", 36.65, "USD", "talla incorrecta"),
                                   refund_v2("R-2", "K-2", 31.5, "GBP", "pedido duplicado por error")]}})
    assert figures(result.row("2026-09-01", "C1")) == ("56.19", "33.72", "22.47", "1")  # 36.65 * 0.92 = 33.718
    assert figures(result.row("2026-09-01", "C2")) == ("245.70", "36.86", "208.84", "1")  # 31.5 * 1.17 = 36.855, half up


def test_both_formats_on_same_order(tmp_path):  # RC-3, E-4: old-format refund (day 07) and new-format refund (day 09)
    result = run_pipeline(tmp_path, {
        "2026-09-06": base_day(total="80.00", created="2026-09-06T10:00:00Z"),
        "2026-09-07": {"refunds": [refund("R-1", "K-1", 70.0)]},
        "2026-09-09": {"refunds": [refund_v2("R-2", "K-1", 20.0, reason="talla incorrecta")]}})
    assert figures(result.row("2026-09-06", "C1")) == ("80.00", "90.00", "-10.00", "2")


def test_formats_mixed_in_same_file(tmp_path):  # RC-3: the format is detected per record, not per file
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-08": {"refunds": [refund("R-1", "K-1", 10.0), refund_v2("R-2", "K-1", 5.5, reason="x")]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "15.50", "84.50", "2")


def test_refund_amount_wins_when_both_present(tmp_path):  # RC-4, E-9
    record = refund_v2("R-1", "K-1", 20.0)
    record["amount"] = 70.0
    result = run_pipeline(tmp_path, {"2026-09-01": base_day(), "2026-09-08": {"refunds": [record]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "20.00", "80.00", "1")


def test_refund_amount_used_when_amount_is_blank(tmp_path):  # RC-5, E-9
    records = []
    for i, blank in enumerate([None, "", "  "], start=1):
        record = refund_v2(f"R-{i}", "K-1", 20.0)
        record["amount"] = blank
        records.append(record)
    result = run_pipeline(tmp_path, {"2026-09-01": base_day(), "2026-09-08": {"refunds": records}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "60.00", "40.00", "3")
    assert result.rejected == set()


@pytest.mark.parametrize("reason", [None, "", "   ", ABSENT, "talla incorrecta", "Me lo devolvió Ana Ruiz"])
def test_reason_null_blank_absent_or_text_is_accepted(tmp_path, reason):  # RC-6, E-10 (red through `importe no valido`)
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-08": {"refunds": [refund_v2("R-1", "K-1", 25.0, reason=reason)]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "25.00", "75.00", "1")
    assert result.rejected == set()


def test_reason_is_kept_only_in_raw_refunds(tmp_path):  # RC-7, E-10
    secret = "Me lo devolvió Ana Ruiz Zubiaur"
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-08": {"refunds": [refund_v2("R-1", "K-1", 10.0, reason=secret),
                                   refund_v2("R-2", "K-1", 5.0, reason=None)]}})
    conn = sqlite3.connect(result.out / "warehouse.db")
    try:
        assert "reason" in [column[1] for column in conn.execute("PRAGMA table_info(raw_refunds)")]
        stored = dict(conn.execute("SELECT refund_id, reason FROM raw_refunds"))
    finally:
        conn.close()
    assert stored == {"R-1": secret, "R-2": ""}  # text as it came; null stored as an empty string
    for name in OUTPUTS:  # the VALUE of the reason is in no output (the column `reason` of rejected.csv is another thing)
        assert "Zubiaur" not in (result.out / name).read_text(encoding="utf-8"), name


def test_new_refunds_do_not_duplicate_rows(tmp_path):  # RC-1, RC-10: joins (several captured payments) multiply nothing
    result = run_pipeline(tmp_path, {
        "2026-09-01": {"orders": [order("K-1", total="100.00")],
                       "payments": [pay("K-1", amount="40.00"), pay("K-1", amount="60.00")],
                       "customers": [customer(), customer(name="Ana Ruiz")]},
        "2026-09-08": {"refunds": [refund_v2("R-1", "K-1", 5.0, reason="a"), refund_v2("R-2", "K-1", 5.0, reason="b"),
                                   refund_v2("R-3", "K-1", 5.0, reason=None)]}})
    assert [(r["metric_date"], r["customer_id"]) for r in result.metrics] == [("2026-09-01", "C1")]  # one row
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "15.00", "85.00", "3")
    assert result.checks["orders_reconcile_with_valid_sales"] == (True, 0)
    assert result.checks["no_duplicate_refund_ids"] == (True, 0)


def test_quality_controls_see_new_format(tmp_path):  # RC-10, E-5: the anomaly is reported, never hidden
    result = run_pipeline(tmp_path, {
        "2026-09-06": base_day(total="80.00", created="2026-09-06T10:00:00Z"),
        "2026-09-07": {"refunds": [refund("R-1", "K-1", 70.0)]},
        "2026-09-09": {"refunds": [refund_v2("R-2", "K-1", 20.0)]}})
    row = result.row("2026-09-06", "C1")
    assert (row["refunded_amount"], row["net_amount"]) == ("90.00", "-10.00")
    assert result.checks["net_amount_not_negative_anomaly"] == (False, 1)
    assert result.checks["refunded_not_exceeds_gross_per_order"] == (False, 1)
    assert result.checks["net_amount_equals_gross_minus_refunded"] == (True, 0)
    assert result.checks["all_rejected_records_have_reason"] == (True, 0)


def test_output_is_deterministic_with_both_formats(tmp_path):  # RC-11, E-12 (red only through the expected figures)
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 10.0)]},
        "2026-09-08": {"refunds": [refund_v2("R-2", "K-1", 20.0, reason="x"), refund_v2("R-3", "K-9", 1.0)]}})
    run(tmp_path / "inbox", tmp_path / "reference", tmp_path / "out2")
    for name in OUTPUTS:
        assert (result.out / name).read_bytes() == (tmp_path / "out2" / name).read_bytes(), name
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "30.00", "70.00", "2")  # the expected figures
    assert ("refunds", "R-3", "pedido no encontrado") in result.rejected
    assert result.read("daily_customer_metrics.csv")[0].keys() == {
        "metric_date", "customer_id", "country", "orders_count", "gross_amount", "refunded_amount", "net_amount",
        "refunds_count", "last_purchase_date"}  # the contract of KIV-101 does not change (RC-11)


def test_late_refund_restates_the_purchase_day(tmp_path):  # RC-1, E-6/E-8: a refund of day 08 changes the row of day 01
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-08": {"orders": [order("K-2", "C2", created="2026-09-08T10:00:00Z", total="50.00")],
                       "payments": [pay("K-2")], "customers": [customer("C2")],
                       "refunds": [refund_v2("R-1", "K-1", 12.0), refund_v2("R-2", "K-2", 5.0)]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "12.00", "88.00", "1")  # the purchase day, not day 08
    assert figures(result.row("2026-09-08", "C2")) == ("50.00", "5.00", "45.00", "1")
    assert result.row("2026-09-08", "C1") is None  # no row for a day without purchases


# The 14 rows that change when the new format is read (spec E-1 .. E-8): (date, customer) -> gross, refunded, net, count
CHANGED_ROWS = {
    ("2026-09-02", "C003"): ("138.19", "4.54", "133.65", "1"),
    ("2026-09-03", "C005"): ("384.48", "23.35", "361.13", "1"),
    ("2026-09-03", "C023"): ("121.74", "3.58", "118.16", "1"),
    ("2026-09-04", "C018"): ("245.70", "36.86", "208.84", "1"),  # E-3 (GBP)
    ("2026-09-05", "C006"): ("356.28", "26.94", "329.34", "1"),
    ("2026-09-05", "C025"): ("421.45", "85.00", "336.45", "2"),
    ("2026-09-06", "C015"): ("239.17", "97.29", "141.88", "3"),
    ("2026-09-06", "C026"): ("80.00", "90.00", "-10.00", "2"),  # E-4 (K-10155: R-1013 old format + R-1035 new format)
    ("2026-09-07", "C001"): ("34.61", "17.30", "17.31", "1"),
    ("2026-09-07", "C022"): ("56.19", "33.72", "22.47", "1"),  # E-2 (USD)
    ("2026-09-07", "C027"): ("409.09", "28.23", "380.86", "1"),
    ("2026-09-07", "C029"): ("85.12", "10.00", "75.12", "1"),  # E-1 (reason = null)
    ("2026-09-08", "C007"): ("81.87", "40.94", "40.93", "1"),  # E-8
    ("2026-09-09", "C031"): ("103.49", "9.95", "93.54", "1"),  # E-8
}


def test_real_data_new_refunds_change_exactly_14_rows(real10):  # RC-1, E-1 .. E-4, E-6, E-8
    assert len(real10.metrics) == 164
    wrong = {}
    for (date, customer_id), expected in CHANGED_ROWS.items():
        row = real10.row(date, customer_id)
        got = figures(row) if row else None
        if got != expected:
            wrong[(date, customer_id)] = {"esperado": expected, "obtenido": got}
    assert wrong == {}


def test_real_data_rejections_and_controls(real10):  # RC-9, RC-10, E-5, E-7
    assert real10.rejected == {
        ("refunds", "R-1003", "pedido no encontrado"), ("refunds", "R-1005", "pedido cancelado"),
        ("refunds", "R-1006", "refund_id duplicado"), ("refunds", "R-1034", "pedido no encontrado")}
    assert not any(reason == "importe no valido" for _, _, reason in real10.rejected)
    assert real10.checks["net_amount_not_negative_anomaly"] == (False, 1)  # C026 / 2026-09-06
    assert real10.checks["refunded_not_exceeds_gross_per_order"] == (False, 2)  # K-10148 and K-10155
    assert real10.checks["net_amount_equals_gross_minus_refunded"] == (True, 0)
    assert real10.checks["orders_reconcile_with_valid_sales"] == (True, 0)


def test_real_data_reason_is_stored_in_raw_refunds(real10):  # RC-7, E-10: 14 reasons with text and 1 null (R-1033)
    conn = sqlite3.connect(real10.out / "warehouse.db")
    try:
        new = conn.execute("SELECT COUNT(*), SUM(reason <> '') FROM raw_refunds WHERE _day >= '2026-09-08'").fetchone()
        r1033 = conn.execute("SELECT reason, amount FROM raw_refunds WHERE refund_id = 'R-1033'").fetchone()
    finally:
        conn.close()
    assert new == (15, 14)
    assert r1033 == ("", "10.0")  # null reason stored as empty; the amount comes from `refund_amount`


def test_real_data_only_late_refunds_change_days_01_to_07(real07, real10):  # RC-2, E-6 (red: the late refunds are lost today)
    old = {(r["metric_date"], r["customer_id"]): r for r in real07.metrics}
    changed = [key for key, row in old.items() if real10.row(*key) != row]
    assert sorted(changed) == sorted(key for key in CHANGED_ROWS if key[0] <= "2026-09-07")  # the 12 late refunds


# ---------------------------------------------------------------------------------------------------------------
# GUARD tests: they protect behaviour that already exists (they pass before and after the change)
# ---------------------------------------------------------------------------------------------------------------

def test_old_format_unchanged(tmp_path):  # RC-2, E-6
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 30.0), refund("R-2", "K-1", 10.5)]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "40.50", "59.50", "2")
    assert result.rejected == set()


def test_real_data_old_format_days_01_to_07_unchanged(real07):  # RC-2, E-6: the figures of KIV-101
    assert len(real07.metrics) == 115
    assert real07.row("2026-09-01", "C007")["refunded_amount"] == "41.51"
    assert figures(real07.row("2026-09-04", "C022")) == ("325.17", "126.02", "199.15", "3")
    assert real07.rejected == {("refunds", "R-1003", "pedido no encontrado"), ("refunds", "R-1005", "pedido cancelado"),
                               ("refunds", "R-1006", "refund_id duplicado")}


@pytest.mark.parametrize("record", [
    {"refund_id": "R-1", "order_id": "K-1", "refunded_at": "2026-09-08T12:00:00Z", "currency": "EUR"},  # no amount
    {"refund_id": "R-1", "order_id": "K-1", "refunded_at": "2026-09-08T12:00:00Z", "currency": "EUR",
     "refund_amount": None, "reason": "x"},
    {"refund_id": "R-1", "order_id": "K-1", "refunded_at": "2026-09-08T12:00:00Z", "currency": "EUR", "amount": ""},
    {"refund_id": "R-1", "order_id": "K-1", "refunded_at": "2026-09-08T12:00:00Z", "currency": "EUR",
     "amount": None, "refund_amount": "  "},
])
def test_record_without_any_amount_is_rejected(tmp_path, record):  # RC-5, E-9: never counted as zero
    result = run_pipeline(tmp_path, {"2026-09-01": base_day(), "2026-09-08": {"refunds": [record]}})
    assert ("refunds", "R-1", "importe no valido") in result.rejected
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "0.00", "100.00", "0")


def test_null_or_blank_refund_amount_falls_back_to_amount(tmp_path):  # RC-5, E-9
    records = []
    for i, blank in enumerate([None, "", "  "], start=1):
        record = refund(f"R-{i}", "K-1", 10.0)
        record["refund_amount"] = blank
        records.append(record)
    result = run_pipeline(tmp_path, {"2026-09-01": base_day(), "2026-09-08": {"refunds": records}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "30.00", "70.00", "3")


def test_unknown_fields_are_ignored(tmp_path):  # RC-8, E-11
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-05": {"refunds": [dict(refund("R-1", "K-1", 10.0), channel="web", note=["x"])]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "10.00", "90.00", "1")
    assert result.rejected == set()


def test_zero_and_negative_amounts_keep_the_current_behaviour(tmp_path):  # A-10: no new rule, behaviour unchanged
    result = run_pipeline(tmp_path, {
        "2026-09-01": base_day(),
        "2026-09-05": {"refunds": [refund("R-1", "K-1", 0.0), refund("R-2", "K-1", -5.0)]}})
    assert figures(result.row("2026-09-01", "C1")) == ("100.00", "-5.00", "105.00", "2")
    assert result.rejected == set()


def test_sales_outputs_do_not_depend_on_refunds(real10, tmp_path):  # E-7: daily_sales and top_customers ignore refunds
    for day in sorted(p for p in INBOX.iterdir() if p.is_dir()):
        target = tmp_path / "inbox" / day.name
        target.mkdir(parents=True)
        for name in ("orders.csv", "customers.csv", "payments.csv"):  # everything except refunds.json
            shutil.copy(day / name, target / name)
    without = run_real(tmp_path / "inbox", tmp_path / "out")
    for name in ("daily_sales.csv", "top_customers.csv"):
        assert (without.out / name).read_bytes() == (real10.out / name).read_bytes(), name
