CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_merchant_cancellation_metrics AS
WITH paid_orders AS (
    SELECT
        orders.tenant_id,
        COUNT(DISTINCT orders.order_id) AS paid_order_count,
        MAX(payment.recorded_at) AS paid_order_freshness_at
    FROM yshopping_dim.dim_canonical_order_current orders
    JOIN yshopping_dim.dim_canonical_payment_current payment
      ON payment.tenant_id = orders.tenant_id
     AND payment.payment_id = orders.payment_id
    WHERE payment.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND payment.captured_amount_minor > 0
    GROUP BY orders.tenant_id
), merchant_cancellations AS (
    SELECT
        tenant_id,
        COUNT(*) AS merchant_responsible_paid_cancellation_count,
        MAX(data_freshness_at) AS cancellation_freshness_at
    FROM yshopping_dws.dws_canonical_merchant_cancellation_current
    WHERE counts_toward_paid_cancellation_rate = TRUE
      AND responsibility_party = 'MERCHANT'
      AND cancellation_mode = 'PAID_UNSHIPPED'
      AND order_status_at_request = 'PAYMENT_CONFIRMED'
      AND saga_status = 'COMPLETED'
      AND order_status = 'CANCELLED'
      AND order_cancellation_saga_id = saga_id
      AND order_responsibility_party = responsibility_party
      AND order_responsibility_code = responsibility_code
    GROUP BY tenant_id
)
SELECT
    paid.tenant_id,
    'merchant.cancellation_rate' AS metric_id,
    CAST(COALESCE(cancelled.merchant_responsible_paid_cancellation_count, 0) * 100.0
         / NULLIF(paid.paid_order_count, 0) AS DECIMAL(38,6)) AS metric_value,
    CAST(COALESCE(cancelled.merchant_responsible_paid_cancellation_count, 0) AS DECIMAL(38,6)) AS numerator,
    CAST(paid.paid_order_count AS DECIMAL(38,6)) AS denominator,
    'percent' AS unit,
    paid.paid_order_count AS source_row_count,
    'Merchant-responsible completed paid-unshipped cancellations divided by paid canonical orders; unpaid cancellations stay auditable but are excluded from the numerator' AS evidence_note,
    GREATEST(paid.paid_order_freshness_at, COALESCE(cancelled.cancellation_freshness_at, paid.paid_order_freshness_at)) AS data_freshness_at
FROM paid_orders paid
LEFT JOIN merchant_cancellations cancelled
  ON cancelled.tenant_id = paid.tenant_id;
