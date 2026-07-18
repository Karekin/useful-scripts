SELECT 'merchant_cancellation_metric_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_merchant_cancellation_metrics metric
LEFT JOIN (
  SELECT
    tenant_id,
    COUNT(*) AS numerator,
    MAX(data_freshness_at) AS data_freshness_at
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
) numerator
  ON numerator.tenant_id = metric.tenant_id
LEFT JOIN (
  SELECT
    orders.tenant_id,
    COUNT(DISTINCT orders.order_id) AS denominator
  FROM yshopping_dim.dim_canonical_order_current orders
  JOIN yshopping_dim.dim_canonical_payment_current payment
    ON payment.tenant_id = orders.tenant_id
   AND payment.payment_id = orders.payment_id
  WHERE payment.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
    AND payment.captured_amount_minor > 0
  GROUP BY orders.tenant_id
) denominator
  ON denominator.tenant_id = metric.tenant_id
WHERE metric.metric_id <> 'merchant.cancellation_rate'
   OR metric.numerator <> CAST(COALESCE(numerator.numerator, 0) AS DECIMAL(38,6))
   OR metric.denominator <> CAST(denominator.denominator AS DECIMAL(38,6))
   OR metric.metric_value <> CAST(COALESCE(numerator.numerator, 0) * 100.0
                                  / NULLIF(denominator.denominator, 0) AS DECIMAL(38,6))
UNION ALL
SELECT 'merchant_cancellation_unpaid_in_numerator', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_cancellation_current
WHERE counts_toward_paid_cancellation_rate = TRUE
  AND cancellation_mode <> 'PAID_UNSHIPPED'
UNION ALL
SELECT 'merchant_cancellation_missing_governed_code', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_cancellation_current
WHERE counts_toward_paid_cancellation_rate = TRUE
  AND (responsibility_party IS NULL
       OR responsibility_code IS NULL
       OR order_responsibility_party IS NULL
       OR order_responsibility_code IS NULL)
UNION ALL
SELECT 'merchant_cancellation_nonmerchant_leak', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_cancellation_current
WHERE counts_toward_paid_cancellation_rate = TRUE
  AND responsibility_party <> 'MERCHANT';
