-- Lightweight governed KPI surface for Finance & Risk plus the executive
-- contribution-margin guardrail. Money remains in CNY yuan at the reporting
-- boundary; source ledgers retain integer minor units.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_finance_role_metrics AS
WITH profitability AS (
    SELECT *
    FROM yshopping_ads.ads_canonical_commerce_profitability
), platform_revenue AS (
    SELECT *
    FROM yshopping_ads.ads_canonical_platform_revenue_take_rate
    WHERE readiness_status = 'READY'
), metric_rows AS (
    SELECT
        tenant_id,
        'finance.net_revenue_yuan' AS metric_id,
        CAST(net_revenue_amount_minor / 100.0 AS DECIMAL(38,6)) AS metric_value,
        CAST(net_revenue_amount_minor / 100.0 AS DECIMAL(38,6)) AS numerator,
        CAST(NULL AS DECIMAL(38,6)) AS denominator,
        'yuan' AS unit,
        profitable_order_count AS source_row_count,
        'Order-line net sales after governed discount allocation and cumulative refunds' AS evidence_note,
        data_freshness_at
    FROM profitability
    UNION ALL
    SELECT
        tenant_id,
        'finance.gross_profit_yuan',
        CAST(gross_profit_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(gross_profit_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(NULL AS DECIMAL(38,6)),
        'yuan',
        profitable_order_count,
        'Net sales less merchandise cost frozen on canonical order items',
        data_freshness_at
    FROM profitability
    UNION ALL
    SELECT
        tenant_id,
        'finance.contribution_margin_rate',
        CAST(contribution_margin_rate * 100.0 AS DECIMAL(38,6)),
        CAST(contribution_profit_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(net_revenue_amount_minor / 100.0 AS DECIMAL(38,6)),
        'percent',
        profitable_order_count,
        'Contribution profit after merchandise, variable fulfillment, after-sale loss and platform-funded marketing divided by net sales',
        data_freshness_at
    FROM profitability
    UNION ALL
    SELECT
        tenant_id,
        'platform.take_rate',
        CAST(platform_take_rate * 100.0 AS DECIMAL(38,6)),
        CAST(platform_revenue_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(gmv_amount_minor / 100.0 AS DECIMAL(38,6)),
        'percent',
        1,
        'Governed platform revenue ledger divided by canonical GMV',
        data_freshness_at
    FROM platform_revenue
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
    FROM yshopping_ads.ads_canonical_risk_commerce_metrics
    WHERE metric_id IN ('risk.flagged_order_rate', 'risk.chargeback_rate', 'risk.loss_amount_yuan')
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
