CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_order_status_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS order_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.order_no') AS order_no,
    get_json_string(payload, '$.buyer_id') AS buyer_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    CAST(get_json_string(payload, '$.product_amount_minor') AS BIGINT) AS product_amount_minor,
    CAST(get_json_string(payload, '$.shipping_amount_minor') AS BIGINT) AS shipping_amount_minor,
    CAST(get_json_string(payload, '$.discount_amount_minor') AS BIGINT) AS discount_amount_minor,
    CAST(get_json_string(payload, '$.payable_amount_minor') AS BIGINT) AS payable_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.payment_id') AS payment_id,
    get_json_string(payload, '$.cancellation_saga_id') AS cancellation_saga_id,
    get_json_string(payload, '$.pre_cancellation_status') AS pre_cancellation_status,
    get_json_string(payload, '$.cancellation_mode') AS cancellation_mode,
    get_json_string(payload, '$.responsibility_party') AS responsibility_party,
    get_json_string(payload, '$.responsibility_code') AS responsibility_code,
    CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal,
    get_json_string(payload, '$.fulfillment_id') AS fulfillment_id,
    get_json_string(payload, '$.shipment_id') AS shipment_id,
    get_json_string(payload, '$.refund_id') AS refund_id,
    get_json_string(payload, '$.reason') AS reason,
    json_query(payload, '$.items') AS items
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.status.changed'
  AND schema_version IN (1, 2, 3)
  AND source_system = 'cloudmold-order';
