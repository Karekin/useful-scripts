CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_policy_current AS
SELECT event_id, tenant_id, policy_id, aggregate_version, occurred_at, recorded_at, policy_code, policy_version,
       rules_sha256, previous_status, current_status, approved_by_principal_id, effective_from, operation, policy_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, policy_id) AS policy_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, policy_id ORDER BY policy_version DESC, aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_risk_policy_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_intelligence_taxonomy_version AS
SELECT event_id, tenant_id, taxonomy_id, taxonomy_version_id, definition_version, aggregate_version,
       event_code, level_codes_json, levels_sha256, previous_status, current_status,
       approved_by_principal_id, effective_from,
       LEAD(effective_from) OVER (PARTITION BY tenant_id, taxonomy_id ORDER BY definition_version) AS next_effective_from,
       taxonomy_source_system, source_table, source_record_key, source_version, source_observed_at,
       source_evidence_ref, source_evidence_sha256, occurred_at, recorded_at
FROM yshopping_dwd.dwd_canonical_intelligence_taxonomy_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_intelligence_taxonomy_current AS
SELECT head.event_id, head.tenant_id, head.taxonomy_id, head.aggregate_version, head.current_status,
       head.event_code, version_state.taxonomy_version_id, head.definition_version,
       version_state.level_codes_json, version_state.levels_sha256, version_state.approved_by_principal_id,
       version_state.effective_from, head.retired_at, head.retired_by_principal_id, head.reason_code,
       head.taxonomy_source_system, head.source_table, head.source_record_key, head.source_version,
       head.source_observed_at, head.source_evidence_ref, head.source_evidence_sha256,
       head.lifecycle_event_count, head.version_event_count, head.recorded_at
FROM (
    SELECT states.*,
           COUNT(*) OVER (PARTITION BY tenant_id, taxonomy_id) AS lifecycle_event_count,
           SUM(CASE WHEN event_kind = 'VERSION' THEN 1 ELSE 0 END)
             OVER (PARTITION BY tenant_id, taxonomy_id) AS version_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, taxonomy_id
             ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM (
        SELECT event_id, tenant_id, taxonomy_id, aggregate_version, definition_version, event_code,
               current_status, CAST(NULL AS DATETIME) AS retired_at,
               CAST(NULL AS VARCHAR(128)) AS retired_by_principal_id,
               CAST(NULL AS VARCHAR(64)) AS reason_code, taxonomy_source_system, source_table,
               source_record_key, source_version, source_observed_at, source_evidence_ref,
               source_evidence_sha256, recorded_at, 'VERSION' AS event_kind
        FROM yshopping_dwd.dwd_canonical_intelligence_taxonomy_version_event
        UNION ALL
        SELECT event_id, tenant_id, taxonomy_id, aggregate_version, definition_version, event_code,
               current_status, retired_at, retired_by_principal_id, reason_code, taxonomy_source_system,
               source_table, source_record_key, source_version, source_observed_at, source_evidence_ref,
               source_evidence_sha256, recorded_at, 'RETIREMENT' AS event_kind
        FROM yshopping_dwd.dwd_canonical_intelligence_taxonomy_retirement_event
    ) states
) head
JOIN yshopping_dim.dim_canonical_intelligence_taxonomy_version version_state
  ON version_state.tenant_id = head.tenant_id AND version_state.taxonomy_id = head.taxonomy_id
 AND version_state.definition_version = head.definition_version
WHERE head.rn = 1;

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
