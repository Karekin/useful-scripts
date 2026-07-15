-- Tenant/user aggregate of current favorite rows; no preference score or reminder outcome is inferred.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_collect_current AS
SELECT
    tenant_id,
    legacy_user_id,
    COUNT(*) AS current_favorite_row_count,
    SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS active_favorite_row_count,
    COUNT(DISTINCT CASE WHEN is_deleted = FALSE THEN legacy_spu_id ELSE NULL END) AS active_distinct_legacy_spu_count,
    SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END)
      - COUNT(DISTINCT CASE WHEN is_deleted = FALSE THEN legacy_spu_id ELSE NULL END) AS duplicate_active_favorite_row_count,
    SUM(CASE WHEN is_deleted = TRUE THEN 1 ELSE 0 END) AS deleted_favorite_row_count,
    SUM(CASE WHEN invalid_legacy_user_id_flag OR invalid_legacy_spu_id_flag THEN 1 ELSE 0 END) AS exposed_invalid_reference_row_count,
    MAX(source_updated_at) AS latest_source_updated_at,
    'LEGACY_CURRENT_STATE_AGGREGATE' AS model_semantics
FROM yshopping_dim.dim_legacy_collect_current
GROUP BY tenant_id, legacy_user_id;
