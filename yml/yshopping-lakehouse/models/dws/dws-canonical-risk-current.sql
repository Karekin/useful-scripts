CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_risk_review_current AS
SELECT r.tenant_id, r.case_id, r.cluster_id, r.current_status AS review_status, r.reviewer_principal_id,
       c.cluster_code, c.current_status AS cluster_status, c.risk_level, c.member_count, c.edge_count,
       COALESCE(d.decision_count, 0) AS decision_count, d.latest_decision_type, d.latest_decision_at,
       COALESCE(f.feedback_count, 0) AS feedback_count, COALESCE(f.corrective_feedback_count, 0) AS corrective_feedback_count
FROM yshopping_dim.dim_canonical_risk_review_case_current r
LEFT JOIN yshopping_dim.dim_canonical_risk_cluster_current c
  ON c.tenant_id = r.tenant_id AND c.cluster_id = r.cluster_id
LEFT JOIN (
    SELECT tenant_id, case_id, COUNT(*) AS decision_count,
           MAX_BY(decision_type, occurred_at) AS latest_decision_type, MAX(occurred_at) AS latest_decision_at
    FROM yshopping_dwd.dwd_canonical_risk_decision_event GROUP BY tenant_id, case_id
) d ON d.tenant_id = r.tenant_id AND d.case_id = r.case_id
LEFT JOIN (
    SELECT tenant_id, case_id, COUNT(*) AS feedback_count,
           SUM(CASE WHEN feedback_type IN ('CORRECTED', 'NOT_ACTIONABLE') THEN 1 ELSE 0 END) AS corrective_feedback_count
    FROM yshopping_dwd.dwd_canonical_risk_feedback_event GROUP BY tenant_id, case_id
) f ON f.tenant_id = r.tenant_id AND f.case_id = r.case_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_risk_policy_effectiveness_current AS
SELECT p.tenant_id, p.policy_id, p.policy_code, p.policy_version, p.current_status,
       COUNT(s.signal_id) AS signal_count,
       COUNT(DISTINCT s.subject_principal_id) AS subject_count,
       SUM(CASE WHEN s.severity IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) AS high_risk_signal_count
FROM yshopping_dim.dim_canonical_risk_policy_current p
LEFT JOIN yshopping_dwd.dwd_canonical_risk_signal_event s
  ON s.tenant_id = p.tenant_id AND s.policy_id = p.policy_id AND s.policy_version = p.policy_version
GROUP BY p.tenant_id, p.policy_id, p.policy_code, p.policy_version, p.current_status;
