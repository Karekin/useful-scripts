CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_order_current AS
SELECT
    event_id, schema_version, tenant_id, order_id, order_no, run_id, buyer_id, aggregate_version,
    previous_status, current_status, product_amount_minor, shipping_amount_minor,
    discount_amount_minor, payable_amount_minor, currency_code, payment_id,
    cancellation_saga_id, pre_cancellation_status, cancellation_mode, step_ordinal,
    fulfillment_id, shipment_id, refund_id,
    reason, correlation_id, occurred_at, recorded_at, order_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, order_id) AS order_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, order_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_order_status_event event
) ranked
WHERE row_num = 1;
