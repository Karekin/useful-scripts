CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_listing_status_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS listing_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.listing_no') AS listing_no,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.canonical_spu_id') AS canonical_spu_id,
    CAST(get_json_string(payload, '$.revision') AS INT) AS revision,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    CAST(get_json_string(payload, '$.completion_passed') AS BOOLEAN) AS completion_passed,
    CAST(get_json_string(payload, '$.business_approved') AS BOOLEAN) AS business_approved,
    CAST(get_json_string(payload, '$.risk_approved') AS BOOLEAN) AS risk_approved,
    get_json_string(payload, '$.reason') AS reason,
    json_query(payload, '$.offers') AS offers
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'listing.status.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-listing';
