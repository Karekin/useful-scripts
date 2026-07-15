CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_policy_current AS
SELECT event_id, tenant_id, policy_id, aggregate_version, occurred_at, recorded_at, policy_code, policy_version,
       rules_sha256, previous_status, current_status, approved_by_principal_id, effective_from, operation, policy_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, policy_id) AS policy_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, policy_id ORDER BY policy_version DESC, aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_risk_policy_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_cluster_current AS
SELECT event_id, tenant_id, cluster_id, aggregate_version, occurred_at, recorded_at, cluster_code, previous_status,
       current_status, risk_level, member_count, edge_count, operation, cluster_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, cluster_id) AS cluster_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, cluster_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_risk_cluster_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_review_case_current AS
SELECT event_id, tenant_id, case_id, aggregate_version, occurred_at, recorded_at, cluster_id, previous_status,
       current_status, reviewer_principal_id, operation, review_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, case_id) AS review_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, case_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_risk_review_event e
) ranked WHERE rn = 1;
