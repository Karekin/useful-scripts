-- Canonical AI Operations, Token Platform and Risk first-slice DQC.
SELECT 'ai_token_risk_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_id FROM yshopping_dwd.dwd_domain_event
    WHERE source_system IN ('cloudmold-ai-operations','cloudmold-token-platform','cloudmold-risk')
    GROUP BY tenant_id, event_id HAVING COUNT(*) <> 1
) duplicates;

SELECT 'ai_workflow_orphan_application' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_ai_workflow_current w
LEFT JOIN yshopping_dim.dim_canonical_ai_application_current a
  ON a.tenant_id = w.tenant_id AND a.application_id = w.application_id
WHERE a.application_id IS NULL;

SELECT 'ai_run_orphan_workflow' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_ai_workflow_run_current r
LEFT JOIN yshopping_dim.dim_canonical_ai_workflow_current w
  ON w.tenant_id = r.tenant_id AND w.workflow_id = r.workflow_id AND w.workflow_version = r.workflow_version
WHERE w.workflow_id IS NULL OR w.application_id <> r.application_id;

SELECT 'ai_invocation_token_conservation' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_ai_model_invocation_event
WHERE input_tokens < 0 OR cached_input_tokens < 0 OR output_tokens < 0
   OR total_tokens <> input_tokens + output_tokens OR cached_input_tokens > input_tokens
   OR latency_millis < 0;

SELECT 'ai_invocation_price_pair_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_ai_model_invocation_event
WHERE (cost_amount_minor IS NULL) <> (currency_code IS NULL)
   OR COALESCE(cost_amount_minor, 0) < 0;

SELECT 'ai_terminal_run_invocation_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_ai_workflow_run_current
WHERE current_status IN ('SUCCEEDED','FAILED','CANCELLED')
  AND expected_invocation_count <> invocation_count;

SELECT 'ai_feedback_orphan_run' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_ai_outcome_feedback_event f
LEFT JOIN yshopping_dim.dim_canonical_ai_workflow_run_current r
  ON r.tenant_id = f.tenant_id AND r.run_id = f.run_id
WHERE r.run_id IS NULL;

SELECT 'token_credential_orphan_offering' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_token_access_credential_current c
LEFT JOIN yshopping_dim.dim_canonical_token_model_offering_current o
  ON o.tenant_id = c.tenant_id AND o.offering_id = c.offering_id
WHERE o.offering_id IS NULL;

SELECT 'token_credential_sensitive_material_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_token_access_credential_current
WHERE credential_fingerprint IS NULL OR LENGTH(credential_fingerprint) <> 64
   OR LOWER(credential_fingerprint) LIKE 'sk-%' OR credential_fingerprint LIKE '% %';

SELECT 'token_usage_token_conservation' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_token_invocation_usage_event
WHERE input_tokens < 0 OR cached_input_tokens < 0 OR output_tokens < 0
   OR total_tokens <> input_tokens + output_tokens OR cached_input_tokens > input_tokens
   OR duration_millis < 0 OR quota_cost_microunits < 0;

SELECT 'token_usage_without_quota_ledger' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_token_invocation_usage_event u
LEFT JOIN yshopping_dwd.dwd_canonical_token_quota_ledger_event l
  ON l.tenant_id = u.tenant_id AND l.ledger_entry_id = u.ledger_entry_id
WHERE l.ledger_entry_id IS NULL
   OR l.account_id IS NULL
   OR l.principal_id <> u.principal_id
   OR l.signed_delta_microunits <> -u.quota_cost_microunits;

SELECT 'token_quota_balance_not_ledger_derived' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_token_quota_account_current current_account
LEFT JOIN (
    SELECT tenant_id, account_id, SUM(signed_delta_microunits) AS derived_balance
    FROM yshopping_dwd.dwd_canonical_token_quota_ledger_event GROUP BY tenant_id, account_id
) ledger ON ledger.tenant_id = current_account.tenant_id AND ledger.account_id = current_account.account_id
WHERE current_account.balance_after_microunits <> ledger.derived_balance
   OR current_account.balance_after_microunits < 0;

SELECT 'risk_signal_orphan_policy_version' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_signal_event s
LEFT JOIN yshopping_dwd.dwd_canonical_risk_policy_event p
  ON p.tenant_id = s.tenant_id AND p.policy_id = s.policy_id AND p.policy_version = s.policy_version
WHERE p.policy_id IS NULL;

SELECT 'risk_relationship_self_edge' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_relationship_event
WHERE subject_principal_id = related_principal_id;

SELECT 'risk_relationship_time_or_confidence_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_relationship_event
WHERE first_seen_at > last_seen_at OR confidence_basis_points < 0 OR confidence_basis_points > 10000;

SELECT 'risk_raw_medium_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_relationship_event
WHERE medium_token IS NULL OR medium_token NOT REGEXP '^[0-9a-f]{64}$';

SELECT 'risk_review_orphan_cluster' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_risk_review_case_current r
LEFT JOIN yshopping_dim.dim_canonical_risk_cluster_current c
  ON c.tenant_id = r.tenant_id AND c.cluster_id = r.cluster_id
WHERE c.cluster_id IS NULL;

SELECT 'risk_decision_orphan_review' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_decision_event d
LEFT JOIN yshopping_dim.dim_canonical_risk_review_case_current r
  ON r.tenant_id = d.tenant_id AND r.case_id = d.case_id
WHERE r.case_id IS NULL OR r.cluster_id <> d.cluster_id;

SELECT 'risk_feedback_orphan_decision' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_feedback_event f
LEFT JOIN yshopping_dwd.dwd_canonical_risk_decision_event d
  ON d.tenant_id = f.tenant_id AND d.decision_id = f.decision_id
WHERE d.decision_id IS NULL OR d.case_id <> f.case_id;

SELECT 'risk_terminal_review_without_decision' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_risk_review_current
WHERE review_status IN ('DECIDED','CLOSED') AND decision_count = 0;

SELECT 'risk_automatic_enforcement_enabled' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_risk_readiness
WHERE automatic_enforcement_enabled <> false;
