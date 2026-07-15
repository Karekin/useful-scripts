-- Bounded projection of legacy product_favorite current rows.
-- It is not canonical member identity, preference evidence, reminder effect, event history, or SCD2.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_collect_current AS
SELECT
    'yudao-mall' AS source_system,
    'product_favorite' AS source_table,
    favorite.tenant_id,
    favorite.id AS legacy_favorite_id,
    CONCAT('yudao-mall:', CAST(favorite.tenant_id AS STRING), ':product_favorite:', CAST(favorite.id AS STRING)) AS legacy_favorite_key,
    favorite.user_id AS legacy_user_id,
    favorite.spu_id AS legacy_spu_id,
    favorite.create_time AS source_created_at,
    favorite.update_time AS source_updated_at,
    favorite.deleted AS is_deleted,
    (favorite.user_id IS NULL OR favorite.user_id <= 0) AS invalid_legacy_user_id_flag,
    (favorite.spu_id IS NULL OR favorite.spu_id <= 0) AS invalid_legacy_spu_id_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.product_favorite favorite;
