SELECT 'merchandise_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_merchandise_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 3 OR COUNT(DISTINCT metric_id) <> 3
) invalid;

SELECT 'merchandise_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchandise_role_metrics
WHERE metric_id NOT IN ('inventory.turnover_days', 'inventory.aged_stock_value_yuan', 'procurement.otif_rate');

SELECT 'merchandise_role_metric_null_or_invalid', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchandise_role_metrics
WHERE metric_value IS NULL OR numerator IS NULL OR source_row_count <= 0 OR data_freshness_at IS NULL
   OR metric_value < 0 OR numerator < 0
   OR (denominator IS NOT NULL AND denominator <= 0)
   OR (unit = 'percent' AND (metric_value > 100 OR numerator > denominator));

SELECT 'merchandise_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchandise_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
