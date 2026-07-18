SELECT 'operations_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_operations_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 3 OR COUNT(DISTINCT metric_id) <> 3
) invalid;

SELECT 'operations_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_operations_role_metrics
WHERE metric_id NOT IN (
    'funnel.visit_to_pay_rate',
    'funnel.cart_abandonment_rate',
    'buyer.new_paid_buyer_count'
);

SELECT 'operations_role_metric_null_value', COUNT(*)
FROM yshopping_ads.ads_ecommerce_operations_role_metrics
WHERE metric_value IS NULL
   OR numerator IS NULL
   OR source_row_count <= 0
   OR data_freshness_at IS NULL;

SELECT 'operations_role_metric_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_operations_role_metrics
WHERE (unit = 'count' AND metric_value <> numerator)
   OR (unit = 'percent' AND metric_value <> numerator * 100.0 / NULLIF(denominator, 0));

SELECT 'operations_role_metric_invalid_range', COUNT(*)
FROM yshopping_ads.ads_ecommerce_operations_role_metrics
WHERE (unit = 'percent' AND (metric_value < 0 OR metric_value > 100))
   OR numerator < 0
   OR (denominator IS NOT NULL AND (denominator <= 0 OR numerator > denominator));

SELECT 'operations_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_operations_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
