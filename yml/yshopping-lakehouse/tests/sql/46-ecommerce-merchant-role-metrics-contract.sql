SELECT 'merchant_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_merchant_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 6 OR COUNT(DISTINCT metric_id) <> 6
) invalid;

SELECT 'merchant_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchant_role_metrics
WHERE metric_id NOT IN (
    'merchant.net_sales_yuan',
    'merchant.new_buyer_count',
    'merchant.store_conversion_rate',
    'marketing.ad_roas',
    'marketing.promotion_roi',
    'merchant.cancellation_rate'
);

SELECT 'merchant_role_metric_null_value', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchant_role_metrics
WHERE metric_value IS NULL
   OR numerator IS NULL
   OR source_row_count <= 0
   OR data_freshness_at IS NULL;

SELECT 'merchant_role_metric_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchant_role_metrics
WHERE (unit = 'count' AND ABS(metric_value - numerator) > 0.000001)
   OR (unit = 'yuan' AND ABS(metric_value - numerator / 100.0) > 0.000001)
   OR (unit = 'percent' AND ABS(metric_value - numerator * 100.0 / NULLIF(denominator, 0)) > 0.000001)
   OR (unit = 'ratio' AND ABS(metric_value - numerator / NULLIF(denominator, 0)) > 0.000001);

SELECT 'merchant_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_merchant_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
