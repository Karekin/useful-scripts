-- Lightweight governed KPI surface for the Merchant Operations dashboard.
-- It is intentionally independent from the full cross-role mart so Agent-driven
-- snapshot refreshes do not require StarRocks to plan every commerce domain.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_merchant_role_metrics AS
WITH merchant_sales AS (
    SELECT
        tenant_id,
        SUM(numerator) AS net_sales_amount_minor,
        SUM(source_row_count) AS source_row_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_sales_metrics
    GROUP BY tenant_id
), merchant_acquisition AS (
    SELECT
        tenant_id,
        SUM(new_buyer_count) AS new_buyer_count,
        SUM(paid_buyer_count) AS paid_buyer_count,
        SUM(store_visitor_count) AS store_visitor_count,
        COUNT(*) AS source_row_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_acquisition_metrics
    GROUP BY tenant_id
), marketing AS (
    SELECT
        tenant_id,
        SUM(CASE WHEN ad_roas_status = 'READY' THEN attribution_amount_minor ELSE 0 END)
            AS attribution_amount_minor,
        SUM(CASE WHEN ad_roas_status = 'READY' THEN ad_spend_amount_minor ELSE 0 END)
            AS ad_spend_amount_minor,
        SUM(CASE WHEN promotion_roi_status = 'READY' THEN incremental_contribution_profit_minor ELSE 0 END)
            AS incremental_contribution_profit_minor,
        SUM(CASE WHEN promotion_roi_status = 'READY' THEN promotion_cost_minor ELSE 0 END)
            AS promotion_cost_minor,
        COUNT(*) AS source_row_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_marketing_campaign_performance
    GROUP BY tenant_id
), metric_rows AS (
    SELECT
        tenant_id,
        'merchant.net_sales_yuan' AS metric_id,
        CAST(net_sales_amount_minor / 100.0 AS DECIMAL(38,6)) AS metric_value,
        CAST(net_sales_amount_minor AS DECIMAL(38,6)) AS numerator,
        CAST(100 AS DECIMAL(38,6)) AS denominator,
        'yuan' AS unit,
        source_row_count,
        'Governed merchant order-item sales less discounts, settled refunds, and merchant-responsible cancellation residuals' AS evidence_note,
        data_freshness_at
    FROM merchant_sales
    UNION ALL
    SELECT
        tenant_id,
        'merchant.new_buyer_count',
        CAST(new_buyer_count AS DECIMAL(38,6)),
        CAST(new_buyer_count AS DECIMAL(38,6)),
        CAST(NULL AS DECIMAL(38,6)),
        'count',
        source_row_count,
        'Distinct buyers whose first strictly attributed paid order is with the governed merchant',
        data_freshness_at
    FROM merchant_acquisition
    UNION ALL
    SELECT
        tenant_id,
        'merchant.store_conversion_rate',
        CAST(paid_buyer_count * 100.0 / NULLIF(store_visitor_count, 0) AS DECIMAL(38,6)),
        CAST(paid_buyer_count AS DECIMAL(38,6)),
        CAST(store_visitor_count AS DECIMAL(38,6)),
        'percent',
        source_row_count,
        'Strict shop-level paid buyers divided by validated listing-offer store visitors',
        data_freshness_at
    FROM merchant_acquisition
    UNION ALL
    SELECT
        tenant_id,
        'marketing.ad_roas',
        CAST(attribution_amount_minor * 1.0 / NULLIF(ad_spend_amount_minor, 0) AS DECIMAL(38,6)),
        CAST(attribution_amount_minor AS DECIMAL(38,6)),
        CAST(ad_spend_amount_minor AS DECIMAL(38,6)),
        'ratio',
        source_row_count,
        'Governed attributed order amount divided by immutable advertising spend ledger',
        data_freshness_at
    FROM marketing
    UNION ALL
    SELECT
        tenant_id,
        'marketing.promotion_roi',
        CAST(incremental_contribution_profit_minor * 1.0 / NULLIF(promotion_cost_minor, 0) AS DECIMAL(38,6)),
        CAST(incremental_contribution_profit_minor AS DECIMAL(38,6)),
        CAST(promotion_cost_minor AS DECIMAL(38,6)),
        'ratio',
        source_row_count,
        'Governed experiment incremental contribution profit divided by booked promotion cost',
        data_freshness_at
    FROM marketing
    UNION ALL
    SELECT
        tenant_id,
        metric_id,
        metric_value,
        numerator,
        denominator,
        unit,
        source_row_count,
        evidence_note,
        data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_cancellation_metrics
)
SELECT
    tenant_id,
    metric_id,
    metric_value,
    numerator,
    denominator,
    unit,
    'LOCAL_TEST_CANONICAL_CURRENT' AS evidence_scope,
    source_row_count,
    evidence_note,
    data_freshness_at
FROM metric_rows
WHERE metric_value IS NOT NULL;
