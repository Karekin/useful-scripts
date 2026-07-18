SELECT 'service_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_service_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 4 OR COUNT(DISTINCT metric_id) <> 4
) invalid;

SELECT 'service_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_service_role_metrics
WHERE metric_id NOT IN (
    'service.first_contact_resolution_rate', 'service.resolution_sla_rate',
    'service.order_defect_rate', 'buyer.csat'
);

SELECT 'service_role_metric_null_or_invalid', COUNT(*)
FROM yshopping_ads.ads_ecommerce_service_role_metrics
WHERE metric_value IS NULL OR numerator IS NULL OR denominator IS NULL
   OR source_row_count <= 0 OR data_freshness_at IS NULL
   OR metric_value < 0 OR metric_value > 100
   OR denominator <= 0 OR numerator > denominator;

SELECT 'service_role_metric_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_service_role_metrics
WHERE ABS(metric_value - numerator * 100.0 / NULLIF(denominator, 0)) > 0.0001;

SELECT 'service_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_service_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
