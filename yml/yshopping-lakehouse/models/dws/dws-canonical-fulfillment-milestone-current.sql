CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_fulfillment_milestone_current AS
SELECT
    tenant_id,
    run_id,
    fulfillment_id,
    fulfillment_no,
    order_id,
    shipment_id,
    current_status AS fulfillment_status,
    aggregate_version,
    fulfillment_event_count,
    carrier_code,
    waybill_no,
    shipped_at,
    in_transit_at,
    delivered_at,
    CASE WHEN shipped_at IS NOT NULL THEN 1 ELSE 0 END AS shipped_milestone_count,
    CASE WHEN in_transit_at IS NOT NULL THEN 1 ELSE 0 END AS in_transit_milestone_count,
    CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END AS delivered_milestone_count,
    CASE
        WHEN shipped_at IS NOT NULL
         AND in_transit_at IS NOT NULL
         AND delivered_at IS NOT NULL
         AND shipped_at <= in_transit_at
         AND in_transit_at <= delivered_at
        THEN TRUE ELSE FALSE
    END AS milestone_time_valid,
    recorded_at AS data_freshness_at
FROM yshopping_dim.dim_canonical_fulfillment_current;
