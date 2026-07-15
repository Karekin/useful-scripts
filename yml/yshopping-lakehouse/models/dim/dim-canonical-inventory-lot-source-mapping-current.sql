CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_lot_source_mapping_current AS
WITH latest AS (
    SELECT *
    FROM (
        SELECT event.*,
               COUNT(*) OVER (PARTITION BY tenant_id, mapping_id) AS mapping_event_count,
               MIN(mapping_version) OVER (PARTITION BY tenant_id, mapping_id) AS minimum_mapping_version,
               ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, mapping_id
                   ORDER BY mapping_version DESC, recorded_at DESC, event_id DESC
               ) AS mapping_version_rank
        FROM yshopping_dwd.dwd_canonical_inventory_lot_source_mapping_event event
    ) ranked
    WHERE mapping_version_rank = 1
), effective_counts AS (
    SELECT tenant_id, mapping_source_system, source_type, source_id, COUNT(*) AS effective_source_mapping_count
    FROM latest
    WHERE current_status = 'ACTIVE'
      AND valid_from <= UTC_TIMESTAMP()
      AND (valid_to IS NULL OR valid_to > UTC_TIMESTAMP())
    GROUP BY tenant_id, mapping_source_system, source_type, source_id
)
SELECT
    latest.event_id,
    latest.tenant_id,
    latest.mapping_id,
    latest.mapping_version,
    latest.mapping_source_system,
    latest.source_type,
    latest.source_id,
    latest.lot_id,
    latest.valid_from,
    latest.valid_to,
    latest.previous_status,
    latest.current_status,
    latest.change_type,
    latest.verification_ref,
    latest.change_reason_code,
    latest.run_id,
    latest.migration_run_id,
    latest.occurred_at,
    latest.recorded_at,
    latest.correlation_id,
    latest.mapping_event_count,
    latest.minimum_mapping_version,
    CASE WHEN latest.current_status = 'ACTIVE'
          AND latest.valid_from <= UTC_TIMESTAMP()
          AND (latest.valid_to IS NULL OR latest.valid_to > UTC_TIMESTAMP())
         THEN 1 ELSE 0 END AS is_effective,
    COALESCE(effective_counts.effective_source_mapping_count, 0) AS effective_source_mapping_count
FROM latest
LEFT JOIN effective_counts
  ON effective_counts.tenant_id = latest.tenant_id
 AND effective_counts.mapping_source_system = latest.mapping_source_system
 AND effective_counts.source_type = latest.source_type
 AND effective_counts.source_id = latest.source_id;
