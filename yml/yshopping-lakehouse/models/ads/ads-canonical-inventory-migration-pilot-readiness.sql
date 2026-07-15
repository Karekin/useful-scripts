CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_migration_pilot_readiness AS
SELECT
    pilot.*,
    CASE
      WHEN batch_event_count<>distinct_batch_version_count OR min_batch_version<>1 OR max_batch_version<>batch_version
        OR batch_event_count<>batch_version OR distinct_manifest_count<>1 OR distinct_policy_count<>1
        OR distinct_environment_count<>1 OR distinct_expected_item_count<>1 OR distinct_expected_quantity_count<>1
        OR invalid_batch_transition_count<>0 OR observed_item_count<>expected_item_count
        OR distinct_item_count<>expected_item_count OR distinct_ordinal_count<>expected_item_count
        OR distinct_source_count<>expected_item_count OR distinct_item_scope_hash_count<>expected_item_count
        OR distinct_item_manifest_count<>1 OR distinct_warehouse_count<>1 OR distinct_base_uom_count<>1
        OR observed_on_hand_quantity<>expected_on_hand_quantity OR item_version_gap_count<>0
        OR invalid_item_transition_count<>0 OR out_of_scope_item_count<>0 OR assessment_mismatch_count<>0
        OR actor_separation_violation_count<>0 OR qualification_event_count<>0
        OR production_opening_event_count<>0 OR post_admission_legacy_write_count<>0
      THEN 'INCONSISTENT'
      WHEN batch_status='ADMISSION_PASSED'
        AND approved_item_count=expected_item_count AND admitted_item_count=expected_item_count
        AND approved_on_hand_quantity=expected_on_hand_quantity
        AND admitted_on_hand_quantity=expected_on_hand_quantity
        AND observed_approved_item_count=expected_item_count
        AND observed_admitted_item_count=expected_item_count
        AND observed_approved_on_hand_quantity=expected_on_hand_quantity
        AND observed_admitted_on_hand_quantity=expected_on_hand_quantity
      THEN 'ADMISSION_RECONCILED'
      WHEN batch_status='APPROVED' THEN 'APPROVED_AWAITING_ADMISSION'
      WHEN batch_status='PARTIALLY_APPROVED' THEN 'APPROVAL_IN_PROGRESS'
      WHEN batch_status='FROZEN' THEN 'FROZEN_AWAITING_APPROVAL'
      ELSE 'ADMISSION_INCOMPLETE'
    END AS readiness_status
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch pilot;
