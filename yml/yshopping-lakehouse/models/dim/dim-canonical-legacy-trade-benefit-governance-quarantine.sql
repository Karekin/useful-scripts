CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_benefit_governance_quarantine AS
SELECT
    event.tenant_id,
    event.governance_run_id,
    event.source_migration_run_id,
    event.candidate_id,
    event.legacy_order_id,
    get_json_string(event.quarantine, '$.quarantine_governance_id') AS quarantine_governance_id,
    get_json_string(event.quarantine, '$.legacy_order_no') AS legacy_order_no,
    get_json_string(event.quarantine, '$.source_candidate_evidence_hash') AS source_candidate_evidence_hash,
    get_json_string(event.quarantine, '$.source_assessment_status') AS source_assessment_status,
    json_query(event.quarantine, '$.source_reason_codes') AS source_reason_codes,
    get_json_string(event.quarantine, '$.decision_id') AS decision_id,
    get_json_string(event.quarantine, '$.decision_status') AS decision_status,
    get_json_string(event.quarantine, '$.recommended_action') AS recommended_action,
    json_query(event.quarantine, '$.blocker_codes') AS blocker_codes,
    CAST(get_json_string(event.quarantine, '$.canonical_import_allowed') AS BOOLEAN) AS canonical_import_allowed,
    get_json_string(event.quarantine, '$.evidence_hash') AS evidence_hash,
    event.assessed_at
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_governance_event event
WHERE get_json_string(event.quarantine, '$.quarantine_governance_id') IS NOT NULL;
