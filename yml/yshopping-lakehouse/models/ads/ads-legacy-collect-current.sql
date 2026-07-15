-- Readiness exposure for legacy favorite current rows; capability flags keep the boundary explicit.
CREATE OR REPLACE VIEW yshopping_ads.ads_legacy_collect_current AS
WITH source_stats AS (
    SELECT
        tenant_id,
        COUNT(*) AS source_current_row_count,
        SUM(CASE WHEN invalid_legacy_user_id_flag OR invalid_legacy_spu_id_flag THEN 1 ELSE 0 END) AS source_invalid_reference_row_count
    FROM yshopping_dwd.dwd_legacy_collect_current
    GROUP BY tenant_id
), exposed_stats AS (
    SELECT
        tenant_id,
        SUM(current_favorite_row_count) AS exposed_current_row_count,
        SUM(active_favorite_row_count) AS active_favorite_row_count,
        SUM(duplicate_active_favorite_row_count) AS duplicate_active_favorite_row_count,
        SUM(exposed_invalid_reference_row_count) AS exposed_invalid_reference_row_count
    FROM yshopping_dws.dws_legacy_collect_current
    GROUP BY tenant_id
)
SELECT
    source.tenant_id,
    source.source_current_row_count,
    COALESCE(exposed.exposed_current_row_count, 0) AS exposed_current_row_count,
    COALESCE(exposed.active_favorite_row_count, 0) AS active_favorite_row_count,
    COALESCE(exposed.duplicate_active_favorite_row_count, 0) AS duplicate_active_favorite_row_count,
    source.source_invalid_reference_row_count,
    COALESCE(exposed.exposed_invalid_reference_row_count, 0) AS exposed_invalid_reference_row_count,
    source.source_invalid_reference_row_count - COALESCE(exposed.exposed_invalid_reference_row_count, 0) AS unexposed_invalid_reference_row_count,
    FALSE AS canonical_member_identity_available,
    FALSE AS favorite_event_history_available,
    FALSE AS preference_score_available,
    FALSE AS reminder_effect_available,
    'LEGACY_CURRENT_STATE_READINESS' AS model_semantics
FROM source_stats source
LEFT JOIN exposed_stats exposed ON exposed.tenant_id = source.tenant_id;
