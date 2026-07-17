SELECT 'canonical_legacy_trade_product_identity_qualification_event_shape' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_product_identity_qualification_review_event
WHERE request_id<>payload_request_id OR request_version NOT BETWEEN 1 AND 3 OR schema_version<>1
   OR policy_version<>'legacy-trade-product-identity-qualification-v1'
   OR source_item_evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR historical_product_snapshot_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR scope_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR canonical_import_allowed OR production_migration_enabled;

SELECT 'canonical_legacy_trade_product_identity_qualification_state_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_product_identity_qualification_request_current
WHERE request_event_count<>request_version
   OR (request_status='PENDING' AND (request_version<>1 OR approval_count<>0 OR qualification_id IS NOT NULL))
   OR (request_status='PARTIALLY_APPROVED' AND (request_version<>2 OR approval_count<>1 OR qualification_id IS NOT NULL))
   OR (request_status='APPLIED' AND (request_version<>3 OR approval_count<>2
       OR approval_set_hash NOT REGEXP '^[0-9a-f]{64}$' OR qualification_id IS NULL));

SELECT 'canonical_legacy_trade_product_identity_qualification_actor_separation' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_product_identity_qualification_request_current
WHERE approval_count=2 AND (first_approver_system_user_id IS NULL OR second_approver_system_user_id IS NULL
   OR first_approver_system_user_id=second_approver_system_user_id
   OR requester_system_user_id IN (first_approver_system_user_id,second_approver_system_user_id));

SELECT 'canonical_legacy_trade_product_identity_qualification_false_authority' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_product_identity_qualification_readiness
WHERE canonical_import_available OR production_migration_enabled
   OR (workflow_status='GOVERNED_QUALIFICATION_REQUESTS_CLOSED'
       AND (event_sequence_mismatch_count>0 OR actor_separation_mismatch_count>0
            OR applied_proof_mismatch_count>0 OR pending_request_count>0
            OR partially_approved_request_count>0));
