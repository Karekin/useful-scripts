-- Current-state projection of legacy browse-history rows.
-- This is not a sessionized clickstream or anonymous-visitor event log.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_product_browse_history_current AS
SELECT
    'yudao-commerce-observability' AS source_system,
    'product_browse_history' AS source_table,
    browse.tenant_id,
    browse.id AS legacy_browse_history_id,
    CONCAT('yudao-commerce-observability:', CAST(browse.tenant_id AS STRING), ':product_browse_history:', CAST(browse.id AS STRING))
        AS legacy_browse_history_key,
    browse.user_id AS legacy_user_id,
    browse.spu_id AS legacy_spu_id,
    browse.user_deleted AS source_user_deleted_flag,
    browse.create_time AS source_created_at,
    browse.update_time AS source_updated_at,
    browse.deleted AS is_deleted,
    browse.update_time < browse.create_time AS update_before_create_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.product_browse_history browse;
