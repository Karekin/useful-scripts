CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_listing_review_event AS
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
    CAST(get_json_string(payload, '$.revision') AS INT) AS revision,
    get_json_string(payload, '$.stage') AS review_stage,
    get_json_string(payload, '$.decision') AS review_decision,
    get_json_string(payload, '$.reason') AS reason
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'listing.review.decided'
  AND schema_version = 1
  AND source_system = 'cloudmold-listing';
