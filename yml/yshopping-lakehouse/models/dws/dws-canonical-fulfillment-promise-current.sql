CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_fulfillment_promise_current AS
SELECT
    tenant_id,
    run_id,
    fulfillment_id,
    fulfillment_no,
    order_id,
    seller_id,
    warehouse_id,
    shipment_id,
    carrier_code,
    waybill_no,
    current_status AS fulfillment_status,
    delivery_promise_version_ref,
    promised_delivery_at,
    promise_frozen_at,
    delivered_at,
    CASE
        WHEN delivery_promise_version_ref IS NOT NULL
         AND promised_delivery_at IS NOT NULL
         AND promise_frozen_at IS NOT NULL
        THEN TRUE ELSE FALSE
    END AS delivery_promise_present,
    CASE
        WHEN delivered_at IS NOT NULL
         AND promised_delivery_at IS NOT NULL
         AND delivered_at <= promised_delivery_at
        THEN TRUE
        WHEN delivered_at IS NOT NULL
         AND promised_delivery_at IS NOT NULL
        THEN FALSE
        ELSE NULL
    END AS delivered_on_time,
    CASE
        WHEN delivered_at IS NOT NULL AND promised_delivery_at IS NOT NULL
        THEN TRUE ELSE FALSE
    END AS comparable_delivery_promise,
    recorded_at AS data_freshness_at
FROM yshopping_dim.dim_canonical_fulfillment_current;
