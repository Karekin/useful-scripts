CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_identity_source_current AS
SELECT
    event_id, tenant_id, source_identity_id, identity_source_system, source_type, source_id,
    principal_id, principal_type, principal_status, source_status,
    aggregate_version, occurred_at, recorded_at, correlation_id
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, identity_source_system, source_type, source_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_identity_source_link_event event
) ranked
WHERE row_num = 1;
