-- Staging: types and duplicates.
-- Reads the raw_* tables loaded by kivora/ingest.py.

DROP TABLE IF EXISTS stg_orders;
CREATE TABLE stg_orders AS
SELECT DISTINCT
    order_id,
    customer_id,
    created_at,
    updated_at,
    status,
    currency,
    CAST(total_amount AS REAL) AS total_amount,
    substr(created_at, 1, 10)   AS order_date
FROM raw_orders;

DROP TABLE IF EXISTS stg_customers;
CREATE TABLE stg_customers AS
SELECT DISTINCT
    customer_id,
    name,
    country,
    signup_date
FROM raw_customers;

DROP TABLE IF EXISTS stg_payments;
CREATE TABLE stg_payments AS
SELECT
    payment_id,
    order_id,
    paid_at,
    method,
    status,
    CAST(amount AS REAL) AS amount
FROM raw_payments;

-- KIV-101: latest version of each order and customer, and refunds (duplicates kept apart).
-- Money stays as text here: all monetary arithmetic is done in Python with Decimal (kivora/metrics.py).
-- The legacy stg_orders / stg_customers above are NOT modified: daily_sales and top_customers read them.

DROP TABLE IF EXISTS stg_orders_latest;
CREATE TABLE stg_orders_latest AS
SELECT order_id, customer_id, created_at, updated_at, status, currency, total_amount
FROM (
    SELECT r.*,
           ROW_NUMBER() OVER (PARTITION BY order_id
                              ORDER BY updated_at DESC, _day ASC, rowid ASC) AS rn
    FROM raw_orders r
)
WHERE rn = 1;

DROP TABLE IF EXISTS stg_customers_latest;
CREATE TABLE stg_customers_latest AS
SELECT customer_id, name, country, signup_date
FROM (
    SELECT r.*,
           ROW_NUMBER() OVER (PARTITION BY customer_id
                              ORDER BY _day DESC, rowid DESC) AS rn
    FROM raw_customers r
)
WHERE rn = 1;

DROP TABLE IF EXISTS stg_refunds_ranked;
CREATE TABLE stg_refunds_ranked AS
SELECT refund_id, order_id, refunded_at, amount, currency, _day,
       ROW_NUMBER() OVER (PARTITION BY refund_id ORDER BY _day ASC, rowid ASC) AS rn
FROM raw_refunds;

DROP TABLE IF EXISTS stg_refunds;
CREATE TABLE stg_refunds AS
SELECT refund_id, order_id, refunded_at, amount, currency, _day
FROM stg_refunds_ranked WHERE rn = 1;

DROP TABLE IF EXISTS stg_refunds_dup;
CREATE TABLE stg_refunds_dup AS
SELECT refund_id, order_id, refunded_at, amount, currency, _day
FROM stg_refunds_ranked WHERE rn > 1;