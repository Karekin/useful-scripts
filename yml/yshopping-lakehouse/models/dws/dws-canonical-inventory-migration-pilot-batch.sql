CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_migration_pilot_batch AS
WITH batch_history AS (
    SELECT
        tenant_id,pilot_batch_id,
        COUNT(*) AS batch_event_count,
        COUNT(DISTINCT batch_version) AS distinct_batch_version_count,
        MIN(batch_version) AS min_batch_version,
        MAX(batch_version) AS max_batch_version,
        COUNT(DISTINCT manifest_hash) AS distinct_manifest_count,
        COUNT(DISTINCT policy_hash) AS distinct_policy_count,
        COUNT(DISTINCT environment_fingerprint) AS distinct_environment_count,
        COUNT(DISTINCT expected_item_count) AS distinct_expected_item_count,
        COUNT(DISTINCT expected_on_hand_quantity) AS distinct_expected_quantity_count,
        SUM(CASE
              WHEN batch_version=1 AND batch_status='FROZEN' AND approval_count=0 THEN 0
              WHEN batch_version=2 AND batch_status='PARTIALLY_APPROVED' AND approval_count=1 THEN 0
              WHEN batch_version=3 AND batch_status='APPROVED' AND approval_count=2 THEN 0
              WHEN batch_version=4 AND batch_status='ADMISSION_PASSED' AND approval_count=2 THEN 0
              ELSE 1 END) AS invalid_batch_transition_count,
        MAX(recorded_at) AS last_batch_recorded_at
    FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event
    GROUP BY tenant_id,pilot_batch_id
), item AS (
    SELECT
        tenant_id,pilot_batch_id,
        COUNT(*) AS observed_item_count,
        COUNT(DISTINCT pilot_item_id) AS distinct_item_count,
        COUNT(DISTINCT manifest_ordinal) AS distinct_ordinal_count,
        COUNT(DISTINCT source_id) AS distinct_source_count,
        COUNT(DISTINCT item_scope_hash) AS distinct_item_scope_hash_count,
        COUNT(DISTINCT manifest_hash) AS distinct_item_manifest_count,
        COUNT(DISTINCT warehouse_id) AS distinct_warehouse_count,
        COUNT(DISTINCT base_uom_code) AS distinct_base_uom_count,
        SUM(source_on_hand_quantity) AS observed_on_hand_quantity,
        SUM(CASE WHEN item_status IN ('APPROVED','ADMISSION_PASSED') THEN 1 ELSE 0 END) AS observed_approved_item_count,
        SUM(CASE WHEN item_status IN ('APPROVED','ADMISSION_PASSED') THEN source_on_hand_quantity ELSE 0 END)
          AS observed_approved_on_hand_quantity,
        SUM(CASE WHEN item_status='ADMISSION_PASSED' THEN 1 ELSE 0 END) AS observed_admitted_item_count,
        SUM(CASE WHEN item_status='ADMISSION_PASSED' THEN source_on_hand_quantity ELSE 0 END)
          AS observed_admitted_on_hand_quantity,
        SUM(CASE WHEN item_event_count<>item_version OR item_version NOT IN (1,2,3) THEN 1 ELSE 0 END)
          AS item_version_gap_count,
        SUM(CASE
              WHEN item_version=1 AND item_status='FROZEN' THEN 0
              WHEN item_version=2 AND item_status='APPROVED' THEN 0
              WHEN item_version=3 AND item_status='ADMISSION_PASSED' THEN 0
              ELSE 1 END) AS invalid_item_transition_count,
        SUM(CASE WHEN source_classification<>'PRODUCTION_HISTORY' OR owner_type<>'MERCHANT'
                  OR source_on_hand_quantity<=0 OR source_reserved_quantity<>0 OR source_in_transit_quantity<>0
                  OR active_reservation_count<>0 OR active_reservation_quantity<>0
                  OR uom_conversion_ratio<>1 OR target_balance_absent<>TRUE OR bridge_absent<>TRUE
                 THEN 1 ELSE 0 END) AS out_of_scope_item_count,
        MAX(recorded_at) AS last_item_recorded_at
    FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current
    GROUP BY tenant_id,pilot_batch_id
), assessment_match AS (
    SELECT
        i.tenant_id,i.pilot_batch_id,
        SUM(CASE WHEN a.assessment_id IS NULL
                  OR a.migration_run_id<>i.migration_run_id
                  OR a.source_id<>i.source_id
                  OR a.source_snapshot_hash<>i.source_snapshot_hash
                  OR a.source_version<>i.source_version
                  OR a.source_on_hand_quantity<>i.source_on_hand_quantity
                  OR a.source_reserved_quantity<>i.source_reserved_quantity
                  OR a.source_in_transit_quantity<>i.source_in_transit_quantity
                  OR a.source_classification<>'UNCLASSIFIED'
                 THEN 1 ELSE 0 END) AS assessment_mismatch_count
    FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current i
    LEFT JOIN yshopping_dim.dim_canonical_inventory_migration_assessment_current a
      ON a.tenant_id=i.tenant_id AND a.assessment_id=i.assessment_id
    GROUP BY i.tenant_id,i.pilot_batch_id
), qualification AS (
    SELECT
        i.tenant_id,i.pilot_batch_id,COUNT(q.qualification_id) AS qualification_event_count
    FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current i
    LEFT JOIN yshopping_dim.dim_canonical_inventory_migration_qualification_current q
      ON q.tenant_id=i.tenant_id AND q.source_id=i.source_id
    GROUP BY i.tenant_id,i.pilot_batch_id
), opening AS (
    SELECT
        i.tenant_id,i.pilot_batch_id,COUNT(e.event_id) AS production_opening_event_count
    FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current i
    LEFT JOIN yshopping_dwd.dwd_domain_event e
      ON e.tenant_id=i.tenant_id
     AND e.event_type='inventory.stock.changed' AND e.schema_version=4
     AND get_json_string(e.payload,'$.migration_run_id')=i.migration_run_id
     AND get_json_string(e.payload,'$.source_id')=i.source_id
    GROUP BY i.tenant_id,i.pilot_batch_id
), source_drift AS (
    SELECT
        i.tenant_id,i.pilot_batch_id,COUNT(e.event_id) AS post_admission_legacy_write_count
    FROM yshopping_dim.dim_canonical_inventory_migration_pilot_item_current i
    LEFT JOIN yshopping_dwd.dwd_domain_event e
      ON e.tenant_id=i.tenant_id
     AND e.event_type='inventory.stock.changed' AND e.schema_version IN (1,2)
     AND e.aggregate_type='inventory_balance' AND e.aggregate_id=i.source_id
     AND e.aggregate_version>i.source_version
    WHERE i.item_status='ADMISSION_PASSED'
    GROUP BY i.tenant_id,i.pilot_batch_id
)
SELECT
    b.*,
    h.distinct_batch_version_count,h.min_batch_version,h.max_batch_version,
    h.distinct_manifest_count,h.distinct_policy_count,h.distinct_environment_count,
    h.distinct_expected_item_count,h.distinct_expected_quantity_count,h.invalid_batch_transition_count,
    h.last_batch_recorded_at,
    COALESCE(i.observed_item_count,0) AS observed_item_count,
    COALESCE(i.distinct_item_count,0) AS distinct_item_count,
    COALESCE(i.distinct_ordinal_count,0) AS distinct_ordinal_count,
    COALESCE(i.distinct_source_count,0) AS distinct_source_count,
    COALESCE(i.distinct_item_scope_hash_count,0) AS distinct_item_scope_hash_count,
    COALESCE(i.distinct_item_manifest_count,0) AS distinct_item_manifest_count,
    COALESCE(i.distinct_warehouse_count,0) AS distinct_warehouse_count,
    COALESCE(i.distinct_base_uom_count,0) AS distinct_base_uom_count,
    COALESCE(i.observed_on_hand_quantity,CAST(0 AS DECIMAL(24,6))) AS observed_on_hand_quantity,
    COALESCE(i.observed_approved_item_count,0) AS observed_approved_item_count,
    COALESCE(i.observed_approved_on_hand_quantity,CAST(0 AS DECIMAL(24,6))) AS observed_approved_on_hand_quantity,
    COALESCE(i.observed_admitted_item_count,0) AS observed_admitted_item_count,
    COALESCE(i.observed_admitted_on_hand_quantity,CAST(0 AS DECIMAL(24,6))) AS observed_admitted_on_hand_quantity,
    COALESCE(i.item_version_gap_count,0) AS item_version_gap_count,
    COALESCE(i.invalid_item_transition_count,0) AS invalid_item_transition_count,
    COALESCE(i.out_of_scope_item_count,0) AS out_of_scope_item_count,
    i.last_item_recorded_at,
    COALESCE(a.assessment_mismatch_count,0) AS assessment_mismatch_count,
    COALESCE(q.qualification_event_count,0) AS qualification_event_count,
    COALESCE(o.production_opening_event_count,0) AS production_opening_event_count,
    COALESCE(d.post_admission_legacy_write_count,0) AS post_admission_legacy_write_count,
    CASE WHEN b.requester_system_user_id IN (b.first_approver_system_user_id,b.second_approver_system_user_id)
           OR b.first_approver_system_user_id=b.second_approver_system_user_id
           OR (b.executor_system_user_id IS NOT NULL AND b.executor_system_user_id IN (
                 b.requester_system_user_id,b.first_approver_system_user_id,b.second_approver_system_user_id))
         THEN 1 ELSE 0 END AS actor_separation_violation_count
FROM yshopping_dim.dim_canonical_inventory_migration_pilot_batch_current b
JOIN batch_history h ON h.tenant_id=b.tenant_id AND h.pilot_batch_id=b.pilot_batch_id
LEFT JOIN item i ON i.tenant_id=b.tenant_id AND i.pilot_batch_id=b.pilot_batch_id
LEFT JOIN assessment_match a ON a.tenant_id=b.tenant_id AND a.pilot_batch_id=b.pilot_batch_id
LEFT JOIN qualification q ON q.tenant_id=b.tenant_id AND q.pilot_batch_id=b.pilot_batch_id
LEFT JOIN opening o ON o.tenant_id=b.tenant_id AND o.pilot_batch_id=b.pilot_batch_id
LEFT JOIN source_drift d ON d.tenant_id=b.tenant_id AND d.pilot_batch_id=b.pilot_batch_id;
