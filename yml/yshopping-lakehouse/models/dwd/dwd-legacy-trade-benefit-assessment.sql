-- Non-mutating assessment of the local Yudao Trade current snapshot.
-- It is not the Y-Shopping ods_trade_trade_discount_di source and it does not
-- manufacture canonical benefit identity, funding, allocation, or history.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_trade_benefit_assessment AS
WITH item_rollup AS (
    SELECT
        tenant_id,
        order_id AS legacy_order_id,
        COUNT(*) AS item_row_count,
        SUM(`count`) AS item_quantity,
        SUM(price * `count`) AS item_gross_amount_minor,
        SUM(discount_price) AS item_generic_discount_amount_minor,
        SUM(coupon_price) AS item_coupon_amount_minor,
        SUM(point_price) AS item_point_amount_minor,
        SUM(vip_price) AS item_vip_amount_minor,
        SUM(delivery_price) AS item_delivery_amount_minor,
        SUM(adjust_price) AS item_adjust_amount_minor,
        SUM(pay_price) AS item_pay_amount_minor,
        SUM(CASE
              WHEN price < 0 OR `count` <= 0 OR discount_price < 0 OR coupon_price < 0
                OR point_price < 0 OR vip_price < 0 OR delivery_price < 0 OR pay_price < 0
                OR price * `count` + delivery_price + adjust_price
                     <> discount_price + coupon_price + point_price + vip_price + pay_price
              THEN 1 ELSE 0
            END) AS invalid_item_money_count
    FROM yshopping_ods.trade_order_item
    WHERE deleted = FALSE
    GROUP BY tenant_id, order_id
), joined AS (
    SELECT
        'yudao-mall' AS source_system,
        'trade_order' AS source_table,
        orders.tenant_id,
        orders.id AS legacy_order_id,
        orders.no AS legacy_order_no,
        CONCAT('yudao-mall:', CAST(orders.tenant_id AS STRING), ':trade_order:', CAST(orders.id AS STRING))
            AS legacy_order_key,
        orders.status AS legacy_order_status_code,
        orders.product_count AS header_quantity,
        orders.total_price AS header_gross_amount_minor,
        orders.discount_price AS header_generic_discount_amount_minor,
        orders.coupon_price AS header_coupon_amount_minor,
        orders.point_price AS header_point_amount_minor,
        orders.vip_price AS header_vip_amount_minor,
        orders.delivery_price AS header_delivery_amount_minor,
        orders.adjust_price AS header_adjust_amount_minor,
        orders.pay_price AS header_pay_amount_minor,
        orders.coupon_id AS legacy_coupon_id,
        orders.use_point AS legacy_used_point_quantity,
        orders.seckill_activity_id AS legacy_seckill_activity_id,
        orders.bargain_activity_id AS legacy_bargain_activity_id,
        orders.combination_activity_id AS legacy_combination_activity_id,
        orders.point_activity_id AS legacy_point_activity_id,
        orders.create_time AS source_created_at,
        orders.update_time AS source_updated_at,
        orders.deleted AS is_deleted,
        COALESCE(items.item_row_count, 0) AS item_row_count,
        COALESCE(items.item_quantity, 0) AS item_quantity,
        COALESCE(items.item_gross_amount_minor, 0) AS item_gross_amount_minor,
        COALESCE(items.item_generic_discount_amount_minor, 0) AS item_generic_discount_amount_minor,
        COALESCE(items.item_coupon_amount_minor, 0) AS item_coupon_amount_minor,
        COALESCE(items.item_point_amount_minor, 0) AS item_point_amount_minor,
        COALESCE(items.item_vip_amount_minor, 0) AS item_vip_amount_minor,
        COALESCE(items.item_delivery_amount_minor, 0) AS item_delivery_amount_minor,
        COALESCE(items.item_adjust_amount_minor, 0) AS item_adjust_amount_minor,
        COALESCE(items.item_pay_amount_minor, 0) AS item_pay_amount_minor,
        COALESCE(items.invalid_item_money_count, 0) AS invalid_item_money_count
    FROM yshopping_ods.trade_order orders
    LEFT JOIN item_rollup items
      ON items.tenant_id = orders.tenant_id
     AND items.legacy_order_id = orders.id
), assessed AS (
    SELECT
        joined.*,
        header_generic_discount_amount_minor + header_coupon_amount_minor
          + header_point_amount_minor + header_vip_amount_minor AS header_benefit_amount_minor,
        item_generic_discount_amount_minor + item_coupon_amount_minor
          + item_point_amount_minor + item_vip_amount_minor AS item_benefit_amount_minor,
        (header_gross_amount_minor < 0 OR header_generic_discount_amount_minor < 0
          OR header_coupon_amount_minor < 0 OR header_point_amount_minor < 0
          OR header_vip_amount_minor < 0 OR header_delivery_amount_minor < 0
          OR header_pay_amount_minor < 0) AS negative_money_flag,
        (header_gross_amount_minor + header_delivery_amount_minor + header_adjust_amount_minor
          <> header_generic_discount_amount_minor + header_coupon_amount_minor
             + header_point_amount_minor + header_vip_amount_minor + header_pay_amount_minor)
          AS header_money_mismatch_flag,
        (item_row_count = 0 OR header_quantity <> item_quantity
          OR header_gross_amount_minor <> item_gross_amount_minor
          OR header_generic_discount_amount_minor <> item_generic_discount_amount_minor
          OR header_coupon_amount_minor <> item_coupon_amount_minor
          OR header_point_amount_minor <> item_point_amount_minor
          OR header_vip_amount_minor <> item_vip_amount_minor
          OR header_delivery_amount_minor <> item_delivery_amount_minor
          OR header_adjust_amount_minor <> item_adjust_amount_minor
          OR header_pay_amount_minor <> item_pay_amount_minor) AS header_item_mismatch_flag
    FROM joined
)
SELECT
    assessed.*,
    CASE
      WHEN is_deleted THEN 'DELETED_EXCLUDED'
      WHEN negative_money_flag OR header_money_mismatch_flag OR invalid_item_money_count <> 0
        THEN 'QUARANTINED_MONEY'
      WHEN header_item_mismatch_flag THEN 'QUARANTINED_HEADER_ITEM'
      WHEN header_generic_discount_amount_minor + header_coupon_amount_minor
             + header_point_amount_minor + header_vip_amount_minor = 0
        THEN 'NO_BENEFIT'
      ELSE 'BENEFIT_REQUIRES_IDENTITY_AND_FUNDING'
    END AS assessment_status,
    FALSE AS canonical_import_allowed,
    'LEGACY_TRADE_BENEFIT_ASSESSMENT_ONLY' AS model_semantics
FROM assessed;
