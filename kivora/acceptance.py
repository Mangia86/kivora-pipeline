"""Acceptance of KIV-101 and KIV-102 (python tasks.py acceptance).

First pass (KIV-101): runs the pipeline twice over the deliveries of KIV-101 in data/inbox (days up to
2026-09-07, so later deliveries do not move the expected figures) and checks the scenarios E-1 .. E-15 of
docs/specs/KIV-101/spec.md with the real figures (28 checks, unchanged).
Second pass (KIV-102): runs the pipeline twice over every day of data/inbox (01 to 10) and checks the scenarios
of docs/specs/KIV-102/spec.md (refunds.json in both formats).
Exit code 0 only if every check of both passes passes, and each pass prints its own summary.
The pipeline itself contains none of these figures: they are expected values of the oracle.
"""

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from kivora import metrics
from kivora.pipeline import run

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
REFERENCE = ROOT / "data" / "reference"
LAST_DAY = "2026-09-07"  # last day of the deliveries covered by KIV-101


def _run(inbox, reference, out):
    with contextlib.redirect_stdout(io.StringIO()):
        run(inbox, reference, out)
    return Path(out)


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class Oracle:
    def __init__(self, out):
        self.metrics = _read(out / "daily_customer_metrics.csv")
        self.rejected = {(r["source"], r["record_id"], r["reason"]) for r in _read(out / "rejected.csv")}
        report = json.loads((out / "quality_report.json").read_text(encoding="utf-8"))
        self.checks = {c["name"]: c["failed_records"] for c in report["checks"]}
        self.results = []

    def row(self, date, customer):
        found = [r for r in self.metrics if r["metric_date"] == date and r["customer_id"] == customer]
        return found[0] if len(found) == 1 else None

    def expect(self, scenario, label, ok, detail=""):
        self.results.append((scenario, label, bool(ok), detail))

    def expect_row(self, scenario, date, customer, **expected):
        row = self.row(date, customer)
        got = {k: (row or {}).get(k) for k in expected}
        self.expect(scenario, f"{customer} / {date}", row is not None and got == expected,
                    "" if row is not None and got == expected else f"esperado {expected}, obtenido {got if row else 'sin fila'}")

    def has_row(self, date, customer):
        return self.row(date, customer) is not None


def scenarios(o, identical):
    o.expect_row("E-1", "2026-09-01", "C009", orders_count="1", gross_amount="45.90")
    o.expect_row("E-1", "2026-09-06", "C017", orders_count="1", gross_amount="23.10")
    o.expect_row("E-2", "2026-09-01", "C007", country="UNKNOWN", orders_count="2", gross_amount="246.66",
                 refunded_amount="41.51", net_amount="205.15", refunds_count="1", last_purchase_date="2026-09-01")
    o.expect_row("E-3", "2026-09-01", "C020", orders_count="1", gross_amount="72.77", refunded_amount="21.83",
                 net_amount="50.94", refunds_count="1")
    o.expect_row("E-4/E-10", "2026-09-04", "C022", orders_count="3", gross_amount="325.17", refunded_amount="126.02",
                 net_amount="199.15", refunds_count="3", last_purchase_date="2026-09-04")
    o.expect("E-5", "R-1003 rechazada: pedido no encontrado", ("refunds", "R-1003", "pedido no encontrado") in o.rejected)
    o.expect_row("E-6", "2026-09-01", "C003", orders_count="2", gross_amount="338.72", refunded_amount="74.53",
                 net_amount="264.19", refunds_count="1")
    o.expect_row("E-7", "2026-09-04", "C018", orders_count="1", gross_amount="245.70")
    o.expect_row("E-7", "2026-09-06", "C006", orders_count="1", gross_amount="134.50")
    o.expect_row("E-8", "2026-09-04", "C014", orders_count="2", gross_amount="244.19", refunded_amount="0.00",
                 net_amount="244.19", refunds_count="0")
    o.expect("E-8", "R-1005 rechazada (pedido cancelado) y K-10149 no rechazado como pedido",
             ("refunds", "R-1005", "pedido cancelado") in o.rejected and not any(r[:2] == ("orders", "K-10149") for r in o.rejected))
    o.expect("E-9", "dos ejecuciones dan ficheros idénticos byte a byte", identical)
    o.expect_row("E-11", "2026-09-04", "C028", gross_amount="196.69", refunded_amount="12.00", refunds_count="1")
    o.expect("E-11", "R-1006 (duplicado) informado en rejected.csv", ("refunds", "R-1006", "refund_id duplicado") in o.rejected)
    o.expect_row("E-12", "2026-09-04", "C010", orders_count="2", gross_amount="258.32", refunded_amount="99.91",
                 net_amount="158.41", refunds_count="1")
    o.expect_row("E-12", "2026-09-05", "C010", orders_count="1", gross_amount="41.55")
    o.expect_row("E-12", "2026-09-02", "C021", orders_count="1", gross_amount="78.68", refunded_amount="39.34",
                 net_amount="39.34", refunds_count="1")
    o.expect("E-12", "C021 no tiene fila el 2026-09-03", not o.has_row("2026-09-03", "C021"))
    o.expect_row("E-13", "2026-09-02", "C024", orders_count="1", gross_amount="197.51", refunded_amount="0.00",
                 net_amount="197.51", refunds_count="0")
    o.expect("E-13", "K-10062 no aparece rechazado como pedido", not any(r[:2] == ("orders", "K-10062") for r in o.rejected))
    o.expect_row("E-14", "2026-09-02", "C003", orders_count="2", gross_amount="138.19", refunded_amount="0.00",
                 net_amount="138.19", refunds_count="0")
    o.expect("E-14", "C004 no tiene fila el 2026-09-01 (K-10054 pasa al día 2 en Madrid)", not o.has_row("2026-09-01", "C004"))
    o.expect_row("E-14", "2026-09-02", "C004", orders_count="6", gross_amount="691.50")
    o.expect("E-14", "115 filas cliente-día (con fechas UTC serían 118)", len(o.metrics) == 115, f"filas: {len(o.metrics)}")
    o.expect_row("E-15", "2026-09-01", "C005", country="ES", orders_count="2", gross_amount="201.59",
                 refunded_amount="18.96", net_amount="182.63", refunds_count="1")
    pairs = [(r["metric_date"], r["customer_id"]) for r in o.metrics]
    o.expect("E-15", "cada (metric_date, customer_id) aparece una sola vez", len(pairs) == len(set(pairs)))
    total_orders = sum(int(r["orders_count"]) for r in o.metrics)
    total_gross = sum(Decimal(r["gross_amount"]) for r in o.metrics)
    o.expect("E-15", "conciliación: 156 ventas válidas y 18490.74 EUR", (total_orders, total_gross) == (156, Decimal("18490.74")),
             f"obtenido {total_orders} y {total_gross}")
    expected_failed = {"net_amount_equals_gross_minus_refunded": 0, "net_amount_not_negative_anomaly": 0,
                       "refunded_not_exceeds_gross_per_order": 1, "no_duplicate_refund_ids": 0,
                       "all_rejected_records_have_reason": 0, "orders_reconcile_with_valid_sales": 0}
    o.expect("C-1..C-6", "controles de calidad con los datos actuales (solo C-3 detecta K-10148)", o.checks == expected_failed,
             f"obtenido {o.checks}")


# KIV-102: the 14 rows of daily_customer_metrics.csv that change when refunds.json is read in both formats
# (spec E-1 .. E-8): (metric_date, customer_id) -> gross, refunded, net, refunds_count.
KIV102_ROWS = {
    ("2026-09-02", "C003"): ("138.19", "4.54", "133.65", "1"),
    ("2026-09-03", "C005"): ("384.48", "23.35", "361.13", "1"),
    ("2026-09-03", "C023"): ("121.74", "3.58", "118.16", "1"),
    ("2026-09-04", "C018"): ("245.70", "36.86", "208.84", "1"),  # E-3: R-1039, GBP
    ("2026-09-05", "C006"): ("356.28", "26.94", "329.34", "1"),
    ("2026-09-05", "C025"): ("421.45", "85.00", "336.45", "2"),
    ("2026-09-06", "C015"): ("239.17", "97.29", "141.88", "3"),
    ("2026-09-06", "C026"): ("80.00", "90.00", "-10.00", "2"),  # E-4: K-10155, R-1013 (old) + R-1035 (new)
    ("2026-09-07", "C001"): ("34.61", "17.30", "17.31", "1"),
    ("2026-09-07", "C022"): ("56.19", "33.72", "22.47", "1"),  # E-2: R-1037, USD
    ("2026-09-07", "C027"): ("409.09", "28.23", "380.86", "1"),
    ("2026-09-07", "C029"): ("85.12", "10.00", "75.12", "1"),  # E-1: R-1033, reason = null
    ("2026-09-08", "C007"): ("81.87", "40.94", "40.93", "1"),  # E-8: R-1041
    ("2026-09-09", "C031"): ("103.49", "9.95", "93.54", "1"),  # E-8: R-1036
}
KIV102_REJECTED = {("refunds", "R-1003", "pedido no encontrado"), ("refunds", "R-1005", "pedido cancelado"),
                   ("refunds", "R-1006", "refund_id duplicado"), ("refunds", "R-1034", "pedido no encontrado")}


def scenarios_kiv102(o, identical):
    """Scenarios E-1 .. E-8 and E-12 of docs/specs/KIV-102/spec.md over every day of data/inbox (01 to 10)."""
    for (date, customer), (gross, refunded, net, count) in KIV102_ROWS.items():
        o.expect_row("KIV-102 E-1..E-4,E-8", date, customer, gross_amount=gross, refunded_amount=refunded,
                     net_amount=net, refunds_count=count)
    o.expect("KIV-102 E-1", "R-1033 (reason = null) no está en rejected.csv", not any(r[:2] == ("refunds", "R-1033") for r in o.rejected))
    o.expect("KIV-102 E-5/E-7", "rejected.csv: exactamente R-1003, R-1005, R-1006 y R-1034", o.rejected == KIV102_REJECTED,
             f"obtenido {sorted(o.rejected)}")
    o.expect("KIV-102 E-7", "ningún rechazo por importe no valido", not any(r[2] == "importe no valido" for r in o.rejected))
    o.expect("KIV-102 E-7", "164 filas cliente-día", len(o.metrics) == 164, f"filas: {len(o.metrics)}")
    pairs = [(r["metric_date"], r["customer_id"]) for r in o.metrics]
    o.expect("KIV-102 E-7", "cada (metric_date, customer_id) aparece una sola vez", len(pairs) == len(set(pairs)))
    expected_failed = {"net_amount_equals_gross_minus_refunded": 0, "net_amount_not_negative_anomaly": 1,
                       "refunded_not_exceeds_gross_per_order": 2, "no_duplicate_refund_ids": 0,
                       "all_rejected_records_have_reason": 0, "orders_reconcile_with_valid_sales": 0}
    o.expect("KIV-102 E-5", "controles: C-2 = 1 (C026) y C-3 = 2 (K-10148 y K-10155), anomalías informadas",
             o.checks == expected_failed, f"obtenido {o.checks}")
    o.expect("KIV-102 E-12", "dos ejecuciones dan ficheros idénticos byte a byte", identical)


def _execute(prefix, last_day, scenario_function):
    """Run the pipeline twice over a copy of data/inbox (days up to last_day, or all) and check the scenarios."""
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        inbox = tmp / "inbox"
        for day in sorted(p for p in INBOX.iterdir() if p.is_dir() and (last_day is None or p.name <= last_day)):
            shutil.copytree(day, inbox / day.name)  # copy: data/inbox is never written
        first, second = _run(inbox, REFERENCE, tmp / "run1"), _run(inbox, REFERENCE, tmp / "run2")
        identical = all((first / n).read_bytes() == (second / n).read_bytes() for n in metrics.OUTPUTS)
        oracle = Oracle(first)
        scenario_function(oracle, identical)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return oracle


def _report(title, oracle):
    failed = [r for r in oracle.results if not r[2]]
    print(f"== {title}")
    for scenario, label, ok, detail in oracle.results:
        print(f"{'OK  ' if ok else 'FAIL'}  {scenario}: {label}" + ("" if ok else f"  ({detail})"))
    print(f"\nacceptance {title.split()[0]}: {len(oracle.results) - len(failed)}/{len(oracle.results)} comprobaciones superadas\n")
    return not failed


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    kiv101 = _execute("kivora-acceptance-101-", LAST_DAY, scenarios)  # first pass: the 28 checks of KIV-101, unchanged
    kiv102 = _execute("kivora-acceptance-102-", None, scenarios_kiv102)  # second pass: every day, KIV-102
    results = [_report("KIV-101 (días hasta 2026-09-07)", kiv101), _report("KIV-102 (todos los días de data/inbox)", kiv102)]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
