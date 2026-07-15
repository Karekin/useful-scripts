CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_migration_shadow_round AS
WITH admitted_batch AS (
    SELECT * FROM (
        SELECT b.*,ROW_NUMBER() OVER (
          PARTITION BY tenant_id,pilot_batch_id ORDER BY recorded_at DESC,event_id DESC
        ) AS admission_rank
        FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event b
        WHERE batch_status='ADMISSION_PASSED' AND batch_version=4
    ) x WHERE admission_rank=1
), admitted_item AS (
    SELECT * FROM (
        SELECT i.*,ROW_NUMBER() OVER (
          PARTITION BY tenant_id,pilot_batch_id,pilot_item_id ORDER BY recorded_at DESC,event_id DESC
        ) AS admission_rank
        FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event i
        WHERE item_status='ADMISSION_PASSED' AND item_version=3
    ) x WHERE admission_rank=1
), round_chain AS (
    SELECT r.*,
           LAG(source_gtid_set) OVER (PARTITION BY tenant_id,shadow_window_id ORDER BY round_sequence) AS prior_source_gtid_set,
           LAG(target_gtid_set) OVER (PARTITION BY tenant_id,shadow_window_id ORDER BY round_sequence) AS prior_target_gtid_set
    FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_round_event r
), comparison_dedup AS (
    SELECT
        tenant_id,shadow_window_id,shadow_round_id,pilot_batch_id,pilot_item_id,round_sequence,
        COUNT(*) AS comparison_event_count,
        MIN(manifest_ordinal) AS manifest_ordinal,MIN(item_scope_hash) AS item_scope_hash,
        MIN(manifest_hash) AS manifest_hash,MIN(expected_item_set_hash) AS expected_item_set_hash,
        MIN(source_gtid_set) AS source_gtid_set,MIN(target_gtid_set) AS target_gtid_set,
        MIN(source_version) AS source_version,MIN(source_snapshot_hash) AS source_snapshot_hash,
        MIN(source_grain_hash) AS source_grain_hash,MIN(target_grain_hash) AS target_grain_hash,
        MIN(source_on_hand_quantity) AS source_on_hand_quantity,MIN(target_on_hand_quantity) AS target_on_hand_quantity,
        MIN(source_reserved_quantity) AS source_reserved_quantity,MIN(target_reserved_quantity) AS target_reserved_quantity,
        MIN(source_in_transit_quantity) AS source_in_transit_quantity,MIN(target_in_transit_quantity) AS target_in_transit_quantity,
        MIN(CAST(source_available AS INT)) AS source_available,
        MIN(CAST(target_available AS INT)) AS target_available,
        MIN(CAST(comparable AS INT)) AS comparable,
        MIN(target_projection_kind) AS target_projection_kind,
        MAX(CAST(target_materialized AS INT)) AS target_materialized,
        MIN(comparison_result) AS comparison_result,
        MIN(difference_fields_json) AS difference_fields_json,
        MIN(reason_codes_json) AS reason_codes_json,
        MIN(source_observed_at) AS source_observed_at,MIN(target_observed_at) AS target_observed_at,
        MAX(CAST(execution_available AS INT)) AS execution_available,
        MAX(CAST(cutover_ready AS INT)) AS cutover_ready
    FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_item_comparison_event
    GROUP BY tenant_id,shadow_window_id,shadow_round_id,pilot_batch_id,pilot_item_id,round_sequence
), comparison_ordered AS (
    SELECT c.*,
           LAG(source_version) OVER (
             PARTITION BY tenant_id,shadow_window_id,pilot_item_id ORDER BY round_sequence
           ) AS prior_source_version
    FROM comparison_dedup c
), denominator AS (
    SELECT
        r.tenant_id,r.shadow_window_id,r.shadow_round_id,r.pilot_batch_id,r.round_sequence,
        COUNT(*) AS denominator_item_count,
        SUM(CASE WHEN c.pilot_item_id IS NULL THEN 1 ELSE 0 END) AS missing_item_count,
        SUM(CASE WHEN c.comparison_event_count>1 THEN c.comparison_event_count-1 ELSE 0 END) AS duplicate_comparison_count,
        SUM(CASE WHEN c.comparison_event_count IS NOT NULL THEN 1 ELSE 0 END) AS derived_observed_item_count,
        SUM(CASE WHEN c.comparison_result='MATCH' THEN 1 ELSE 0 END) AS derived_match_item_count,
        SUM(CASE WHEN c.comparison_result='DIFFERENT' THEN 1 ELSE 0 END) AS derived_different_item_count,
        SUM(CASE WHEN c.comparison_result='UNCOMPARABLE' THEN 1 ELSE 0 END) AS derived_uncomparable_item_count,
        SUM(CASE WHEN c.pilot_item_id IS NULL THEN 0
                 WHEN c.manifest_ordinal<>i.manifest_ordinal OR c.item_scope_hash<>i.item_scope_hash
                   OR c.manifest_hash<>i.manifest_hash OR r.manifest_hash<>i.manifest_hash
                   OR c.pilot_batch_id<>i.pilot_batch_id
                 THEN 1 ELSE 0 END) AS frozen_item_mismatch_count,
        SUM(CASE WHEN c.pilot_item_id IS NULL THEN 0
                 WHEN c.source_gtid_set<>r.source_gtid_set OR c.target_gtid_set<>r.target_gtid_set
                 THEN 1 ELSE 0 END) AS comparison_watermark_mismatch_count,
        SUM(CASE WHEN c.pilot_item_id IS NULL THEN 0
                 WHEN r.target_contains_source=FALSE
                   AND (c.comparison_result<>'UNCOMPARABLE'
                     OR c.reason_codes_json NOT LIKE '%TARGET_WATERMARK_NOT_COVERED%')
                 THEN 1 ELSE 0 END) AS watermark_uncomparable_mismatch_count,
        SUM(CASE
              WHEN c.pilot_item_id IS NULL THEN 0
              WHEN c.comparison_result='MATCH' AND c.source_available=1 AND c.target_available=1 AND c.comparable=1
                AND c.difference_fields_json='[]' AND c.reason_codes_json='[]'
                AND c.source_grain_hash=c.target_grain_hash
                AND c.source_on_hand_quantity=c.target_on_hand_quantity
                AND c.source_reserved_quantity=c.target_reserved_quantity
                AND c.source_in_transit_quantity=c.target_in_transit_quantity THEN 0
              WHEN c.comparison_result='DIFFERENT' AND c.source_available=1 AND c.target_available=1 AND c.comparable=1
                AND c.difference_fields_json<>'[]' AND c.reason_codes_json<>'[]'
                AND (c.source_grain_hash<>c.target_grain_hash
                  OR c.source_on_hand_quantity<>c.target_on_hand_quantity
                  OR c.source_reserved_quantity<>c.target_reserved_quantity
                  OR c.source_in_transit_quantity<>c.target_in_transit_quantity) THEN 0
              WHEN c.comparison_result='UNCOMPARABLE' AND c.comparable=0 AND c.reason_codes_json<>'[]'
                AND (c.target_available=1 OR c.reason_codes_json LIKE '%TARGET_MISSING%') THEN 0
              ELSE 1 END) AS invalid_comparison_semantics_count,
        SUM(CASE WHEN c.prior_source_version IS NOT NULL AND c.source_version<c.prior_source_version THEN 1 ELSE 0 END)
          AS source_version_regression_count,
        SUM(CASE WHEN c.target_projection_kind<>'CANONICAL_INVENTORY_V3_SHADOW_PROJECTION'
                   OR c.target_materialized<>0 OR c.execution_available<>0 OR c.cutover_ready<>0
                 THEN 1 ELSE 0 END) AS forbidden_effect_count
    FROM round_chain r
    JOIN admitted_item i ON i.tenant_id=r.tenant_id AND i.pilot_batch_id=r.pilot_batch_id
    LEFT JOIN comparison_ordered c
      ON c.tenant_id=r.tenant_id AND c.shadow_window_id=r.shadow_window_id
     AND c.shadow_round_id=r.shadow_round_id AND c.round_sequence=r.round_sequence
     AND c.pilot_item_id=i.pilot_item_id
    GROUP BY r.tenant_id,r.shadow_window_id,r.shadow_round_id,r.pilot_batch_id,r.round_sequence
), extras AS (
    SELECT c.tenant_id,c.shadow_window_id,c.shadow_round_id,c.round_sequence,COUNT(*) AS extra_item_count
    FROM comparison_dedup c
    LEFT JOIN admitted_item i
      ON i.tenant_id=c.tenant_id AND i.pilot_batch_id=c.pilot_batch_id AND i.pilot_item_id=c.pilot_item_id
    WHERE i.pilot_item_id IS NULL
    GROUP BY c.tenant_id,c.shadow_window_id,c.shadow_round_id,c.round_sequence
)
SELECT
    r.*,
    b.event_id AS admission_event_id,b.source_watermark_value AS admission_source_gtid_set,
    b.target_watermark_value AS admission_target_gtid_set,
    COALESCE(d.denominator_item_count,0) AS denominator_item_count,
    COALESCE(d.missing_item_count,0) AS missing_item_count,
    COALESCE(e.extra_item_count,0) AS extra_item_count,
    COALESCE(d.duplicate_comparison_count,0) AS duplicate_comparison_count,
    COALESCE(d.derived_observed_item_count,0) AS derived_observed_item_count,
    COALESCE(d.derived_match_item_count,0) AS derived_match_item_count,
    COALESCE(d.derived_different_item_count,0) AS derived_different_item_count,
    COALESCE(d.derived_uncomparable_item_count,0) AS derived_uncomparable_item_count,
    COALESCE(d.frozen_item_mismatch_count,0) AS frozen_item_mismatch_count,
    COALESCE(d.comparison_watermark_mismatch_count,0) AS comparison_watermark_mismatch_count,
    COALESCE(d.watermark_uncomparable_mismatch_count,0) AS watermark_uncomparable_mismatch_count,
    COALESCE(d.invalid_comparison_semantics_count,0) AS invalid_comparison_semantics_count,
    COALESCE(d.source_version_regression_count,0) AS source_version_regression_count,
    COALESCE(d.forbidden_effect_count,0) AS forbidden_effect_count,
    TIMESTAMPDIFF(SECOND,r.source_watermark_captured_at,r.target_watermark_applied_at) AS derived_lag_seconds,
    CASE WHEN r.round_version<>1 OR r.round_status<>'COMPLETED' OR r.watermark_kind<>'MYSQL_GTID_SET'
           OR r.gtid_validator_version<>'MYSQL_GTID_SET_CONTAINS_V1'
           OR r.source_monotonic<>TRUE OR r.target_monotonic<>TRUE
           OR (r.round_sequence=1 AND (r.previous_source_gtid_set<>b.source_watermark_value
                                      OR r.previous_target_gtid_set<>b.target_watermark_value))
           OR (r.round_sequence>1 AND (r.previous_source_gtid_set<>r.prior_source_gtid_set
                                      OR r.previous_target_gtid_set<>r.prior_target_gtid_set))
           OR r.reported_lag_seconds<>TIMESTAMPDIFF(SECOND,r.source_watermark_captured_at,r.target_watermark_applied_at)
           OR r.reported_lag_seconds<0 OR r.reported_lag_seconds>w.max_lag_seconds
         THEN 1 ELSE 0 END AS invalid_watermark_count,
    CASE WHEN COALESCE(d.denominator_item_count,0)<>r.expected_item_count
           OR r.pilot_batch_id<>w.pilot_batch_id OR r.manifest_hash<>w.manifest_hash
           OR r.expected_item_set_hash<>w.expected_item_set_hash
           OR r.expected_item_count<>w.expected_item_count
           OR COALESCE(d.missing_item_count,0)<>0 OR COALESCE(e.extra_item_count,0)<>0
           OR COALESCE(d.duplicate_comparison_count,0)<>0
           OR COALESCE(d.watermark_uncomparable_mismatch_count,0)<>0
           OR COALESCE(d.derived_observed_item_count,0)<>r.expected_item_count
           OR COALESCE(d.derived_match_item_count,0)+COALESCE(d.derived_different_item_count,0)
              +COALESCE(d.derived_uncomparable_item_count,0)<>r.expected_item_count
           OR r.reported_observed_item_count<>COALESCE(d.derived_observed_item_count,0)
           OR r.reported_match_item_count<>COALESCE(d.derived_match_item_count,0)
           OR r.reported_different_item_count<>COALESCE(d.derived_different_item_count,0)
           OR r.reported_uncomparable_item_count<>COALESCE(d.derived_uncomparable_item_count,0)
         THEN 1 ELSE 0 END AS denominator_invalid_count,
    CASE WHEN (r.round_result='MATCH' AND COALESCE(d.derived_match_item_count,0)=r.expected_item_count
                                      AND COALESCE(d.derived_different_item_count,0)=0
                                      AND COALESCE(d.derived_uncomparable_item_count,0)=0)
           OR (r.round_result='DIFFERENT' AND COALESCE(d.derived_different_item_count,0)>0
                                           AND COALESCE(d.derived_uncomparable_item_count,0)=0)
           OR (r.round_result='UNCOMPARABLE' AND COALESCE(d.derived_uncomparable_item_count,0)>0)
         THEN 0 ELSE 1 END AS invalid_round_result_count
FROM round_chain r
JOIN yshopping_dim.dim_canonical_inventory_migration_shadow_window_current w
  ON w.tenant_id=r.tenant_id AND w.shadow_window_id=r.shadow_window_id
JOIN admitted_batch b
  ON b.tenant_id=r.tenant_id AND b.pilot_batch_id=r.pilot_batch_id
LEFT JOIN denominator d
  ON d.tenant_id=r.tenant_id AND d.shadow_window_id=r.shadow_window_id AND d.shadow_round_id=r.shadow_round_id
LEFT JOIN extras e
  ON e.tenant_id=r.tenant_id AND e.shadow_window_id=r.shadow_window_id AND e.shadow_round_id=r.shadow_round_id;
