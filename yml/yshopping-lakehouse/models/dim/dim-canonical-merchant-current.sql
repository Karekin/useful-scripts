CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_merchant_current AS
SELECT
    event_id, tenant_id, entity_id AS merchant_id, legal_entity_id,
    previous_status, current_status, aggregate_version, occurred_at, recorded_at,
    correlation_id, entity_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, entity_id) AS entity_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, entity_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_merchant_entity_status_event event
    WHERE entity_type = 'MERCHANT'
) ranked
WHERE row_num = 1;
