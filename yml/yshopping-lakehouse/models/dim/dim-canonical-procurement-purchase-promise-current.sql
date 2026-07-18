CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_procurement_purchase_promise_current AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    promise_id,
    run_id,
    promise_key,
    purchase_order_id,
    purchase_order_no,
    purchase_order_line_id,
    supplier_id,
    product_id,
    product_unit_id,
    ordered_quantity,
    promised_receipt_at,
    promise_timezone,
    grace_minutes,
    pause_minutes,
    promise_frozen_at,
    previous_status,
    current_status,
    reason,
    correlation_id,
    occurred_at,
    recorded_at,
    promise_event_count
FROM (
    SELECT
        event.*,
        COUNT(*) OVER (PARTITION BY tenant_id, promise_id) AS promise_event_count,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, promise_id
            ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
        ) AS row_num
    FROM yshopping_dwd.dwd_canonical_procurement_purchase_promise_event event
) ranked
WHERE row_num = 1;
