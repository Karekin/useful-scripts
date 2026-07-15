-- Current interpretation of legacy favorite rows without canonical identity or catalog joins.
CREATE OR REPLACE VIEW yshopping_dim.dim_legacy_collect_current AS
SELECT
    favorite.*,
    CASE WHEN is_deleted = TRUE THEN 'DELETED_CURRENT_ROW' ELSE 'ACTIVE_CURRENT_ROW' END AS favorite_row_state,
    'LEGACY_CURRENT_STATE_ENRICHMENT' AS dimension_semantics
FROM yshopping_dwd.dwd_legacy_collect_current favorite;
