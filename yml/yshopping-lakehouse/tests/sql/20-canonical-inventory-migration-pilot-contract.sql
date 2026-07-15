SELECT 'pilot_batch_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event
      GROUP BY event_id HAVING COUNT(*)<>1) duplicate_event;

SELECT 'pilot_item_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (SELECT event_id FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event
      GROUP BY event_id HAVING COUNT(*)<>1) duplicate_event;

SELECT 'pilot_batch_aggregate_version_gap' AS check_name, COUNT(*) AS violations
FROM (SELECT tenant_id,pilot_batch_id,COUNT(*) event_count,COUNT(DISTINCT batch_version) version_count,
             MIN(batch_version) min_version,MAX(batch_version) max_version
      FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event
      GROUP BY tenant_id,pilot_batch_id) versioned
WHERE event_count<>version_count OR min_version<>1 OR max_version<>event_count;

SELECT 'pilot_batch_transition_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event
WHERE NOT ((batch_version=1 AND batch_status='FROZEN' AND approval_count=0)
        OR (batch_version=2 AND batch_status='PARTIALLY_APPROVED' AND approval_count=1)
        OR (batch_version=3 AND batch_status='APPROVED' AND approval_count=2)
        OR (batch_version=4 AND batch_status='ADMISSION_PASSED' AND approval_count=2));

SELECT 'pilot_batch_frozen_fact_drift' AS check_name, COUNT(*) AS violations
FROM (SELECT tenant_id,pilot_batch_id,COUNT(DISTINCT manifest_hash) manifest_count,
             COUNT(DISTINCT policy_hash) policy_count,COUNT(DISTINCT environment_fingerprint) environment_count,
             COUNT(DISTINCT expected_item_count) denominator_count,
             COUNT(DISTINCT expected_on_hand_quantity) quantity_count
      FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event
      GROUP BY tenant_id,pilot_batch_id) immutable
WHERE manifest_count<>1 OR policy_count<>1 OR environment_count<>1 OR denominator_count<>1 OR quantity_count<>1;

SELECT 'pilot_item_aggregate_version_gap' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current
WHERE item_event_count<>item_version OR item_version NOT IN (1,2,3);

SELECT 'pilot_item_transition_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event
WHERE NOT ((item_version=1 AND item_status='FROZEN')
        OR (item_version=2 AND item_status='APPROVED')
        OR (item_version=3 AND item_status='ADMISSION_PASSED'));

SELECT 'pilot_item_frozen_fact_drift' AS check_name, COUNT(*) AS violations
FROM (SELECT tenant_id,pilot_item_id,COUNT(DISTINCT item_scope_hash) scope_count,
             COUNT(DISTINCT manifest_hash) manifest_count,COUNT(DISTINCT source_snapshot_hash) snapshot_count,
             COUNT(DISTINCT source_on_hand_quantity) quantity_count,
             COUNT(DISTINCT CONCAT(owner_id,'|',canonical_sku_id,'|',warehouse_id,'|',location_id,'|',
                                   COALESCE(lot_id,''),'|',stock_status,'|',quality_status,'|',base_uom_code)) grain_count
      FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event
      GROUP BY tenant_id,pilot_item_id) immutable
WHERE scope_count<>1 OR manifest_count<>1 OR snapshot_count<>1 OR quantity_count<>1 OR grain_count<>1;

SELECT 'pilot_item_batch_manifest_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current i
LEFT JOIN yshopping_dim.dim_canonical_inventory_migration_pilot_batch_current b
  ON b.tenant_id=i.tenant_id AND b.pilot_batch_id=i.pilot_batch_id
WHERE b.pilot_batch_id IS NULL OR b.manifest_hash<>i.manifest_hash OR b.migration_run_id<>i.migration_run_id
   OR b.warehouse_id<>i.warehouse_id OR b.base_uom_code<>i.base_uom_code;

SELECT 'pilot_item_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE observed_item_count<>expected_item_count OR distinct_item_count<>expected_item_count
   OR distinct_ordinal_count<>expected_item_count OR distinct_source_count<>expected_item_count
   OR observed_on_hand_quantity<>expected_on_hand_quantity;

SELECT 'pilot_item_identity_not_unique' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE distinct_item_scope_hash_count<>expected_item_count OR distinct_item_manifest_count<>1
   OR distinct_warehouse_count<>1 OR distinct_base_uom_count<>1;

SELECT 'pilot_assessment_exact_match_failed' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE assessment_mismatch_count<>0;

SELECT 'pilot_actor_separation_failed' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE actor_separation_violation_count<>0;

SELECT 'pilot_post_admission_legacy_write' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE post_admission_legacy_write_count<>0;

SELECT 'pilot_production_qualification_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE qualification_event_count<>0;

SELECT 'pilot_production_opening_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_migration_pilot_batch
WHERE production_opening_event_count<>0;

SELECT 'pilot_execution_or_cutover_enabled' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_inventory_migration_pilot_readiness
WHERE execution_available<>0 OR cutover_ready<>0;

SELECT 'pilot_readiness_status_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_inventory_migration_pilot_readiness
WHERE readiness_status NOT IN ('FROZEN_AWAITING_APPROVAL','APPROVAL_IN_PROGRESS',
  'APPROVED_AWAITING_ADMISSION','ADMISSION_RECONCILED','ADMISSION_INCOMPLETE','INCONSISTENT');

SELECT 'pilot_admission_reconciliation_incomplete' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_inventory_migration_pilot_readiness
WHERE readiness_status='ADMISSION_RECONCILED'
  AND (batch_status<>'ADMISSION_PASSED' OR approved_item_count<>expected_item_count
    OR admitted_item_count<>expected_item_count OR observed_admitted_item_count<>expected_item_count
    OR approved_on_hand_quantity<>expected_on_hand_quantity
    OR admitted_on_hand_quantity<>expected_on_hand_quantity
    OR observed_admitted_on_hand_quantity<>expected_on_hand_quantity);

SELECT 'pilot_event_pii_or_principal_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE event_type IN ('inventory.migration.pilot_batch_status_changed','inventory.migration.pilot_item_status_changed')
  AND (get_json_string(payload,'$.mobile') IS NOT NULL
    OR get_json_string(payload,'$.phone') IS NOT NULL
    OR get_json_string(payload,'$.id_card') IS NOT NULL
    OR get_json_string(payload,'$.principal_id') IS NOT NULL);
