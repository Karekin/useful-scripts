CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_legacy_trade_product_identity_qualification_workflow AS
SELECT
    tenant_id,
    source_migration_run_id,
    COUNT(*) AS request_count,
    SUM(CASE WHEN request_status='PENDING' THEN 1 ELSE 0 END) AS pending_request_count,
    SUM(CASE WHEN request_status='PARTIALLY_APPROVED' THEN 1 ELSE 0 END) AS partially_approved_request_count,
    SUM(CASE WHEN request_status='APPLIED' AND action_type='QUALIFY' THEN 1 ELSE 0 END)
        AS applied_qualification_count,
    SUM(CASE WHEN request_status='APPLIED' AND action_type='REVOKE' THEN 1 ELSE 0 END)
        AS applied_revocation_count,
    SUM(CASE WHEN request_event_count<>request_version THEN 1 ELSE 0 END) AS event_sequence_mismatch_count,
    SUM(CASE WHEN approval_count=2 AND (
          first_approver_system_user_id IS NULL OR second_approver_system_user_id IS NULL
          OR first_approver_system_user_id=second_approver_system_user_id
          OR requester_system_user_id IN (first_approver_system_user_id,second_approver_system_user_id))
        THEN 1 ELSE 0 END) AS actor_separation_mismatch_count,
    SUM(CASE WHEN request_status='APPLIED' AND (
          approval_count<>2 OR approval_set_hash NOT REGEXP '^[0-9a-f]{64}$'
          OR qualification_id IS NULL OR canonical_import_allowed OR production_migration_enabled)
        THEN 1 ELSE 0 END) AS applied_proof_mismatch_count,
    SUM(CASE WHEN action_type='QUALIFY' AND (evidence_verification_status IS NULL
          OR evidence_verification_status<>'VERIFIED'
          OR evidence_verifier_version IS NULL
          OR evidence_verifier_version<>'filesystem-content-addressed-sha256-v1'
          OR evidence_content_length IS NULL OR evidence_content_length<=0
          OR evidence_content_length>65536 OR evidence_verified_at IS NULL
          OR source_evidence_uri IS NULL
          OR source_evidence_uri<>CONCAT('evidence://sha256/',historical_product_snapshot_hash))
        THEN 1 ELSE 0 END) AS evidence_verification_mismatch_count,
    MAX(reviewed_at) AS last_reviewed_at,
    'DUAL_REVIEW_CONTENT_VERIFIED_IMMUTABLE_HISTORICAL_PRODUCT_IDENTITY' AS model_semantics
FROM yshopping_dim.dim_canonical_legacy_trade_product_identity_qualification_request_current
GROUP BY tenant_id,source_migration_run_id;
