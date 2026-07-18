CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_fulfillment_promise_metrics AS
SELECT
    tenant_id,
    metric_date,
    seller_id,
    warehouse_id,
    carrier_code,
    COUNT(IF(comparable_delivery_promise = TRUE, 1, NULL)) AS delivered_promise_count,
    COUNT(IF(delivered_on_time = TRUE, 1, NULL)) AS on_time_delivery_count,
    COUNT(IF(delivered_on_time = FALSE, 1, NULL)) AS late_delivery_count,
    CAST(
        COUNT(IF(delivered_on_time = TRUE, 1, NULL)) * 100.0
        / NULLIF(COUNT(IF(comparable_delivery_promise = TRUE, 1, NULL)), 0)
        AS DECIMAL(18,6)
    ) AS fulfillment_on_time_delivery_rate,
    CAST(
        COUNT(IF(delivered_on_time = TRUE, 1, NULL)) * 100.0
        / NULLIF(COUNT(IF(comparable_delivery_promise = TRUE, 1, NULL)), 0)
        AS DECIMAL(18,6)
    ) AS buyer_delivery_promise_hit_rate,
    MAX(data_freshness_at) AS data_freshness_at
FROM yshopping_ads.ads_canonical_fulfillment_promise_readiness
WHERE delivery_promise_present = TRUE
GROUP BY tenant_id, metric_date, seller_id, warehouse_id, carrier_code;
