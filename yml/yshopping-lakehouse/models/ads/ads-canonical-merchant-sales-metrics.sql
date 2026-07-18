CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_merchant_sales_metrics AS
SELECT
    tenant_id,
    merchant_id,
    'merchant.net_sales_yuan' AS metric_id,
    CAST(SUM(merchant_net_sales_amount_minor) / 100.0 AS DECIMAL(38,6)) AS metric_value,
    CAST(SUM(merchant_net_sales_amount_minor) AS DECIMAL(38,6)) AS numerator,
    CAST(100 AS DECIMAL(38,6)) AS denominator,
    'yuan' AS unit,
    COUNT(*) AS source_row_count,
    'Frozen listing_offer_id to merchant mapping; booked order-item sales less governed discounts, settled refunds, and any unrefunded residual on merchant-responsible paid cancellation' AS evidence_note,
    MAX(data_freshness_at) AS data_freshness_at
FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
GROUP BY tenant_id, merchant_id;
