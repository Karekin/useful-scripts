CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_catalog_entity_status_current AS
SELECT
    event_id, tenant_id, entity_type, entity_id, business_code,
    previous_status, current_status, lifecycle_action, reason,
    aggregate_version, correlation_id, occurred_at, recorded_at
FROM (
    SELECT change_event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, entity_type, entity_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS version_rank
    FROM yshopping_dwd.dwd_canonical_catalog_status_change change_event
) ranked
WHERE version_rank = 1;
