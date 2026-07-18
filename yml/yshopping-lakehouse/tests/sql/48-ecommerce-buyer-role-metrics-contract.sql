SELECT 'buyer_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 3 OR COUNT(DISTINCT metric_id) <> 3
) invalid;

SELECT 'buyer_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
WHERE metric_id NOT IN (
    'buyer.time_to_first_order_hours',
    'buyer.delivery_promise_hit_rate',
    'fulfillment.on_time_delivery_rate'
);

SELECT 'buyer_role_metric_null_value', COUNT(*)
FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
WHERE metric_value IS NULL
   OR numerator IS NULL
   OR source_row_count <= 0
   OR data_freshness_at IS NULL;

SELECT 'buyer_role_metric_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
WHERE (unit = 'hours' AND (denominator IS NOT NULL OR metric_value <> numerator))
   OR (unit = 'percent' AND metric_value <> numerator * 100.0 / NULLIF(denominator, 0));

SELECT 'buyer_role_metric_invalid_range', COUNT(*)
FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
WHERE metric_value < 0
   OR (unit = 'percent' AND metric_value > 100)
   OR numerator < 0
   OR (denominator IS NOT NULL AND (denominator <= 0 OR numerator > denominator));

SELECT 'buyer_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_buyer_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
