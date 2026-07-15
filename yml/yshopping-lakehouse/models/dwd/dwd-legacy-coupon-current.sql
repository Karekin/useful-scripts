-- Bounded projection of the legacy Mall coupon table's current rows.
-- This is not a canonical coupon identity, allocation event stream, or SCD2 history.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_coupon_current AS
SELECT
    'yudao-mall' AS source_system,
    'promotion_coupon' AS source_table,
    coupon.tenant_id,
    coupon.id AS legacy_coupon_id,
    CONCAT('yudao-mall:', CAST(coupon.tenant_id AS STRING), ':promotion_coupon:', CAST(coupon.id AS STRING)) AS legacy_coupon_key,
    coupon.template_id AS legacy_coupon_template_id,
    coupon.user_id AS legacy_user_id,
    coupon.name AS coupon_name,
    coupon.status AS coupon_status_code,
    CASE coupon.status WHEN 1 THEN 'UNUSED' WHEN 2 THEN 'USED' WHEN 3 THEN 'EXPIRED' ELSE 'UNKNOWN_LEGACY_STATUS' END AS coupon_status_name,
    coupon.take_type AS take_type_code,
    coupon.use_price AS minimum_spend_amount_minor,
    coupon.valid_start_time,
    coupon.valid_end_time,
    coupon.product_scope AS product_scope_code,
    coupon.product_scope_values AS product_scope_values_raw,
    coupon.discount_type AS discount_type_code,
    coupon.discount_percent,
    coupon.discount_price AS discount_amount_minor,
    coupon.discount_limit_price AS discount_limit_amount_minor,
    coupon.use_order_id AS legacy_use_order_id,
    coupon.use_time,
    coupon.create_time AS source_created_at,
    coupon.update_time AS source_updated_at,
    coupon.deleted AS is_deleted,
    coupon.valid_start_time >= coupon.valid_end_time AS invalid_time_window_flag,
    coupon.status NOT IN (1, 2, 3) AS invalid_status_flag,
    (coupon.use_price < 0
      OR coupon.discount_type NOT IN (1, 2)
      OR (coupon.discount_type = 1 AND (coupon.discount_price IS NULL OR coupon.discount_price < 0))
      OR (coupon.discount_type = 2 AND (coupon.discount_percent IS NULL OR coupon.discount_percent < 1 OR coupon.discount_percent > 100))) AS invalid_discount_rule_flag,
    (coupon.status = 2 AND ((coupon.use_order_id IS NULL OR coupon.use_order_id = 0) OR coupon.use_time IS NULL)) AS incomplete_used_state_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.promotion_coupon coupon;
