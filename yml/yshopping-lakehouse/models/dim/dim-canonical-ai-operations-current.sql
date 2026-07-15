CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_ai_application_current AS
SELECT event_id, tenant_id, application_id, aggregate_version, occurred_at, recorded_at,
       application_code, application_name, previous_status, current_status, operation, application_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, application_id) AS application_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, application_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_ai_application_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_ai_workflow_current AS
SELECT event_id, tenant_id, workflow_id, aggregate_version, occurred_at, recorded_at,
       workflow_code, application_id, workflow_version, definition_sha256, published_at, operation, version_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, workflow_id) AS version_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, workflow_id ORDER BY workflow_version DESC, aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_ai_workflow_version_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_ai_workflow_run_current AS
SELECT event_id, tenant_id, run_id, aggregate_version, occurred_at, recorded_at, application_id, workflow_id,
       workflow_version, trigger_type, previous_status, current_status, expected_invocation_count,
       started_at, finished_at, error_code, operation, run_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, run_id) AS run_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, run_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_ai_workflow_run_event e
) ranked WHERE rn = 1;
