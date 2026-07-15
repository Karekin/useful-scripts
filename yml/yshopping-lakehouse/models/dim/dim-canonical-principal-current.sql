CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_principal_current AS
SELECT
    event_id, tenant_id, principal_id, principal_type, principal_status,
    aggregate_version, occurred_at, recorded_at, correlation_id, principal_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, principal_id) AS principal_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, principal_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_identity_source_link_event event
) ranked
WHERE row_num = 1;
