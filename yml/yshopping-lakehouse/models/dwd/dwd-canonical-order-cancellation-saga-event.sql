CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_order_cancellation_saga_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS saga_id,
    get_json_string(payload, '$.saga_id') AS payload_saga_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_no') AS order_no,
    get_json_string(payload, '$.cancellation_mode') AS cancellation_mode,
    get_json_string(payload, '$.order_status_at_request') AS order_status_at_request,
    get_json_string(payload, '$.payment_id') AS payment_id,
    CAST(get_json_string(payload, '$.payment_refund_transaction_id') AS BIGINT) AS payment_refund_transaction_id,
    get_json_string(payload, '$.payment_status') AS payment_status,
    CAST(get_json_string(payload, '$.expected_fulfillment_count') AS INT) AS expected_fulfillment_count,
    CAST(get_json_string(payload, '$.cancelled_fulfillment_count') AS INT) AS cancelled_fulfillment_count,
    json_query(payload, '$.fulfillments') AS fulfillments,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.active_step') AS active_step,
    CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal,
    CAST(get_json_string(payload, '$.attempt') AS INT) AS attempt,
    get_json_string(payload, '$.reason') AS reason,
    get_json_string(payload, '$.responsibility_party') AS responsibility_party,
    get_json_string(payload, '$.responsibility_code') AS responsibility_code,
    CASE get_json_string(payload, '$.counts_toward_paid_cancellation_rate')
        WHEN 'true' THEN TRUE
        WHEN 'false' THEN FALSE
        ELSE NULL
    END AS counts_toward_paid_cancellation_rate,
    CAST(get_json_string(payload, '$.expected_reservation_count') AS INT) AS expected_reservation_count,
    CAST(get_json_string(payload, '$.released_reservation_count') AS INT) AS released_reservation_count,
    json_query(payload, '$.reservations') AS reservations,
    get_json_string(payload, '$.error_code') AS error_code,
    get_json_string(payload, '$.error_message') AS error_message,
    get_json_string(payload, '$.next_retry_at') AS next_retry_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.cancellation_saga.status_changed'
  AND schema_version IN (1, 2)
  AND source_system = 'cloudmold-order';
