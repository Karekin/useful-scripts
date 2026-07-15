CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_merchant_onboarding_event AS
SELECT
    event_id, tenant_id, aggregate_id AS application_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.legal_entity_id') AS legal_entity_id,
    get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
    get_json_string(payload, '$.channel_code') AS channel_code,
    get_json_string(payload, '$.external_shop_id') AS external_shop_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.onboarding.status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-merchant';
