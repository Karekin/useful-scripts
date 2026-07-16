CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_legacy_trade_benefit_migration_readiness AS
WITH backend_candidate_quality AS (
    SELECT
        backend.tenant_id,
        backend.migration_run_id,
        SUM(CASE WHEN offline.legacy_order_id IS NULL THEN 1 ELSE 0 END) AS missing_offline_candidate_count,
        SUM(CASE WHEN offline.legacy_order_id IS NOT NULL AND (
              backend.legacy_order_no <> offline.legacy_order_no
              OR backend.is_deleted <> offline.is_deleted
              OR backend.header_quantity <> offline.header_quantity
              OR backend.item_row_count <> offline.item_row_count
              OR backend.item_quantity <> offline.item_quantity
              OR backend.header_gross_amount_minor <> offline.header_gross_amount_minor
              OR backend.header_benefit_amount_minor <> offline.header_benefit_amount_minor
              OR backend.header_pay_amount_minor <> offline.header_pay_amount_minor
              OR backend.item_gross_amount_minor <> offline.item_gross_amount_minor
              OR backend.item_benefit_amount_minor <> offline.item_benefit_amount_minor
              OR backend.item_pay_amount_minor <> offline.item_pay_amount_minor
              OR backend.negative_money <> offline.negative_money_flag
              OR backend.header_money_mismatch <> offline.header_money_mismatch_flag
              OR backend.header_item_mismatch <> offline.header_item_mismatch_flag
              OR backend.invalid_item_money_count <> offline.invalid_item_money_count
              OR backend.assessment_status <> offline.assessment_status
              OR backend.canonical_import_allowed <> offline.canonical_import_allowed)
            THEN 1 ELSE 0 END) AS candidate_fact_mismatch_count
    FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event backend
    LEFT JOIN yshopping_dwd.dwd_legacy_trade_benefit_assessment offline
      ON offline.tenant_id = backend.tenant_id
     AND offline.legacy_order_id = backend.legacy_order_id
    GROUP BY backend.tenant_id, backend.migration_run_id
), offline_candidate_quality AS (
    SELECT
        run.tenant_id,
        run.migration_run_id,
        SUM(CASE WHEN backend.legacy_order_id IS NULL THEN 1 ELSE 0 END) AS missing_backend_candidate_count
    FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment run
    JOIN yshopping_dwd.dwd_legacy_trade_benefit_assessment offline
      ON offline.tenant_id = run.tenant_id
    LEFT JOIN yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event backend
      ON backend.tenant_id = run.tenant_id
     AND backend.migration_run_id = run.migration_run_id
     AND backend.legacy_order_id = offline.legacy_order_id
    GROUP BY run.tenant_id, run.migration_run_id
), backend_component_quality AS (
    SELECT
        backend.tenant_id,
        backend.migration_run_id,
        SUM(CASE WHEN offline.legacy_order_id IS NULL THEN 1 ELSE 0 END) AS missing_offline_component_count,
        SUM(CASE WHEN offline.legacy_order_id IS NOT NULL AND (
              backend.component_amount_minor <> offline.component_amount_minor
              OR backend.identity_resolution_status <> offline.identity_resolution_status
              OR backend.funding_resolution_status <> offline.funding_resolution_status
              OR backend.canonical_import_allowed <> offline.canonical_import_allowed)
            THEN 1 ELSE 0 END) AS component_fact_mismatch_count
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_component_assessment backend
    LEFT JOIN yshopping_dim.dim_legacy_trade_benefit_component_assessment offline
      ON offline.tenant_id = backend.tenant_id
     AND offline.legacy_order_id = backend.legacy_order_id
     AND offline.legacy_component_type = backend.component_type
    GROUP BY backend.tenant_id, backend.migration_run_id
), offline_component_quality AS (
    SELECT
        run.tenant_id,
        run.migration_run_id,
        SUM(CASE WHEN backend.legacy_order_id IS NULL THEN 1 ELSE 0 END) AS missing_backend_component_count
    FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment run
    JOIN yshopping_dim.dim_legacy_trade_benefit_component_assessment offline
      ON offline.tenant_id = run.tenant_id
    LEFT JOIN yshopping_dim.dim_canonical_legacy_trade_benefit_component_assessment backend
      ON backend.tenant_id = run.tenant_id
     AND backend.migration_run_id = run.migration_run_id
     AND backend.legacy_order_id = offline.legacy_order_id
     AND backend.component_type = offline.legacy_component_type
    GROUP BY run.tenant_id, run.migration_run_id
)
SELECT
    backend.tenant_id,
    backend.migration_run_id,
    backend.source_scope,
    backend.source_order_row_count AS backend_source_order_row_count,
    offline.source_order_row_count AS offline_source_order_row_count,
    backend.non_deleted_order_count AS backend_non_deleted_order_count,
    offline.non_deleted_order_count AS offline_non_deleted_order_count,
    backend.deleted_excluded_count AS backend_deleted_excluded_count,
    offline.deleted_excluded_count AS offline_deleted_excluded_count,
    backend.no_benefit_order_count AS backend_no_benefit_order_count,
    offline.no_benefit_order_count AS offline_no_benefit_order_count,
    backend.benefit_evidence_pending_order_count AS backend_benefit_evidence_pending_order_count,
    offline.benefit_evidence_pending_order_count AS offline_benefit_evidence_pending_order_count,
    backend.quarantined_order_count AS backend_quarantined_order_count,
    offline.quarantined_order_count AS offline_quarantined_order_count,
    backend.source_benefit_amount_minor AS backend_source_benefit_amount_minor,
    offline.source_benefit_amount_minor AS offline_source_benefit_amount_minor,
    backend.component_count AS backend_component_count,
    offline.component_count AS offline_component_count,
    backend.component_amount_minor AS backend_component_amount_minor,
    offline.component_amount_minor AS offline_component_amount_minor,
    backend.unresolved_identity_count AS backend_unresolved_identity_count,
    offline.unresolved_identity_count AS offline_unresolved_identity_count,
    backend.unresolved_funding_count AS backend_unresolved_funding_count,
    offline.unresolved_funding_count AS offline_unresolved_funding_count,
    COALESCE(backend_candidate_quality.missing_offline_candidate_count, 0) AS missing_offline_candidate_count,
    COALESCE(offline_candidate_quality.missing_backend_candidate_count, 0) AS missing_backend_candidate_count,
    COALESCE(backend_candidate_quality.candidate_fact_mismatch_count, 0) AS candidate_fact_mismatch_count,
    COALESCE(backend_component_quality.missing_offline_component_count, 0) AS missing_offline_component_count,
    COALESCE(offline_component_quality.missing_backend_component_count, 0) AS missing_backend_component_count,
    COALESCE(backend_component_quality.component_fact_mismatch_count, 0) AS component_fact_mismatch_count,
    backend.import_allowed_component_count,
    backend.production_migration_enabled,
    CASE
      WHEN offline.tenant_id IS NULL THEN 'BLOCKED_OFFLINE_ASSESSMENT_MISSING'
      WHEN backend.source_scope <> 'LOCAL_YUDAO_TRADE_CURRENT' THEN 'BLOCKED_SOURCE_SCOPE_MISMATCH'
      WHEN backend.source_order_row_count <> offline.source_order_row_count
        OR backend.non_deleted_order_count <> offline.non_deleted_order_count
        OR backend.deleted_excluded_count <> offline.deleted_excluded_count
        OR backend.no_benefit_order_count <> offline.no_benefit_order_count
        OR backend.benefit_evidence_pending_order_count <> offline.benefit_evidence_pending_order_count
        OR backend.quarantined_order_count <> offline.quarantined_order_count
        OR backend.source_benefit_amount_minor <> offline.source_benefit_amount_minor
        OR backend.component_count <> offline.component_count
        OR backend.component_amount_minor <> offline.component_amount_minor
        OR backend.unresolved_identity_count <> offline.unresolved_identity_count
        OR backend.unresolved_funding_count <> offline.unresolved_funding_count
        OR COALESCE(backend_candidate_quality.missing_offline_candidate_count, 0) <> 0
        OR COALESCE(offline_candidate_quality.missing_backend_candidate_count, 0) <> 0
        OR COALESCE(backend_candidate_quality.candidate_fact_mismatch_count, 0) <> 0
        OR COALESCE(backend_component_quality.missing_offline_component_count, 0) <> 0
        OR COALESCE(offline_component_quality.missing_backend_component_count, 0) <> 0
        OR COALESCE(backend_component_quality.component_fact_mismatch_count, 0) <> 0
        THEN 'BLOCKED_BACKEND_OFFLINE_MISMATCH'
      WHEN backend.import_allowed_component_count <> 0 OR backend.production_migration_enabled
        THEN 'BLOCKED_ILLEGAL_IMPORT_AUTHORITY'
      ELSE 'MATCHED_LOCAL_SNAPSHOT_BLOCKED_REQUIRES_GOVERNED_EVIDENCE'
    END AS reconciliation_status,
    FALSE AS exact_order_item_mapping_available,
    FALSE AS versioned_benefit_identity_available,
    FALSE AS named_funding_breakdown_available,
    'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE' AS governed_scope,
    'CANONICAL_LEGACY_TRADE_BENEFIT_MIGRATION_READINESS' AS model_semantics
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment backend
LEFT JOIN yshopping_dws.dws_legacy_trade_benefit_migration_assessment offline
  ON offline.tenant_id = backend.tenant_id
LEFT JOIN backend_candidate_quality
  ON backend_candidate_quality.tenant_id = backend.tenant_id
 AND backend_candidate_quality.migration_run_id = backend.migration_run_id
LEFT JOIN offline_candidate_quality
  ON offline_candidate_quality.tenant_id = backend.tenant_id
 AND offline_candidate_quality.migration_run_id = backend.migration_run_id
LEFT JOIN backend_component_quality
  ON backend_component_quality.tenant_id = backend.tenant_id
 AND backend_component_quality.migration_run_id = backend.migration_run_id
LEFT JOIN offline_component_quality
  ON offline_component_quality.tenant_id = backend.tenant_id
 AND offline_component_quality.migration_run_id = backend.migration_run_id;
