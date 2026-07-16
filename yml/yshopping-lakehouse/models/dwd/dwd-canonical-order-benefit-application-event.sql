CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_order_benefit_application_event AS
SELECT
    event_id,
    schema_version,
    source_system,
    tenant_id,
    aggregate_type,
    aggregate_id AS envelope_order_id,
    aggregate_version,
    event_sequence,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_no') AS order_no,
    get_json_string(payload, '$.benefit_application_id') AS benefit_application_id,
    get_json_string(payload, '$.application_key') AS application_key,
    get_json_string(payload, '$.benefit_type') AS benefit_type,
    get_json_string(payload, '$.benefit_source_type') AS benefit_source_type,
    get_json_string(payload, '$.benefit_source_id') AS benefit_source_id,
    CAST(get_json_string(payload, '$.benefit_source_version') AS BIGINT) AS benefit_source_version,
    get_json_string(payload, '$.entitlement_id') AS entitlement_id,
    CAST(get_json_string(payload, '$.amount_minor') AS BIGINT) AS amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.calculation_digest') AS calculation_digest,
    json_query(payload, '$.allocations') AS allocations
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.benefit_application.recorded'
  AND schema_version = 1
  AND source_system = 'cloudmold-order';
