-- Activity-kind aggregate over legacy current rows, including surfaced time-window anomalies.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_activity_current AS
SELECT
    tenant_id,
    activity_kind,
    COUNT(*) AS current_activity_row_count,
    SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS non_deleted_activity_row_count,
    SUM(CASE WHEN time_window_applicable THEN 1 ELSE 0 END) AS time_window_applicable_row_count,
    SUM(CASE WHEN invalid_time_window_flag THEN 1 ELSE 0 END) AS exposed_invalid_time_window_count,
    SUM(CASE WHEN activity_status_name = 'UNKNOWN_LEGACY_STATUS' THEN 1 ELSE 0 END) AS unknown_legacy_status_count,
    SUM(CASE WHEN observed_lifecycle = 'ACTIVE_BY_TIME' THEN 1 ELSE 0 END) AS active_by_time_row_count,
    MAX(source_updated_at) AS latest_source_updated_at,
    'LEGACY_CURRENT_STATE_AGGREGATE' AS model_semantics
FROM yshopping_dim.dim_legacy_activity_current
GROUP BY tenant_id, activity_kind;
