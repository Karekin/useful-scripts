SELECT 'canonical_inventory_migration_event_id_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event;

SELECT 'canonical_inventory_migration_payload_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE assessment_id <> payload_assessment_id
   OR legacy_balance_id <> source_id
   OR migration_source_system <> 'CLOUDMOLD_INVENTORY_V1'
   OR migration_source_type <> 'BALANCE'
   OR assessment_version <> 1;

SELECT 'canonical_inventory_migration_source_evidence', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE migration_run_id IS NULL OR source_id IS NULL OR source_version < 1
   OR source_updated_at IS NULL OR source_snapshot_hash NOT REGEXP '^[a-f0-9]{64}$'
   OR policy_version IS NULL OR verification_ref IS NULL OR assessed_at IS NULL;

SELECT 'canonical_inventory_migration_quantity_domain', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE source_on_hand_quantity < 0 OR source_reserved_quantity < 0 OR source_in_transit_quantity < 0
   OR active_reservation_count < 0 OR active_reservation_quantity < 0
   OR reservation_allocation_count < 0 OR reservation_allocation_quantity < 0;

SELECT 'canonical_inventory_migration_v1_reservation_provenance', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE reservation_allocation_count <> 0 OR reservation_allocation_quantity <> 0
   OR ((active_reservation_count > 0 OR source_reserved_quantity > 0)
       AND LOCATE('RESERVATION_PROVENANCE_MISSING', blocker_codes_json) = 0);

SELECT 'canonical_inventory_migration_decision_evidence', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE assessment_status NOT IN ('ELIGIBLE', 'BLOCKED', 'REJECTED')
   OR (assessment_status IN ('BLOCKED', 'REJECTED') AND blocker_codes_json IN ('[]', '', 'null'))
   OR (assessment_status = 'ELIGIBLE' AND blocker_codes_json NOT IN ('[]', '', 'null'));

SELECT 'canonical_inventory_migration_eligible_dimensions', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event
WHERE assessment_status = 'ELIGIBLE'
  AND (resolved_owner_type <> 'MERCHANT' OR resolved_owner_id IS NULL
    OR resolved_canonical_sku_id IS NULL OR resolved_warehouse_id IS NULL
    OR resolved_location_id IS NULL OR lot_tracking_policy = 'UNRESOLVED'
    OR resolved_base_uom_code IS NULL OR active_reservation_count <> 0
    OR active_reservation_quantity <> 0 OR source_reserved_quantity <> 0
    OR source_in_transit_quantity <> 0);

SELECT 'canonical_inventory_migration_run_rollup', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_migration_run
WHERE candidate_count <> assessment_event_count
   OR candidate_count <> distinct_source_count
   OR candidate_count <> eligible_count + blocked_count + rejected_count
   OR blockerless_blocked_count <> 0 OR eligible_with_blocker_count <> 0
   OR false_allocation_claim_count <> 0;

SELECT 'canonical_inventory_migration_stage_fence', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_migration_run
WHERE (qualification_count = 0 AND (opening_event_count <> 0 OR opening_on_hand_quantity <> 0))
   OR opening_event_count > qualification_count
   OR qualification_count <> qualification_event_count
   OR qualification_count <> distinct_qualification_count
   OR qualification_count <> controlled_canary_count
   OR invalid_qualification_status_count <> 0
   OR nonzero_qualification_hold_count <> 0
   OR qualification_assessment_mismatch_count <> 0
   OR opening_hold_delta_count <> 0
   OR invalid_opening_driver_count <> 0
   OR post_qualification_legacy_write_count <> 0;

SELECT 'canonical_inventory_migration_legacy_source_frozen', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_migration_run
WHERE post_qualification_legacy_write_count <> 0;

SELECT 'canonical_inventory_migration_qualification_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_migration_qualification_event
WHERE qualification_id <> payload_qualification_id
   OR migration_source_system <> 'CLOUDMOLD_INVENTORY_V1'
   OR migration_source_type <> 'BALANCE'
   OR source_classification <> 'CONTROLLED_CANARY'
   OR source_version < 1 OR source_snapshot_hash NOT REGEXP '^[a-f0-9]{64}$'
   OR owner_type <> 'MERCHANT' OR owner_id IS NULL OR canonical_sku_id IS NULL
   OR warehouse_source_mapping_id IS NULL OR warehouse_id IS NULL OR location_id IS NULL
   OR lot_tracking_policy NOT IN ('NOT_TRACKED','TRACKED')
   OR (lot_tracking_policy='NOT_TRACKED' AND lot_id IS NOT NULL)
   OR (lot_tracking_policy='TRACKED' AND lot_id IS NULL)
   OR source_on_hand_quantity <= 0 OR source_reserved_quantity <> 0 OR source_in_transit_quantity <> 0
   OR qualification_status <> 'QUALIFIED';

SELECT 'canonical_inventory_migration_readiness_consistency', COUNT(*)
FROM yshopping_ads.ads_canonical_inventory_migration_readiness
WHERE readiness_status IN ('INCONSISTENT', 'ASSESSMENT_INCOMPLETE')
   OR migration_stage NOT IN ('ASSESSED_ONLY','QUALIFIED_ONLY','MIGRATED_CANARY')
   OR (migration_stage='ASSESSED_ONLY' AND (qualification_count<>0 OR opening_event_count<>0))
   OR (migration_stage='QUALIFIED_ONLY' AND (qualification_count=0 OR opening_event_count<>0
        OR readiness_status<>'QUALIFIED_RUNTIME_GATED'))
   OR (migration_stage='MIGRATED_CANARY' AND (opening_event_count=0
        OR post_qualification_legacy_write_count<>0 OR readiness_status<>'CANARY_RECONCILED'))
   OR (readiness_status = 'READY_TO_QUALIFY' AND eligible_count = 0)
   OR (readiness_status = 'BLOCKED' AND blocked_count + rejected_count <> candidate_count);

SELECT 'canonical_inventory_migration_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'inventory.migration.balance_assessed'
  AND (get_json_string(payload, '$.contact_mobile') IS NOT NULL
    OR get_json_string(payload, '$.contact_name') IS NOT NULL
    OR get_json_string(payload, '$.id_card') IS NOT NULL
    OR get_json_string(payload, '$.address') IS NOT NULL);
