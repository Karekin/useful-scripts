-- Canonical commerce behavior session events. This model is intentionally append-only
-- and must not infer historical journey facts from legacy current-state browse/cart tables.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_commerce_session_status_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS session_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.principal_id') AS principal_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.entrypoint_code') AS entrypoint_code,
    CAST(get_json_string(payload, '$.started_at') AS DATETIME) AS started_at,
    CAST(get_json_string(payload, '$.last_activity_at') AS DATETIME) AS last_activity_at,
    get_json_string(payload, '$.source_system') AS source_system_ref,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'commerce.session.status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-commerce-behavior';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_commerce_session_identity_link_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS session_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.previous_principal_id') AS previous_principal_id,
    get_json_string(payload, '$.current_principal_id') AS current_principal_id,
    CAST(get_json_string(payload, '$.link_version') AS BIGINT) AS link_version,
    get_json_string(payload, '$.session_status') AS session_status,
    CAST(get_json_string(payload, '$.linked_at') AS DATETIME) AS linked_at,
    get_json_string(payload, '$.source_system') AS source_system_ref,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'commerce.session.identity_linked'
  AND schema_version = 1
  AND source_system = 'cloudmold-commerce-behavior';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_commerce_behavior_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS session_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.behavior_id') AS behavior_id,
    CAST(get_json_string(payload, '$.session_version') AS BIGINT) AS session_version,
    get_json_string(payload, '$.behavior_type') AS behavior_type,
    get_json_string(payload, '$.principal_id') AS principal_id,
    get_json_string(payload, '$.canonical_spu_id') AS canonical_spu_id,
    get_json_string(payload, '$.sku_id') AS sku_id,
    get_json_string(payload, '$.listing_id') AS listing_id,
    get_json_string(payload, '$.listing_offer_id') AS listing_offer_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.search_token') AS search_token,
    get_json_string(payload, '$.result_set_token') AS result_set_token,
    CAST(get_json_string(payload, '$.result_position') AS INT) AS result_position,
    CAST(get_json_string(payload, '$.quantity') AS INT) AS quantity,
    get_json_string(payload, '$.checkout_token') AS checkout_token,
    CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS behavior_occurred_at,
    get_json_string(payload, '$.source_system') AS source_system_ref,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'commerce.behavior.recorded'
  AND schema_version = 1
  AND source_system = 'cloudmold-commerce-behavior';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS session_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.attribution_id') AS attribution_id,
    CAST(get_json_string(payload, '$.session_version') AS BIGINT) AS session_version,
    get_json_string(payload, '$.principal_id') AS principal_id,
    get_json_string(payload, '$.checkout_token') AS checkout_token,
    get_json_string(payload, '$.order_id') AS order_id,
    CAST(get_json_string(payload, '$.order_version') AS BIGINT) AS order_version,
    get_json_string(payload, '$.payment_id') AS payment_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.order_status') AS order_status,
    CAST(get_json_string(payload, '$.attributed_at') AS DATETIME) AS attributed_at,
    get_json_string(payload, '$.source_system') AS source_system_ref,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'commerce.session.payment_attributed'
  AND schema_version = 1
  AND source_system = 'cloudmold-commerce-behavior';
