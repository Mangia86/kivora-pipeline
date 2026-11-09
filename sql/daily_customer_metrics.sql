-- KIV-101: daily_customer_metrics. Selections only; the monetary arithmetic and the
-- Europe/Madrid date are computed in kivora/metrics.py (SQLite has neither Decimal nor time zones).
-- Contract: docs/specs/KIV-101/spec.md

-- A sale is the latest version of an order that is not cancelled and has a captured payment.
-- EXISTS (not a JOIN) so several payments never multiply the order; the latest customer version
-- (stg_customers_latest) has one row per customer, so the join does not multiply it either.
DROP TABLE IF EXISTS kpi_valid_orders;
CREATE TABLE kpi_valid_orders AS
SELECT o.order_id, o.customer_id, o.created_at, o.currency, o.total_amount,
       COALESCE(NULLIF(TRIM(c.country), ''), 'UNKNOWN') AS country
FROM stg_orders_latest o
LEFT JOIN stg_customers_latest c ON c.customer_id = o.customer_id
WHERE LOWER(TRIM(o.status)) <> 'cancelled'
  AND EXISTS (SELECT 1 FROM stg_payments p
              WHERE p.order_id = o.order_id AND LOWER(TRIM(p.status)) = 'captured')
ORDER BY o.order_id;

-- Number of sales computed WITHOUT the customers join (control C-6 compares against it).
DROP TABLE IF EXISTS kpi_valid_count;
CREATE TABLE kpi_valid_count AS
SELECT COUNT(*) AS n
FROM stg_orders_latest o
WHERE LOWER(TRIM(o.status)) <> 'cancelled'
  AND EXISTS (SELECT 1 FROM stg_payments p
              WHERE p.order_id = o.order_id AND LOWER(TRIM(p.status)) = 'captured');

-- Refunds that can be attributed: their order exists and is a sale (one row per refund_id).
DROP TABLE IF EXISTS kpi_refunds;
CREATE TABLE kpi_refunds AS
SELECT r.refund_id, r.order_id, r.currency, r.amount
FROM stg_refunds r
JOIN kpi_valid_orders v ON v.order_id = r.order_id
ORDER BY r.refund_id;

-- Rejections decided in SQL. Cancelled or unpaid ORDERS are valid business states and are not
-- rejected (A-9); only the refunds that cannot be processed, and the repeated refund_id, are.
DROP TABLE IF EXISTS kpi_rejected;
CREATE TABLE kpi_rejected AS
SELECT 'refunds' AS source, r.refund_id AS record_id, 'pedido no encontrado' AS reason
FROM stg_refunds r
WHERE NOT EXISTS (SELECT 1 FROM stg_orders_latest o WHERE o.order_id = r.order_id)
UNION ALL
SELECT 'refunds', r.refund_id, 'pedido cancelado'
FROM stg_refunds r
JOIN stg_orders_latest o ON o.order_id = r.order_id
WHERE LOWER(TRIM(o.status)) = 'cancelled'
UNION ALL
SELECT 'refunds', r.refund_id, 'pedido sin pago cobrado'
FROM stg_refunds r
JOIN stg_orders_latest o ON o.order_id = r.order_id
WHERE LOWER(TRIM(o.status)) <> 'cancelled'
  AND NOT EXISTS (SELECT 1 FROM stg_payments p
                  WHERE p.order_id = o.order_id AND LOWER(TRIM(p.status)) = 'captured')
UNION ALL
SELECT 'refunds', refund_id, 'refund_id duplicado'
FROM stg_refunds_dup;
