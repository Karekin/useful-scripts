CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_listing_unpublish_saga_event AS
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
    get_json_string(payload, '$.source_event_id') AS source_event_id,
    get_json_string(payload, '$.source_entity_type') AS source_entity_type,
    CAST(get_json_string(payload, '$.source_aggregate_version') AS BIGINT) AS source_aggregate_version,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.active_step') AS active_step,
    CAST(get_json_string(payload, '$.attempt') AS INT) AS attempt,
    get_json_string(payload, '$.reason') AS reason,
    CAST(get_json_string(payload, '$.expected_listing_count') AS INT) AS expected_listing_count,
    CAST(get_json_string(payload, '$.unpublished_listing_count') AS INT) AS unpublished_listing_count,
    CAST(get_json_string(payload, '$.skipped_listing_count') AS INT) AS skipped_listing_count,
    get_json_string(payload, '$.error_code') AS error_code,
    get_json_string(payload, '$.error_message') AS error_message,
    get_json_string(payload, '$.next_retry_at') AS next_retry_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'listing.sales_eligibility_enforcement.status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-listing';
