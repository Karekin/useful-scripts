SELECT 'finance_role_metric_count_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_ecommerce_finance_role_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 7 OR COUNT(DISTINCT metric_id) <> 7
) invalid;

SELECT 'finance_role_metric_unknown_id', COUNT(*)
FROM yshopping_ads.ads_ecommerce_finance_role_metrics
WHERE metric_id NOT IN (
    'finance.net_revenue_yuan', 'finance.gross_profit_yuan', 'finance.contribution_margin_rate',
    'platform.take_rate', 'risk.flagged_order_rate', 'risk.chargeback_rate', 'risk.loss_amount_yuan'
);

SELECT 'finance_role_metric_null_or_invalid', COUNT(*)
FROM yshopping_ads.ads_ecommerce_finance_role_metrics
WHERE metric_value IS NULL OR numerator IS NULL OR source_row_count <= 0 OR data_freshness_at IS NULL
   OR (unit = 'percent' AND (metric_value < 0 OR metric_value > 100))
   OR (denominator IS NOT NULL AND denominator <= 0);

SELECT 'finance_role_metric_percent_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_finance_role_metrics
WHERE unit = 'percent'
  AND ABS(metric_value - numerator * 100.0 / NULLIF(denominator, 0)) > 0.0001;

SELECT 'finance_role_metric_evidence_scope_mismatch', COUNT(*)
FROM yshopping_ads.ads_ecommerce_finance_role_metrics
WHERE evidence_scope <> 'LOCAL_TEST_CANONICAL_CURRENT';
