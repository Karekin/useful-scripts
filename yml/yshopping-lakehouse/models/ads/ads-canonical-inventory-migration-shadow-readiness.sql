CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_migration_shadow_readiness AS
SELECT
    shadow.*,
    FALSE AS execution_permitted,
    FALSE AS cutover_permitted,
    FALSE AS target_projection_materialized,
    CASE
      WHEN historical_admission_mismatch_count<>0 OR window_history_invalid_count<>0
        OR forbidden_effect_count<>0 OR invalid_comparison_semantics_count<>0
        OR source_version_regression_count<>0 OR invalid_round_result_count<>0
        OR terminal_result_invalid_count<>0
      THEN 'INCONSISTENT'
      WHEN denominator_complete=0 THEN 'DENOMINATOR_INCOMPLETE'
      WHEN invalid_watermark_count<>0 OR comparison_watermark_mismatch_count<>0
        OR watermark_uncomparable_mismatch_count<>0 THEN 'WATERMARK_INVALID'
      WHEN uncomparable_round_count>0 THEN
        CASE WHEN window_status='VERIFIED' AND verification_result='UNCOMPARABLE'
             THEN 'SHADOW_UNCOMPARABLE_VERIFIED' ELSE 'UNCOMPARABLE_PRESENT' END
      WHEN different_round_count>0 THEN
        CASE WHEN window_status='VERIFIED' AND verification_result='DIFFERENT'
             THEN 'SHADOW_DIFFERENCE_VERIFIED' ELSE 'DIFFERENCE_DETECTED' END
      WHEN window_status IN ('OPEN','OBSERVING') AND verification_result='PENDING'
        AND shadow_match_evidence=1 THEN 'EVIDENCE_COMPLETE_AWAITING_TERMINAL'
      WHEN window_status IN ('OPEN','OBSERVING') AND verification_result='PENDING' THEN 'COLLECTING'
      WHEN window_status='VERIFIED' AND verification_result='MATCH' AND shadow_match_evidence=1
        THEN 'SHADOW_MATCH_VERIFIED'
      ELSE 'INCONSISTENT'
    END AS readiness_status
FROM yshopping_dws.dws_canonical_inventory_migration_shadow_window shadow;
