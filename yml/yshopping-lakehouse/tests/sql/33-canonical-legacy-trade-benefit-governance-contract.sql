SELECT 'canonical_legacy_trade_benefit_governance_event_identity_mismatch' AS check_name,
       COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_governance_event
WHERE candidate_id <> payload_candidate_id OR governance_version <> 1
   OR schema_version NOT IN (1,2)
   OR (schema_version=1 AND governance_evaluation_id<>candidate_id)
   OR (schema_version=2 AND governance_evaluation_id=candidate_id)
   OR policy_version <> 'legacy-trade-benefit-governance-v1'
   OR governance_evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR production_migration_enabled;

SELECT 'canonical_legacy_trade_benefit_governance_component_shape_invalid' AS check_name,
       COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_governance_component
WHERE source_component_evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR evidence_hash NOT REGEXP '^[0-9a-f]{64}$' OR canonical_import_allowed
   OR current_reference_status NOT IN (
        'CURRENT_REFERENCE_OBSERVED_NOT_HISTORICAL_VERSION','MISSING_SOURCE_REFERENCE',
        'SOURCE_REFERENCE_NOT_FOUND','NON_VERSIONED_ENTITLEMENT_QUANTITY_ONLY')
   OR (current_reference_status='CURRENT_REFERENCE_OBSERVED_NOT_HISTORICAL_VERSION' AND (
       observed_source_table IS NULL OR observed_source_id IS NULL
       OR current_reference_snapshot_hash NOT REGEXP '^[0-9a-f]{64}$'))
   OR (governance_status='READY' AND (
       historical_identity_status<>'QUALIFIED' OR funding_resolution_status<>'QUALIFIED'
       OR NOT governance_admission_allowed))
   OR (governance_status='BLOCKED' AND governance_admission_allowed);

SELECT 'canonical_legacy_trade_benefit_governance_quarantine_shape_invalid' AS check_name,
       COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_governance_quarantine
WHERE source_candidate_evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR evidence_hash NOT REGEXP '^[0-9a-f]{64}$' OR canonical_import_allowed
   OR source_assessment_status NOT IN ('QUARANTINED_MONEY','QUARANTINED_HEADER_ITEM')
   OR (decision_status='OPEN' AND (
       decision_id IS NOT NULL OR recommended_action<>'CORRECT_SOURCE_AND_REASSESS'))
   OR (decision_status='DECIDED' AND (
       decision_id IS NULL OR recommended_action<>'EXCLUDE_CONFIRMED_SOURCE_DEFECT'));

SELECT 'canonical_legacy_trade_benefit_governance_declared_denominator_mismatch' AS check_name,
       COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_governance
WHERE declared_source_component_count<>component_count
   OR declared_source_reference_present_count<>source_reference_present_count
   OR declared_current_reference_observed_count<>current_reference_observed_count
   OR declared_historical_identity_qualified_count<>historical_identity_qualified_count
   OR declared_identity_blocked_count<>identity_blocked_count
   OR declared_funding_qualified_count<>funding_qualified_count
   OR declared_funding_blocked_count<>funding_blocked_count
   OR declared_source_quarantine_count<>quarantine_count
   OR declared_quarantine_decided_count<>quarantine_decided_count
   OR declared_quarantine_open_count<>quarantine_open_count
   OR declared_governance_admitted_component_count<>governance_admitted_component_count;

SELECT 'canonical_legacy_trade_benefit_governance_false_import_readiness' AS check_name,
       COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_benefit_governance_readiness
WHERE canonical_import_available OR production_migration_enabled
   OR canonical_import_allowed_component_count<>0
   OR canonical_import_allowed_quarantine_count<>0
   OR governed_scope<>'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE';

SELECT 'canonical_legacy_trade_benefit_governance_source_denominator_mismatch' AS check_name,
       COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_benefit_governance_readiness
WHERE readiness_status='BLOCKED_GOVERNANCE_DENOMINATOR_MISMATCH';
