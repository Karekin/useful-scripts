CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_legacy_trade_product_identity_qualification_readiness AS
SELECT
    tenant_id,
    source_migration_run_id,
    request_count,
    pending_request_count,
    partially_approved_request_count,
    applied_qualification_count,
    applied_revocation_count,
    event_sequence_mismatch_count,
    actor_separation_mismatch_count,
    applied_proof_mismatch_count,
    evidence_verification_mismatch_count,
    CASE
      WHEN evidence_verification_mismatch_count>0
        THEN 'BLOCKED_HISTORICAL_PRODUCT_EVIDENCE_NOT_CONTENT_VERIFIED'
      WHEN event_sequence_mismatch_count>0 OR actor_separation_mismatch_count>0
        OR applied_proof_mismatch_count>0 THEN 'BLOCKED_QUALIFICATION_WORKFLOW_PROOF_MISMATCH'
      WHEN pending_request_count>0 OR partially_approved_request_count>0
        THEN 'AWAITING_INDEPENDENT_QUALIFICATION_REVIEW'
      ELSE 'GOVERNED_QUALIFICATION_REQUESTS_CLOSED'
    END AS workflow_status,
    FALSE AS canonical_import_available,
    FALSE AS production_migration_enabled,
    last_reviewed_at,
    'CONTENT_VERIFIED_QUALIFICATION_REVIEW_IS_EVIDENCE_NOT_IMPORT_AUTHORITY' AS readiness_semantics
FROM yshopping_dws.dws_canonical_legacy_trade_product_identity_qualification_workflow;
