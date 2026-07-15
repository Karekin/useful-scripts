CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_merchant_entity_status_event AS
SELECT
    event_id, tenant_id, aggregate_type, aggregate_id AS entity_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.entity_type') AS entity_type,
    get_json_string(payload, '$.legal_entity_id') AS legal_entity_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.external_shop_id') AS external_shop_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.reason') AS reason
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.entity.status_changed'
  AND schema_version IN (1,2)
  AND source_system = 'cloudmold-merchant';
