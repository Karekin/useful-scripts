CREATE OR REPLACE VIEW yshopping_dwd.dwd_app_product_review_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS review_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_item_id') AS order_item_id,
    get_json_string(payload, '$.listing_id') AS listing_id,
    get_json_string(payload, '$.listing_offer_id') AS listing_offer_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.canonical_spu_id') AS canonical_spu_id,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    CAST(get_json_string(payload, '$.product_score') AS INT) AS product_score,
    CAST(get_json_string(payload, '$.service_score') AS INT) AS service_score,
    CAST(get_json_string(payload, '$.logistics_score') AS INT) AS logistics_score,
    CAST(get_json_string(payload, '$.overall_score') AS INT) AS overall_score,
    get_json_string(payload, '$.content_digest_sha256') AS content_digest_sha256,
    get_json_string(payload, '$.public_summary') AS public_summary,
    get_json_string(payload, '$.moderation_status') AS moderation_status,
    get_json_string(payload, '$.moderation_policy') AS moderation_policy
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'app.product_review.created'
  AND schema_version = 1
  AND source_system = 'cloudmold-app-commerce';
