SELECT 'shadow_window_event_id_duplicate' AS check_name,COUNT(*) AS violations
FROM (SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_window_event
      GROUP BY event_id HAVING COUNT(*)<>1) x;

SELECT 'shadow_round_event_id_duplicate' AS check_name,COUNT(*) AS violations
FROM (SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_round_event
      GROUP BY event_id HAVING COUNT(*)<>1) x;

SELECT 'shadow_comparison_event_id_duplicate' AS check_name,COUNT(*) AS violations
FROM (SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_item_comparison_event
      GROUP BY event_id HAVING COUNT(*)<>1) x;

SELECT 'shadow_round_or_comparison_not_immutable_v1' AS check_name,COUNT(*) AS violations
FROM (
  SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_round_event
  WHERE round_version<>1
  UNION ALL
  SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_item_comparison_event
  WHERE comparison_version<>1
) x;

SELECT 'shadow_window_version_or_transition_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE window_history_invalid_count<>0;

SELECT 'shadow_window_status_result_not_separated' AS check_name,COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_window_event
WHERE (window_status IN ('OPEN','OBSERVING') AND (verification_result<>'PENDING' OR window_verified_at IS NOT NULL))
   OR (window_status='VERIFIED' AND (verification_result='PENDING' OR window_verified_at IS NULL));

SELECT 'shadow_historical_admission_binding_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE historical_admission_mismatch_count<>0;

SELECT 'shadow_expected_items_by_round_denominator_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE denominator_invalid_count<>0 OR missing_item_count<>0 OR extra_item_count<>0
   OR duplicate_comparison_count<>0 OR denominator_item_count<>expected_item_count;

SELECT 'shadow_reported_vs_derived_counts_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE reported_observed_item_count<>derived_observed_item_count
   OR reported_match_item_count<>derived_match_item_count
   OR reported_different_item_count<>derived_different_item_count
   OR reported_uncomparable_item_count<>derived_uncomparable_item_count;

SELECT 'shadow_comparison_result_semantics_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE invalid_comparison_semantics_count<>0 OR invalid_round_result_count<>0;

SELECT 'shadow_target_missing_not_uncomparable' AS check_name,COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_item_comparison_event
WHERE target_available=FALSE
  AND (comparison_result<>'UNCOMPARABLE' OR comparable<>FALSE OR reason_codes_json NOT LIKE '%TARGET_MISSING%');

SELECT 'shadow_projection_boundary_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_item_comparison_event
WHERE target_projection_kind<>'CANONICAL_INVENTORY_V3_SHADOW_PROJECTION' OR target_materialized<>FALSE;

SELECT 'shadow_gtid_contract_invalid' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE watermark_kind<>'MYSQL_GTID_SET' OR gtid_validator_version<>'MYSQL_GTID_SET_CONTAINS_V1'
   OR source_monotonic<>TRUE OR target_monotonic<>TRUE
   OR invalid_watermark_count<>0;

SELECT 'shadow_uncovered_target_not_full_round_uncomparable' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE target_contains_source=FALSE
  AND (round_result<>'UNCOMPARABLE' OR derived_uncomparable_item_count<>expected_item_count
    OR watermark_uncomparable_mismatch_count<>0);

SELECT 'shadow_comparison_watermark_mismatch' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_round
WHERE comparison_watermark_mismatch_count<>0;

SELECT 'shadow_source_version_regression' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE source_version_regression_count<>0;

SELECT 'shadow_round_sequence_gap_or_duplicate' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE round_count>0 AND (distinct_round_count<>round_count OR distinct_round_sequence_count<>round_count
  OR min_round_sequence<>1 OR max_round_sequence<>round_count);

SELECT 'shadow_observation_policy_not_met' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE window_status='VERIFIED' AND (round_count<required_round_count
   OR observed_duration_seconds<required_duration_seconds
   OR max_observed_round_gap_seconds>max_round_gap_seconds);

SELECT 'shadow_terminal_result_not_evidence_backed' AS check_name,COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window
WHERE terminal_result_invalid_count<>0;

SELECT 'shadow_match_verified_without_all_gates' AS check_name,COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_inventory_migration_shadow_readiness
WHERE readiness_status='SHADOW_MATCH_VERIFIED'
  AND (window_status<>'VERIFIED' OR verification_result<>'MATCH' OR shadow_match_evidence<>1
    OR denominator_complete<>1 OR invalid_watermark_count<>0);

SELECT 'shadow_execution_cutover_or_materialization_enabled' AS check_name,COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_inventory_migration_shadow_readiness
WHERE execution_available<>FALSE OR cutover_ready<>FALSE OR execution_permitted<>FALSE
   OR cutover_permitted<>FALSE OR target_projection_materialized<>FALSE;

SELECT 'shadow_qualification_opening_or_bridge_leak' AS check_name,COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event e
JOIN yshopping_dim.dim_canonical_inventory_migration_shadow_window_current w
  ON w.tenant_id=e.tenant_id
WHERE (e.event_type='inventory.migration.balance_qualified'
    OR (e.event_type='inventory.stock.changed' AND e.schema_version=4)
    OR get_json_string(e.payload,'$.bridge_created')='true')
  AND get_json_string(e.payload,'$.pilot_batch_id')=w.pilot_batch_id;

SELECT 'shadow_event_pii_or_principal_leak' AS check_name,COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE event_type IN ('inventory.migration.shadow_window_status_changed',
                     'inventory.migration.shadow_round_completed',
                     'inventory.migration.shadow_item_compared')
  AND (get_json_string(payload,'$.mobile') IS NOT NULL
    OR get_json_string(payload,'$.phone') IS NOT NULL
    OR get_json_string(payload,'$.id_card') IS NOT NULL
    OR get_json_string(payload,'$.principal_id') IS NOT NULL);
