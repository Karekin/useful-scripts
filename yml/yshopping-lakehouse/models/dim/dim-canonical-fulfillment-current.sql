CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_fulfillment_current AS
SELECT
    event_id, schema_version, tenant_id, fulfillment_id, fulfillment_no, order_id, order_no, run_id,
    aggregate_version, seller_id, warehouse_id, previous_status, current_status,
    shipment_id, carrier_code, waybill_no, shipped_at, in_transit_at, delivered_at,
    reason, cancellation_saga_id, step_ordinal,
    correlation_id, occurred_at, recorded_at, fulfillment_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, fulfillment_id) AS fulfillment_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, fulfillment_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_fulfillment_status_event event
) ranked
WHERE row_num = 1;
