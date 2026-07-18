CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_commerce_session_current AS
SELECT
    latest_status.event_id,
    latest_status.tenant_id,
    latest_status.session_id,
    latest_status.aggregate_version,
    latest_status.occurred_at,
    latest_status.recorded_at,
    latest_status.correlation_id,
    latest_status.causation_id,
    latest_status.idempotency_key,
    latest_status.run_id,
    status_rollup.started_at,
    COALESCE(behavior.last_behavior_at, status_rollup.last_activity_at, latest_link.linked_at, status_rollup.started_at)
        AS last_activity_at,
    latest_status.previous_status,
    latest_status.current_status,
    latest_status.channel_code,
    latest_status.entrypoint_code,
    latest_status.source_system_ref,
    latest_status.source_type,
    latest_status.source_id,
    COALESCE(latest_link.current_principal_id, latest_status.principal_id) AS current_principal_id,
    latest_link.previous_principal_id,
    latest_link.link_version,
    latest_link.session_status AS linked_session_status,
    latest_link.linked_at,
    latest_link.source_system_ref AS linked_source_system_ref,
    latest_link.source_type AS linked_source_type,
    latest_link.source_id AS linked_source_id,
    status_rollup.status_event_count,
    COALESCE(latest_link.identity_link_event_count, 0) AS identity_link_event_count,
    COALESCE(behavior.behavior_event_count, 0) AS behavior_event_count,
    COALESCE(behavior.search_request_count, 0) AS search_request_count,
    COALESCE(behavior.result_set_count, 0) AS result_set_count
FROM (
    SELECT
        event.*,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, session_id
            ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
        ) AS row_num
    FROM yshopping_dwd.dwd_canonical_commerce_session_status_event event
) latest_status
LEFT JOIN (
    SELECT
        tenant_id,
        session_id,
        MIN(started_at) AS started_at,
        MAX(last_activity_at) AS last_activity_at,
        COUNT(*) AS status_event_count
    FROM yshopping_dwd.dwd_canonical_commerce_session_status_event
    GROUP BY tenant_id, session_id
) status_rollup
  ON status_rollup.tenant_id = latest_status.tenant_id
 AND status_rollup.session_id = latest_status.session_id
LEFT JOIN (
    SELECT
        ranked.tenant_id,
        ranked.session_id,
        ranked.previous_principal_id,
        ranked.current_principal_id,
        ranked.link_version,
        ranked.session_status,
        ranked.linked_at,
        ranked.source_system_ref,
        ranked.source_type,
        ranked.source_id,
        ranked.identity_link_event_count
    FROM (
        SELECT
            event.*,
            COUNT(*) OVER (PARTITION BY tenant_id, session_id) AS identity_link_event_count,
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, session_id
                ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
            ) AS row_num
        FROM yshopping_dwd.dwd_canonical_commerce_session_identity_link_event event
    ) ranked
    WHERE ranked.row_num = 1
) latest_link
  ON latest_link.tenant_id = latest_status.tenant_id
 AND latest_link.session_id = latest_status.session_id
LEFT JOIN (
    SELECT
        tenant_id,
        session_id,
        COUNT(*) AS behavior_event_count,
        COUNT(DISTINCT CASE WHEN search_token IS NOT NULL THEN search_token END) AS search_request_count,
        COUNT(DISTINCT CASE WHEN result_set_token IS NOT NULL THEN result_set_token END) AS result_set_count,
        MAX(COALESCE(behavior_occurred_at, occurred_at)) AS last_behavior_at
    FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
    GROUP BY tenant_id, session_id
) behavior
  ON behavior.tenant_id = latest_status.tenant_id
 AND behavior.session_id = latest_status.session_id
WHERE latest_status.row_num = 1;
