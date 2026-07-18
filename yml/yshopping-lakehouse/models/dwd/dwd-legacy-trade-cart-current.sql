-- Current-state projection of legacy cart rows.
-- This is not an append-only add/remove cart behavior stream.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_trade_cart_current AS
SELECT
    'yudao-commerce-observability' AS source_system,
    'trade_cart' AS source_table,
    cart.tenant_id,
    cart.id AS legacy_cart_id,
    CONCAT('yudao-commerce-observability:', CAST(cart.tenant_id AS STRING), ':trade_cart:', CAST(cart.id AS STRING))
        AS legacy_cart_key,
    cart.user_id AS legacy_user_id,
    cart.spu_id AS legacy_spu_id,
    cart.sku_id AS legacy_sku_id,
    cart.count AS cart_quantity,
    cart.selected AS selected_flag,
    cart.create_time AS source_created_at,
    cart.update_time AS source_updated_at,
    cart.deleted AS is_deleted,
    cart.count <= 0 AS invalid_quantity_flag,
    cart.update_time < cart.create_time AS update_before_create_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.trade_cart cart;
