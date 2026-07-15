CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_merchant_onboarding_current AS
SELECT
    event_id, tenant_id, application_id, legal_entity_id, owner_principal_id,
    channel_code, external_shop_id, merchant_id, shop_id, previous_status, current_status,
    aggregate_version, occurred_at, recorded_at, correlation_id, onboarding_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, application_id) AS onboarding_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, application_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_merchant_onboarding_event event
) ranked
WHERE row_num = 1;
