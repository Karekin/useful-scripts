CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_migration_readiness AS
SELECT
    migration.*,
    CASE
      WHEN opening_event_count > 0 THEN 'MIGRATED_CANARY'
      WHEN qualification_count > 0 THEN 'QUALIFIED_ONLY'
      ELSE 'ASSESSED_ONLY'
    END AS migration_stage,
    CASE
      WHEN candidate_count <> assessment_event_count
        OR candidate_count <> distinct_source_count
        OR candidate_count <> eligible_count + blocked_count + rejected_count
        OR blockerless_blocked_count <> 0
        OR eligible_with_blocker_count <> 0
        OR false_allocation_claim_count <> 0
        OR qualification_count <> qualification_event_count
        OR qualification_count <> distinct_qualification_count
        OR qualification_count <> distinct_qualified_assessment_count
        OR qualification_count <> distinct_qualified_source_count
        OR qualification_count <> distinct_qualified_snapshot_count
        OR qualification_count <> controlled_canary_count
        OR invalid_qualification_status_count <> 0
        OR nonzero_qualification_hold_count <> 0
        OR qualification_assessment_mismatch_count <> 0
        OR opening_hold_delta_count <> 0
        OR invalid_opening_driver_count <> 0
        OR post_qualification_legacy_write_count <> 0
        OR opening_event_count > qualification_count
      THEN 'INCONSISTENT'
      WHEN opening_event_count > 0
        AND opening_event_count = qualification_count
        AND opening_event_count = distinct_opening_qualification_count
        AND opening_event_count = distinct_opening_candidate_count
        AND opening_event_count = distinct_opening_source_count
        AND opening_event_count = distinct_opening_snapshot_count
        AND opening_on_hand_quantity = qualified_on_hand_quantity
      THEN 'CANARY_RECONCILED'
      WHEN qualification_count > 0 AND opening_event_count = 0 THEN 'QUALIFIED_RUNTIME_GATED'
      WHEN eligible_count > 0 THEN 'READY_TO_QUALIFY'
      WHEN blocked_count + rejected_count = candidate_count THEN 'BLOCKED'
      ELSE 'ASSESSMENT_INCOMPLETE'
    END AS readiness_status
FROM yshopping_dws.dws_canonical_inventory_migration_run migration;
