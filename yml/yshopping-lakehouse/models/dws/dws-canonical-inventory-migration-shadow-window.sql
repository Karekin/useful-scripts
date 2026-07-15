CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_migration_shadow_window AS
WITH window_history AS (
    SELECT
        tenant_id,shadow_window_id,
        COUNT(*) AS window_event_count,COUNT(DISTINCT window_version) AS distinct_window_version_count,
        MIN(window_version) AS min_window_version,MAX(window_version) AS max_window_version,
        COUNT(DISTINCT pilot_batch_id) AS distinct_pilot_batch_count,
        COUNT(DISTINCT admission_event_id) AS distinct_admission_event_count,
        COUNT(DISTINCT manifest_hash) AS distinct_manifest_count,
        COUNT(DISTINCT expected_item_set_hash) AS distinct_item_set_count,
        COUNT(DISTINCT environment_fingerprint) AS distinct_environment_count,
        COUNT(DISTINCT policy_hash) AS distinct_policy_count,
        COUNT(DISTINCT expected_item_count) AS distinct_expected_item_count,
        COUNT(DISTINCT required_round_count) AS distinct_required_round_count,
        COUNT(DISTINCT required_duration_seconds) AS distinct_required_duration_count,
        COUNT(DISTINCT max_round_gap_seconds) AS distinct_max_round_gap_count,
        COUNT(DISTINCT max_lag_seconds) AS distinct_max_lag_count,
        SUM(CASE
              WHEN window_version=1 AND window_status='OPEN' AND verification_result='PENDING'
                   AND window_verified_at IS NULL THEN 0
              WHEN window_version=2 AND window_status='OBSERVING' AND verification_result='PENDING'
                   AND window_verified_at IS NULL THEN 0
              WHEN window_version=3 AND window_status='VERIFIED'
                   AND verification_result IN ('MATCH','DIFFERENT','UNCOMPARABLE')
                   AND window_verified_at IS NOT NULL THEN 0
              ELSE 1 END) AS invalid_window_transition_count,
        SUM(CASE WHEN target_projection_kind<>'CANONICAL_INVENTORY_V3_SHADOW_PROJECTION'
                   OR target_materialized<>FALSE OR watermark_kind<>'MYSQL_GTID_SET'
                   OR gtid_validator_version<>'MYSQL_GTID_SET_CONTAINS_V1'
                   OR execution_available<>FALSE OR cutover_ready<>FALSE THEN 1 ELSE 0 END)
          AS invalid_window_fence_count
    FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_window_event
    GROUP BY tenant_id,shadow_window_id
), admitted_batch AS (
    SELECT * FROM (
        SELECT b.*,ROW_NUMBER() OVER (
          PARTITION BY tenant_id,pilot_batch_id ORDER BY recorded_at DESC,event_id DESC
        ) AS admission_rank
        FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event b
        WHERE batch_status='ADMISSION_PASSED' AND batch_version=4
    ) x WHERE admission_rank=1
), admitted_items AS (
    SELECT tenant_id,pilot_batch_id,manifest_hash,
           COUNT(DISTINCT pilot_item_id) AS admitted_item_count,
           COUNT(DISTINCT manifest_ordinal) AS admitted_ordinal_count,
           COUNT(DISTINCT item_scope_hash) AS admitted_scope_hash_count
    FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event
    WHERE item_status='ADMISSION_PASSED' AND item_version=3
    GROUP BY tenant_id,pilot_batch_id,manifest_hash
), ordered_round AS (
    SELECT r.*,
           LAG(round_completed_at) OVER (
             PARTITION BY tenant_id,shadow_window_id ORDER BY round_sequence
           ) AS prior_round_completed_at
    FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round r
), round_rollup AS (
    SELECT
        tenant_id,shadow_window_id,
        COUNT(*) AS round_count,COUNT(DISTINCT shadow_round_id) AS distinct_round_count,
        COUNT(DISTINCT round_sequence) AS distinct_round_sequence_count,
        MIN(round_sequence) AS min_round_sequence,MAX(round_sequence) AS max_round_sequence,
        MIN(round_started_at) AS first_round_started_at,MAX(round_completed_at) AS last_round_completed_at,
        MAX(CASE WHEN prior_round_completed_at IS NULL THEN 0
                 ELSE TIMESTAMPDIFF(SECOND,prior_round_completed_at,round_started_at) END) AS max_internal_round_gap_seconds,
        SUM(CASE WHEN round_result='MATCH' THEN 1 ELSE 0 END) AS match_round_count,
        SUM(CASE WHEN round_result='DIFFERENT' THEN 1 ELSE 0 END) AS different_round_count,
        SUM(CASE WHEN round_result='UNCOMPARABLE' THEN 1 ELSE 0 END) AS uncomparable_round_count,
        SUM(missing_item_count) AS missing_item_count,
        SUM(extra_item_count) AS extra_item_count,
        SUM(duplicate_comparison_count) AS duplicate_comparison_count,
        SUM(frozen_item_mismatch_count) AS frozen_item_mismatch_count,
        SUM(comparison_watermark_mismatch_count) AS comparison_watermark_mismatch_count,
        SUM(watermark_uncomparable_mismatch_count) AS watermark_uncomparable_mismatch_count,
        SUM(invalid_comparison_semantics_count) AS invalid_comparison_semantics_count,
        SUM(source_version_regression_count) AS source_version_regression_count,
        SUM(forbidden_effect_count) AS forbidden_effect_count,
        SUM(invalid_watermark_count) AS invalid_watermark_count,
        SUM(denominator_invalid_count) AS denominator_invalid_count,
        SUM(invalid_round_result_count) AS invalid_round_result_count,
        MAX_BY(source_gtid_set,round_sequence) AS verified_through_source_gtid_set,
        MAX_BY(target_gtid_set,round_sequence) AS verified_through_target_gtid_set,
        MAX(target_watermark_applied_at) AS verified_through_at
    FROM ordered_round
    GROUP BY tenant_id,shadow_window_id
), window_round_metrics AS (
    SELECT r.*,
           TIMESTAMPDIFF(SECOND,w.window_started_at,
             COALESCE(w.window_verified_at,r.last_round_completed_at,w.window_started_at)) AS observed_duration_seconds,
           GREATEST(
             COALESCE(r.max_internal_round_gap_seconds,0),
             COALESCE(TIMESTAMPDIFF(SECOND,w.window_started_at,r.first_round_started_at),0),
             CASE WHEN w.window_status='VERIFIED'
                  THEN COALESCE(TIMESTAMPDIFF(SECOND,r.last_round_completed_at,w.window_verified_at),0)
                  ELSE 0 END
           ) AS max_observed_round_gap_seconds
    FROM round_rollup r
    JOIN yshopping_dim.dim_canonical_inventory_migration_shadow_window_current w
      ON w.tenant_id=r.tenant_id AND w.shadow_window_id=r.shadow_window_id
)
SELECT
    w.*,
    h.distinct_window_version_count,h.min_window_version,h.max_window_version,
    h.distinct_pilot_batch_count,h.distinct_admission_event_count,h.distinct_manifest_count,
    h.distinct_item_set_count,h.distinct_environment_count,h.distinct_policy_count,
    h.distinct_expected_item_count,h.distinct_required_round_count,h.distinct_required_duration_count,
    h.distinct_max_round_gap_count,h.distinct_max_lag_count,h.invalid_window_transition_count,
    h.invalid_window_fence_count,
    b.event_id AS historical_admission_event_id,b.manifest_hash AS historical_manifest_hash,
    b.expected_item_count AS historical_expected_item_count,
    COALESCE(i.admitted_item_count,0) AS historical_admitted_item_count,
    COALESCE(i.admitted_ordinal_count,0) AS historical_admitted_ordinal_count,
    COALESCE(i.admitted_scope_hash_count,0) AS historical_admitted_scope_hash_count,
    COALESCE(r.round_count,0) AS round_count,COALESCE(r.distinct_round_count,0) AS distinct_round_count,
    COALESCE(r.distinct_round_sequence_count,0) AS distinct_round_sequence_count,
    COALESCE(r.min_round_sequence,0) AS min_round_sequence,COALESCE(r.max_round_sequence,0) AS max_round_sequence,
    r.first_round_started_at,r.last_round_completed_at,
    COALESCE(r.observed_duration_seconds,0) AS observed_duration_seconds,
    COALESCE(r.max_observed_round_gap_seconds,0) AS max_observed_round_gap_seconds,
    COALESCE(r.match_round_count,0) AS match_round_count,
    COALESCE(r.different_round_count,0) AS different_round_count,
    COALESCE(r.uncomparable_round_count,0) AS uncomparable_round_count,
    COALESCE(r.missing_item_count,0) AS missing_item_count,
    COALESCE(r.extra_item_count,0) AS extra_item_count,
    COALESCE(r.duplicate_comparison_count,0) AS duplicate_comparison_count,
    COALESCE(r.frozen_item_mismatch_count,0) AS frozen_item_mismatch_count,
    COALESCE(r.comparison_watermark_mismatch_count,0) AS comparison_watermark_mismatch_count,
    COALESCE(r.watermark_uncomparable_mismatch_count,0) AS watermark_uncomparable_mismatch_count,
    COALESCE(r.invalid_comparison_semantics_count,0) AS invalid_comparison_semantics_count,
    COALESCE(r.source_version_regression_count,0) AS source_version_regression_count,
    COALESCE(r.forbidden_effect_count,0) AS forbidden_effect_count,
    COALESCE(r.invalid_watermark_count,0) AS invalid_watermark_count,
    COALESCE(r.denominator_invalid_count,0) AS denominator_invalid_count,
    COALESCE(r.invalid_round_result_count,0) AS invalid_round_result_count,
    r.verified_through_source_gtid_set,r.verified_through_target_gtid_set,r.verified_through_at,
    CASE WHEN b.event_id IS NULL OR b.event_id<>w.admission_event_id OR b.manifest_hash<>w.manifest_hash
           OR b.expected_item_count<>w.expected_item_count OR COALESCE(i.admitted_item_count,0)<>w.expected_item_count
           OR COALESCE(i.admitted_ordinal_count,0)<>w.expected_item_count
           OR COALESCE(i.admitted_scope_hash_count,0)<>w.expected_item_count
         THEN 1 ELSE 0 END AS historical_admission_mismatch_count,
    CASE WHEN h.window_event_count<>h.distinct_window_version_count OR h.min_window_version<>1
           OR h.max_window_version<>w.window_version OR h.window_event_count<>w.window_version
           OR h.distinct_pilot_batch_count<>1 OR h.distinct_admission_event_count<>1
           OR h.distinct_manifest_count<>1 OR h.distinct_item_set_count<>1 OR h.distinct_environment_count<>1
           OR h.distinct_policy_count<>1 OR h.distinct_expected_item_count<>1
           OR h.distinct_required_round_count<>1 OR h.distinct_required_duration_count<>1
           OR h.distinct_max_round_gap_count<>1 OR h.distinct_max_lag_count<>1
           OR h.invalid_window_transition_count<>0 OR h.invalid_window_fence_count<>0
         THEN 1 ELSE 0 END AS window_history_invalid_count,
    CASE WHEN COALESCE(r.round_count,0)>=w.required_round_count
           AND COALESCE(r.distinct_round_count,0)=COALESCE(r.round_count,0)
           AND COALESCE(r.distinct_round_sequence_count,0)=COALESCE(r.round_count,0)
           AND COALESCE(r.min_round_sequence,0)=1 AND COALESCE(r.max_round_sequence,0)=COALESCE(r.round_count,0)
           AND COALESCE(r.observed_duration_seconds,0)>=w.required_duration_seconds
           AND COALESCE(r.max_observed_round_gap_seconds,0)<=w.max_round_gap_seconds
           AND COALESCE(r.missing_item_count,0)=0 AND COALESCE(r.extra_item_count,0)=0
           AND COALESCE(r.duplicate_comparison_count,0)=0 AND COALESCE(r.denominator_invalid_count,0)=0
         THEN 1 ELSE 0 END AS denominator_complete,
    CASE WHEN COALESCE(r.round_count,0)>=w.required_round_count
           AND COALESCE(r.match_round_count,0)=COALESCE(r.round_count,0)
           AND COALESCE(r.different_round_count,0)=0 AND COALESCE(r.uncomparable_round_count,0)=0
           AND COALESCE(r.missing_item_count,0)=0 AND COALESCE(r.extra_item_count,0)=0
           AND COALESCE(r.duplicate_comparison_count,0)=0 AND COALESCE(r.frozen_item_mismatch_count,0)=0
           AND COALESCE(r.comparison_watermark_mismatch_count,0)=0
           AND COALESCE(r.watermark_uncomparable_mismatch_count,0)=0
           AND COALESCE(r.invalid_comparison_semantics_count,0)=0
           AND COALESCE(r.source_version_regression_count,0)=0 AND COALESCE(r.forbidden_effect_count,0)=0
           AND COALESCE(r.invalid_watermark_count,0)=0 AND COALESCE(r.denominator_invalid_count,0)=0
           AND COALESCE(r.invalid_round_result_count,0)=0
           AND COALESCE(r.observed_duration_seconds,0)>=w.required_duration_seconds
           AND COALESCE(r.max_observed_round_gap_seconds,0)<=w.max_round_gap_seconds
         THEN 1 ELSE 0 END AS shadow_match_evidence
    ,CASE
       WHEN w.window_status IN ('OPEN','OBSERVING') AND w.verification_result='PENDING' THEN 0
       WHEN w.window_status='VERIFIED' AND w.verification_result='MATCH'
         AND COALESCE(r.round_count,0)>=w.required_round_count
         AND COALESCE(r.match_round_count,0)=COALESCE(r.round_count,0)
         AND COALESCE(r.different_round_count,0)=0 AND COALESCE(r.uncomparable_round_count,0)=0 THEN 0
       WHEN w.window_status='VERIFIED' AND w.verification_result='DIFFERENT'
         AND COALESCE(r.different_round_count,0)>0 AND COALESCE(r.uncomparable_round_count,0)=0 THEN 0
       WHEN w.window_status='VERIFIED' AND w.verification_result='UNCOMPARABLE'
         AND COALESCE(r.uncomparable_round_count,0)>0 THEN 0
       ELSE 1 END AS terminal_result_invalid_count
FROM yshopping_dim.dim_canonical_inventory_migration_shadow_window_current w
JOIN window_history h ON h.tenant_id=w.tenant_id AND h.shadow_window_id=w.shadow_window_id
LEFT JOIN admitted_batch b ON b.tenant_id=w.tenant_id AND b.pilot_batch_id=w.pilot_batch_id
LEFT JOIN admitted_items i
  ON i.tenant_id=w.tenant_id AND i.pilot_batch_id=w.pilot_batch_id AND i.manifest_hash=w.manifest_hash
LEFT JOIN window_round_metrics r ON r.tenant_id=w.tenant_id AND r.shadow_window_id=w.shadow_window_id;
