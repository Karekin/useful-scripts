CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_procurement_purchase_promise_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS promise_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.promise_key') AS promise_key,
    CAST(get_json_string(payload, '$.purchase_order_id') AS BIGINT) AS purchase_order_id,
    get_json_string(payload, '$.purchase_order_no') AS purchase_order_no,
    CAST(get_json_string(payload, '$.purchase_order_line_id') AS BIGINT) AS purchase_order_line_id,
    CAST(get_json_string(payload, '$.supplier_id') AS BIGINT) AS supplier_id,
    CAST(get_json_string(payload, '$.product_id') AS BIGINT) AS product_id,
    CAST(get_json_string(payload, '$.product_unit_id') AS BIGINT) AS product_unit_id,
    CAST(get_json_string(payload, '$.ordered_quantity') AS DECIMAL(24,6)) AS ordered_quantity,
    CAST(get_json_string(payload, '$.promised_receipt_at') AS DATETIME) AS promised_receipt_at,
    get_json_string(payload, '$.promise_timezone') AS promise_timezone,
    CAST(get_json_string(payload, '$.grace_minutes') AS INT) AS grace_minutes,
    CAST(get_json_string(payload, '$.pause_minutes') AS INT) AS pause_minutes,
    CAST(get_json_string(payload, '$.promise_frozen_at') AS DATETIME) AS promise_frozen_at,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.reason') AS reason
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'procurement.purchase_promise.status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-integration-yudao';
