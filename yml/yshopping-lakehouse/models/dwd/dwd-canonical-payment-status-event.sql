CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_payment_status_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS payment_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.payment_no') AS payment_no,
    get_json_string(payload, '$.order_id') AS order_id,
    CAST(get_json_string(payload, '$.transaction_id') AS BIGINT) AS transaction_id,
    get_json_string(payload, '$.transaction_type') AS transaction_type,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    CAST(get_json_string(payload, '$.payable_amount_minor') AS BIGINT) AS payable_amount_minor,
    CAST(get_json_string(payload, '$.captured_amount_minor') AS BIGINT) AS captured_amount_minor,
    CAST(get_json_string(payload, '$.refunded_amount_minor') AS BIGINT) AS refunded_amount_minor,
    CAST(get_json_string(payload, '$.refund_amount_minor') AS BIGINT) AS refund_amount_minor,
    CAST(get_json_string(payload, '$.remaining_refundable_amount_minor') AS BIGINT)
        AS remaining_refundable_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.provider_code') AS provider_code,
    get_json_string(payload, '$.provider_transaction_id') AS provider_transaction_id,
    get_json_bool(payload, '$.test_mode') AS test_mode,
    get_json_string(payload, '$.reason') AS reason
    ,get_json_string(payload, '$.cancellation_saga_id') AS cancellation_saga_id
    ,CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'payment.status.changed'
  AND schema_version IN (1, 2, 3)
  AND source_system = 'cloudmold-payment';
