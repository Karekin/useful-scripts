-- Readiness exposure for the bounded legacy coupon current-state projection.
-- Explicit false capability flags prevent consumers from treating rows as canonical events.
CREATE OR REPLACE VIEW yshopping_ads.ads_legacy_coupon_current AS
WITH source_stats AS (
    SELECT
        tenant_id,
        COUNT(*) AS source_current_row_count,
        SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS source_non_deleted_row_count,
        SUM(CASE WHEN invalid_time_window_flag OR invalid_status_flag
                  OR invalid_discount_rule_flag OR incomplete_used_state_flag THEN 1 ELSE 0 END) AS source_anomaly_row_count
    FROM yshopping_dwd.dwd_legacy_coupon_current
    GROUP BY tenant_id
), exposed_stats AS (
    SELECT
        tenant_id,
        COUNT(*) AS exposed_current_row_count,
        SUM(CASE WHEN invalid_time_window_flag OR invalid_status_flag
                  OR invalid_discount_rule_flag OR incomplete_used_state_flag THEN 1 ELSE 0 END) AS exposed_source_anomaly_row_count,
        SUM(CASE WHEN missing_template_flag THEN 1 ELSE 0 END) AS missing_template_count
    FROM yshopping_dim.dim_legacy_coupon_current
    GROUP BY tenant_id
)
SELECT
    source.tenant_id,
    source.source_current_row_count,
    source.source_non_deleted_row_count,
    COALESCE(exposed.exposed_current_row_count, 0) AS exposed_current_row_count,
    source.source_anomaly_row_count,
    COALESCE(exposed.exposed_source_anomaly_row_count, 0) AS exposed_source_anomaly_row_count,
    source.source_anomaly_row_count - COALESCE(exposed.exposed_source_anomaly_row_count, 0) AS unexposed_source_anomaly_row_count,
    COALESCE(exposed.missing_template_count, 0) AS missing_template_count,
    FALSE AS canonical_coupon_identity_available,
    FALSE AS allocation_event_history_available,
    FALSE AS refund_semantics_available,
    'LEGACY_CURRENT_STATE_READINESS' AS model_semantics
FROM source_stats source
LEFT JOIN exposed_stats exposed ON exposed.tenant_id = source.tenant_id;
