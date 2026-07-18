-- Isolated current-state metrics from local legacy Yudao commerce sources.
-- This view is deliberately not a canonical fact and must never be added to the
-- canonical role metric mart without governed identity/history qualification.
CREATE OR REPLACE VIEW yshopping_ads.ads_legacy_commerce_source_metrics AS
WITH order_rollup AS (
    SELECT
        tenant_id,
        COUNT(*) AS source_order_count,
        SUM(CASE WHEN deleted = FALSE THEN 1 ELSE 0 END) AS active_order_count,
        SUM(CASE WHEN deleted = FALSE AND pay_status = TRUE THEN 1 ELSE 0 END) AS paid_order_count,
        COUNT(DISTINCT CASE WHEN deleted = FALSE AND pay_status = TRUE THEN user_id END)
            AS paid_buyer_count,
        SUM(CASE WHEN deleted = FALSE AND pay_status = TRUE THEN pay_price ELSE 0 END)
            AS gross_paid_amount_minor,
        SUM(CASE WHEN deleted = FALSE AND pay_status = TRUE
                 THEN pay_price - delivery_price ELSE 0 END) AS product_paid_amount_minor,
        SUM(CASE WHEN deleted = FALSE AND pay_status = TRUE THEN refund_price ELSE 0 END)
            AS refunded_amount_minor,
        SUM(CASE WHEN deleted = FALSE AND pay_status = FALSE AND status = 30 THEN 1 ELSE 0 END)
            AS unpaid_terminal_order_count,
        SUM(CASE WHEN deleted = FALSE AND refund_price > pay_price THEN 1 ELSE 0 END)
            AS refund_exceeds_paid_order_count,
        SUM(CASE WHEN deleted = FALSE AND pay_status = TRUE AND pay_time IS NULL THEN 1 ELSE 0 END)
            AS paid_order_missing_pay_time_count,
        MAX(update_time) AS data_freshness_at
    FROM yshopping_ods.trade_order
    GROUP BY tenant_id
), buyer_rollup AS (
    SELECT
        tenant_id,
        COUNT(*) AS paid_buyer_count,
        SUM(CASE WHEN paid_order_count >= 2 THEN 1 ELSE 0 END) AS repeat_buyer_count,
        SUM(paid_order_count) AS paid_order_count
    FROM (
        SELECT tenant_id, user_id, COUNT(DISTINCT id) AS paid_order_count
        FROM yshopping_ods.trade_order
        WHERE deleted = FALSE AND pay_status = TRUE
        GROUP BY tenant_id, user_id
    ) buyer
    GROUP BY tenant_id
), item_quality AS (
    SELECT
        orders.tenant_id,
        COUNT(*) AS active_item_on_deleted_order_count
    FROM yshopping_ods.trade_order_item item
    JOIN yshopping_ods.trade_order orders
      ON orders.tenant_id = item.tenant_id
     AND orders.id = item.order_id
    WHERE item.deleted = FALSE AND orders.deleted = TRUE
    GROUP BY orders.tenant_id
), payment_observability AS (
    SELECT *
    FROM yshopping_dws.dws_legacy_payment_current
), user_behavior_observability AS (
    SELECT *
    FROM yshopping_dws.dws_legacy_user_behavior_current
)
SELECT
    orders.tenant_id,
    orders.source_order_count,
    orders.active_order_count,
    orders.paid_order_count,
    orders.paid_buyer_count,
    buyers.repeat_buyer_count,
    CAST(buyers.repeat_buyer_count * 100.0 / NULLIF(buyers.paid_buyer_count, 0)
         AS DECIMAL(38,6)) AS repeat_buyer_rate,
    CAST(buyers.paid_order_count * 1.0 / NULLIF(buyers.paid_buyer_count, 0)
         AS DECIMAL(38,6)) AS average_order_frequency,
    CAST(orders.gross_paid_amount_minor / 100.0 AS DECIMAL(38,6)) AS gross_paid_amount_yuan,
    CAST(orders.product_paid_amount_minor / 100.0 AS DECIMAL(38,6)) AS product_paid_amount_yuan,
    CAST(orders.refunded_amount_minor / 100.0 AS DECIMAL(38,6)) AS refunded_amount_yuan,
    CAST((orders.gross_paid_amount_minor - orders.refunded_amount_minor) / 100.0
         AS DECIMAL(38,6)) AS net_paid_amount_yuan,
    orders.unpaid_terminal_order_count,
    orders.refund_exceeds_paid_order_count,
    orders.paid_order_missing_pay_time_count,
    COALESCE(items.active_item_on_deleted_order_count, 0) AS active_item_on_deleted_order_count,
    COALESCE(payment.pay_order_row_count, 0) AS pay_order_row_count,
    COALESCE(payment.active_pay_order_count, 0) AS active_pay_order_count,
    COALESCE(payment.successful_pay_order_count, 0) AS successful_pay_order_count,
    COALESCE(payment.successful_paid_buyer_count, 0) AS successful_paid_buyer_count,
    COALESCE(payment.trade_order_linked_pay_order_count, 0) AS trade_order_linked_pay_order_count,
    COALESCE(payment.active_trade_order_linked_pay_order_count, 0)
        AS active_trade_order_linked_pay_order_count,
    COALESCE(payment.trade_order_unlinked_pay_order_count, 0) AS trade_order_unlinked_pay_order_count,
    COALESCE(payment.duplicated_trade_order_match_count, 0) AS duplicated_trade_order_match_count,
    COALESCE(payment.pay_trade_user_mismatch_count, 0) AS pay_trade_user_mismatch_count,
    COALESCE(payment.pay_trade_pay_amount_mismatch_count, 0) AS pay_trade_pay_amount_mismatch_count,
    COALESCE(payment.pay_trade_refund_amount_mismatch_count, 0)
        AS pay_trade_refund_amount_mismatch_count,
    COALESCE(payment.refund_row_count, 0) AS refund_row_count,
    COALESCE(payment.active_refund_row_count, 0) AS active_refund_row_count,
    COALESCE(payment.pay_order_linked_refund_count, 0) AS pay_order_linked_refund_count,
    COALESCE(payment.trade_order_linked_refund_count, 0) AS trade_order_linked_refund_count,
    COALESCE(payment.pay_order_unlinked_refund_count, 0) AS pay_order_unlinked_refund_count,
    COALESCE(payment.pay_order_user_mismatch_refund_count, 0) AS pay_order_user_mismatch_refund_count,
    COALESCE(payment.refund_exceeds_linked_pay_order_count, 0)
        AS refund_exceeds_linked_pay_order_count,
    COALESCE(payment.observable_refund_cycle_count, 0) AS observable_refund_cycle_count,
    CAST(COALESCE(payment.average_refund_cycle_hours, 0) AS DECIMAL(38,6))
        AS average_refund_cycle_hours,
    CAST(COALESCE(payment.trade_order_linked_pay_order_count, 0) * 100.0
         / NULLIF(payment.pay_order_row_count, 0) AS DECIMAL(38,6))
        AS pay_order_trade_order_link_rate,
    CAST(COALESCE(payment.pay_order_linked_refund_count, 0) * 100.0
         / NULLIF(payment.refund_row_count, 0) AS DECIMAL(38,6))
        AS refund_order_join_rate,
    COALESCE(behavior.member_row_count, 0) AS member_row_count,
    COALESCE(behavior.active_member_row_count, 0) AS active_member_row_count,
    COALESCE(behavior.browse_row_count, 0) AS browse_row_count,
    COALESCE(behavior.active_browse_row_count, 0) AS active_browse_row_count,
    COALESCE(behavior.member_unresolved_browse_count, 0) AS member_unresolved_browse_count,
    COALESCE(behavior.active_member_unresolved_browse_count, 0)
        AS active_member_unresolved_browse_count,
    COALESCE(behavior.source_user_deleted_browse_count, 0) AS source_user_deleted_browse_count,
    COALESCE(behavior.cart_row_count, 0) AS cart_row_count,
    COALESCE(behavior.active_cart_row_count, 0) AS active_cart_row_count,
    COALESCE(behavior.selected_cart_row_count, 0) AS selected_cart_row_count,
    COALESCE(behavior.member_unresolved_cart_count, 0) AS member_unresolved_cart_count,
    COALESCE(behavior.active_member_unresolved_cart_count, 0)
        AS active_member_unresolved_cart_count,
    COALESCE(behavior.invalid_quantity_cart_count, 0) AS invalid_quantity_cart_count,
    CAST(COALESCE(behavior.active_member_unresolved_browse_count, 0) * 100.0
         / NULLIF(behavior.active_browse_row_count, 0) AS DECIMAL(38,6))
        AS browse_unresolved_member_rate,
    CAST(COALESCE(behavior.active_member_unresolved_cart_count, 0) * 100.0
         / NULLIF(behavior.active_cart_row_count, 0) AS DECIMAL(38,6))
        AS cart_unresolved_member_rate,
    orders.unpaid_terminal_order_count
      + orders.refund_exceeds_paid_order_count
      + orders.paid_order_missing_pay_time_count
      + COALESCE(items.active_item_on_deleted_order_count, 0)
      + COALESCE(payment.trade_order_unlinked_pay_order_count, 0)
      + COALESCE(payment.duplicated_trade_order_match_count, 0)
      + COALESCE(payment.pay_trade_user_mismatch_count, 0)
      + COALESCE(payment.pay_trade_pay_amount_mismatch_count, 0)
      + COALESCE(payment.pay_trade_refund_amount_mismatch_count, 0)
      + COALESCE(payment.pay_order_unlinked_refund_count, 0)
      + COALESCE(payment.pay_order_user_mismatch_refund_count, 0)
      + COALESCE(payment.refund_exceeds_linked_pay_order_count, 0)
      + COALESCE(behavior.member_unresolved_browse_count, 0)
      + COALESCE(behavior.source_user_deleted_browse_count, 0)
      + COALESCE(behavior.member_unresolved_cart_count, 0)
      + COALESCE(behavior.invalid_quantity_cart_count, 0) AS quality_flag_count,
    FALSE AS production_combinable,
    'LEGACY_SOURCE_ONLY' AS evidence_scope,
    'LOCAL_YUDAO_TRADE_CURRENT_STATE_NOT_YSHOPPING_PRODUCTION' AS source_scope,
    GREATEST(
        orders.data_freshness_at,
        COALESCE(payment.data_freshness_at, orders.data_freshness_at),
        COALESCE(behavior.data_freshness_at, orders.data_freshness_at)
    ) AS data_freshness_at
FROM order_rollup orders
JOIN buyer_rollup buyers ON buyers.tenant_id = orders.tenant_id
LEFT JOIN item_quality items ON items.tenant_id = orders.tenant_id
LEFT JOIN payment_observability payment ON payment.tenant_id = orders.tenant_id
LEFT JOIN user_behavior_observability behavior ON behavior.tenant_id = orders.tenant_id;
