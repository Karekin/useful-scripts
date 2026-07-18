CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_fulfillment_promise_readiness AS
SELECT
    tenant_id,
    fulfillment_id,
    fulfillment_no,
    order_id,
    run_id,
    seller_id,
    warehouse_id,
    carrier_code,
    waybill_no,
    fulfillment_status,
    delivery_promise_version_ref,
    promised_delivery_at,
    promise_frozen_at,
    delivered_at,
    delivery_promise_present,
    comparable_delivery_promise,
    delivered_on_time,
    SUBSTR(COALESCE(delivered_at, promised_delivery_at), 1, 10) AS metric_date,
    CASE
        WHEN delivery_promise_present <> TRUE THEN 'PROMISE_MISSING'
        WHEN fulfillment_status = 'DELIVERED' AND delivered_on_time = TRUE
        THEN 'PROMISED_DELIVERED_ON_TIME'
        WHEN fulfillment_status = 'DELIVERED' AND delivered_on_time = FALSE
        THEN 'PROMISED_DELIVERED_LATE'
        WHEN fulfillment_status IN ('CREATED', 'SHIPPED', 'IN_TRANSIT')
        THEN 'PROMISED_PENDING'
        ELSE 'PROMISE_INCOMPLETE'
    END AS readiness_status,
    data_freshness_at
FROM yshopping_dws.dws_canonical_fulfillment_promise_current;
