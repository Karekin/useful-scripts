-- Readiness exposure for legacy activity current rows. Source anomalies are allowed only if exposed.
CREATE OR REPLACE VIEW yshopping_ads.ads_legacy_activity_current AS
WITH source_stats AS (
    SELECT
        tenant_id,
        COUNT(*) AS source_current_row_count,
        SUM(CASE WHEN invalid_time_window_flag THEN 1 ELSE 0 END) AS source_invalid_time_window_count
    FROM yshopping_dwd.dwd_legacy_activity_current
    GROUP BY tenant_id
), exposed_stats AS (
    SELECT
        tenant_id,
        SUM(current_activity_row_count) AS exposed_current_row_count,
        SUM(exposed_invalid_time_window_count) AS exposed_invalid_time_window_count,
        SUM(unknown_legacy_status_count) AS unknown_legacy_status_count
    FROM yshopping_dws.dws_legacy_activity_current
    GROUP BY tenant_id
)
SELECT
    source.tenant_id,
    source.source_current_row_count,
    COALESCE(exposed.exposed_current_row_count, 0) AS exposed_current_row_count,
    source.source_invalid_time_window_count,
    COALESCE(exposed.exposed_invalid_time_window_count, 0) AS exposed_invalid_time_window_count,
    source.source_invalid_time_window_count - COALESCE(exposed.exposed_invalid_time_window_count, 0) AS unexposed_invalid_time_window_count,
    COALESCE(exposed.unknown_legacy_status_count, 0) AS unknown_legacy_status_count,
    FALSE AS canonical_activity_identity_available,
    FALSE AS activity_event_history_available,
    'LEGACY_CURRENT_STATE_READINESS' AS model_semantics
FROM source_stats source
LEFT JOIN exposed_stats exposed ON exposed.tenant_id = source.tenant_id;
