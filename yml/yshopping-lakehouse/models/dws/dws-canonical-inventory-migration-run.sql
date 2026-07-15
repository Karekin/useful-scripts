CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_migration_run AS
WITH assessment AS (
    SELECT
        tenant_id,
        migration_run_id,
        MAX(policy_version) AS assessment_policy_version,
        COUNT(*) AS candidate_count,
        SUM(assessment_event_count) AS assessment_event_count,
        COUNT(DISTINCT source_id) AS distinct_source_count,
        COUNT(DISTINCT source_snapshot_hash) AS distinct_snapshot_count,
        SUM(CASE WHEN assessment_status = 'ELIGIBLE' THEN 1 ELSE 0 END) AS eligible_count,
        SUM(CASE WHEN assessment_status = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_count,
        SUM(CASE WHEN assessment_status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_count,
        SUM(CASE WHEN assessment_status = 'BLOCKED' AND blocker_codes_json IN ('[]', '', 'null') THEN 1 ELSE 0 END)
          AS blockerless_blocked_count,
        SUM(CASE WHEN assessment_status = 'ELIGIBLE' AND blocker_codes_json NOT IN ('[]', '', 'null') THEN 1 ELSE 0 END)
          AS eligible_with_blocker_count,
        SUM(CASE WHEN reservation_allocation_count <> 0 OR reservation_allocation_quantity <> 0 THEN 1 ELSE 0 END)
          AS false_allocation_claim_count,
        SUM(source_on_hand_quantity) AS source_on_hand_quantity,
        SUM(source_reserved_quantity) AS source_reserved_quantity,
        SUM(source_in_transit_quantity) AS source_in_transit_quantity,
        SUM(active_reservation_count) AS active_reservation_count,
        SUM(active_reservation_quantity) AS active_reservation_quantity,
        MIN(assessed_at) AS first_assessed_at,
        MAX(assessed_at) AS last_assessed_at,
        MAX(recorded_at) AS last_assessment_recorded_at
    FROM yshopping_dim.dim_canonical_inventory_migration_assessment_current
    GROUP BY tenant_id, migration_run_id
), qualification AS (
    SELECT
        q.tenant_id,
        q.migration_run_id,
        MAX(q.policy_version) AS qualification_policy_version,
        COUNT(*) AS qualification_count,
        SUM(q.qualification_event_count) AS qualification_event_count,
        COUNT(DISTINCT q.qualification_id) AS distinct_qualification_count,
        COUNT(DISTINCT q.assessment_id) AS distinct_qualified_assessment_count,
        COUNT(DISTINCT q.source_id) AS distinct_qualified_source_count,
        COUNT(DISTINCT q.source_snapshot_hash) AS distinct_qualified_snapshot_count,
        SUM(CASE WHEN q.source_classification = 'CONTROLLED_CANARY' THEN 1 ELSE 0 END) AS controlled_canary_count,
        SUM(CASE WHEN q.qualification_status <> 'QUALIFIED' THEN 1 ELSE 0 END) AS invalid_qualification_status_count,
        SUM(CASE WHEN q.source_reserved_quantity <> 0 OR q.source_in_transit_quantity <> 0 THEN 1 ELSE 0 END)
          AS nonzero_qualification_hold_count,
        SUM(CASE WHEN a.assessment_id IS NULL
                  OR a.source_id <> q.source_id
                  OR a.source_snapshot_hash <> q.source_snapshot_hash
                  OR a.source_classification <> 'CONTROLLED_CANARY'
                 THEN 1 ELSE 0 END) AS qualification_assessment_mismatch_count,
        SUM(q.source_on_hand_quantity) AS qualified_on_hand_quantity,
        MIN(q.qualified_at) AS first_qualified_at,
        MAX(q.qualified_at) AS last_qualified_at,
        MAX(q.recorded_at) AS last_qualification_recorded_at
    FROM yshopping_dim.dim_canonical_inventory_migration_qualification_current q
    LEFT JOIN yshopping_dim.dim_canonical_inventory_migration_assessment_current a
      ON a.tenant_id = q.tenant_id
     AND a.migration_run_id = q.migration_run_id
     AND a.assessment_id = q.assessment_id
    GROUP BY q.tenant_id, q.migration_run_id
), opening AS (
    SELECT
        tenant_id,
        get_json_string(payload, '$.migration_run_id') AS migration_run_id,
        COUNT(*) AS opening_event_count,
        COUNT(DISTINCT get_json_string(payload, '$.migration_qualification_id')) AS distinct_opening_qualification_count,
        COUNT(DISTINCT get_json_string(payload, '$.migration_candidate_id')) AS distinct_opening_candidate_count,
        COUNT(DISTINCT get_json_string(payload, '$.source_id')) AS distinct_opening_source_count,
        COUNT(DISTINCT get_json_string(payload, '$.source_snapshot_hash')) AS distinct_opening_snapshot_count,
        SUM(CAST(get_json_string(payload, '$.delta_on_hand_quantity') AS DECIMAL(24,6))) AS opening_on_hand_quantity,
        SUM(CASE WHEN CAST(get_json_string(payload, '$.delta_reserved_quantity') AS DECIMAL(24,6)) <> 0
                  OR CAST(get_json_string(payload, '$.delta_in_transit_quantity') AS DECIMAL(24,6)) <> 0
                 THEN 1 ELSE 0 END) AS opening_hold_delta_count,
        SUM(CASE WHEN get_json_string(payload, '$.opening_driver') <> 'INVENTORY_MIGRATION_QUALIFICATION'
                  OR get_json_string(payload, '$.migration_stage') <> 'MIGRATED'
                 THEN 1 ELSE 0 END) AS invalid_opening_driver_count,
        MIN(occurred_at) AS first_opened_at,
        MAX(occurred_at) AS last_opened_at,
        MAX(recorded_at) AS last_opening_recorded_at
    FROM yshopping_dwd.dwd_domain_event
    WHERE event_type = 'inventory.stock.changed'
      AND schema_version = 4
      AND source_system = 'cloudmold-inventory'
      AND get_json_string(payload, '$.business_type') = 'MIGRATION_OPENING'
    GROUP BY tenant_id, get_json_string(payload, '$.migration_run_id')
), legacy_source_fence AS (
    SELECT
        q.tenant_id,
        q.migration_run_id,
        COUNT(e.event_id) AS post_qualification_legacy_write_count
    FROM yshopping_dim.dim_canonical_inventory_migration_qualification_current q
    LEFT JOIN yshopping_dwd.dwd_domain_event e
      ON e.tenant_id = q.tenant_id
     AND e.event_type = 'inventory.stock.changed'
     AND e.schema_version IN (1, 2)
     AND e.source_system = 'cloudmold-inventory'
     AND e.aggregate_type = 'inventory_balance'
     AND e.aggregate_id = q.source_id
     AND e.aggregate_version > q.source_version
    GROUP BY q.tenant_id, q.migration_run_id
)
SELECT
    assessment.*,
    qualification.qualification_policy_version,
    COALESCE(qualification.qualification_count, 0) AS qualification_count,
    COALESCE(qualification.qualification_event_count, 0) AS qualification_event_count,
    COALESCE(qualification.distinct_qualification_count, 0) AS distinct_qualification_count,
    COALESCE(qualification.distinct_qualified_assessment_count, 0) AS distinct_qualified_assessment_count,
    COALESCE(qualification.distinct_qualified_source_count, 0) AS distinct_qualified_source_count,
    COALESCE(qualification.distinct_qualified_snapshot_count, 0) AS distinct_qualified_snapshot_count,
    COALESCE(qualification.controlled_canary_count, 0) AS controlled_canary_count,
    COALESCE(qualification.invalid_qualification_status_count, 0) AS invalid_qualification_status_count,
    COALESCE(qualification.nonzero_qualification_hold_count, 0) AS nonzero_qualification_hold_count,
    COALESCE(qualification.qualification_assessment_mismatch_count, 0) AS qualification_assessment_mismatch_count,
    COALESCE(qualification.qualified_on_hand_quantity, CAST(0 AS DECIMAL(24,6))) AS qualified_on_hand_quantity,
    qualification.first_qualified_at,
    qualification.last_qualified_at,
    qualification.last_qualification_recorded_at,
    COALESCE(opening.opening_event_count, 0) AS opening_event_count,
    COALESCE(opening.distinct_opening_qualification_count, 0) AS distinct_opening_qualification_count,
    COALESCE(opening.distinct_opening_candidate_count, 0) AS distinct_opening_candidate_count,
    COALESCE(opening.distinct_opening_source_count, 0) AS distinct_opening_source_count,
    COALESCE(opening.distinct_opening_snapshot_count, 0) AS distinct_opening_snapshot_count,
    COALESCE(opening.opening_on_hand_quantity, CAST(0 AS DECIMAL(24,6))) AS opening_on_hand_quantity,
    COALESCE(opening.opening_hold_delta_count, 0) AS opening_hold_delta_count,
    COALESCE(opening.invalid_opening_driver_count, 0) AS invalid_opening_driver_count,
    COALESCE(legacy_source_fence.post_qualification_legacy_write_count, 0)
      AS post_qualification_legacy_write_count,
    opening.first_opened_at,
    opening.last_opened_at,
    opening.last_opening_recorded_at
FROM assessment
LEFT JOIN qualification
  ON qualification.tenant_id = assessment.tenant_id
 AND qualification.migration_run_id = assessment.migration_run_id
LEFT JOIN opening
  ON opening.tenant_id = assessment.tenant_id
 AND opening.migration_run_id = assessment.migration_run_id
LEFT JOIN legacy_source_fence
  ON legacy_source_fence.tenant_id = assessment.tenant_id
 AND legacy_source_fence.migration_run_id = assessment.migration_run_id;
