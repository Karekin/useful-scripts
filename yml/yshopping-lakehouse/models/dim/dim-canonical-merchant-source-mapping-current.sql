CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_merchant_source_mapping_current AS
SELECT
    event_id, tenant_id, mapping_id, mapping_source_system, source_type, source_id,
    target_type, target_id, valid_from, valid_to, verification_ref, run_id, migration_run_id,
    previous_status, current_status, aggregate_version, occurred_at, recorded_at, correlation_id,
    active_mapping_count
FROM (
    SELECT effective.*,
           COUNT(*) OVER (
               PARTITION BY tenant_id, mapping_source_system, source_type, source_id
           ) AS active_mapping_count
    FROM (
        SELECT latest.*
        FROM (
            SELECT event.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, mapping_id
                       ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
                   ) AS mapping_version_rank
            FROM yshopping_dwd.dwd_canonical_merchant_source_mapping_event event
        ) latest
        WHERE mapping_version_rank = 1
          AND current_status = 'ACTIVE'
          AND valid_from <= UTC_TIMESTAMP()
          AND (valid_to IS NULL OR valid_to > UTC_TIMESTAMP())
    ) effective
) qualified
WHERE active_mapping_count = 1;
