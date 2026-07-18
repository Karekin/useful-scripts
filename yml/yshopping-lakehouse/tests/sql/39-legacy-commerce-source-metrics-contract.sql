SELECT 'legacy_commerce_source_metric_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id
    FROM yshopping_ads.ads_legacy_commerce_source_metrics
    GROUP BY tenant_id
    HAVING COUNT(*) <> 1
) duplicate_tenant;

SELECT 'legacy_commerce_source_metric_count_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE tenant_id IS NULL
   OR source_order_count < active_order_count
   OR active_order_count < paid_order_count
   OR paid_order_count < paid_buyer_count
   OR paid_buyer_count < repeat_buyer_count
   OR source_order_count < 0 OR active_order_count < 0 OR paid_order_count < 0
   OR paid_buyer_count < 0 OR repeat_buyer_count < 0;

SELECT 'legacy_commerce_source_metric_money_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE gross_paid_amount_yuan < 0
   OR product_paid_amount_yuan < 0
   OR refunded_amount_yuan < 0
   OR ABS(gross_paid_amount_yuan - refunded_amount_yuan - net_paid_amount_yuan) > 0.000001;

SELECT 'legacy_commerce_source_metric_scope_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE production_combinable <> FALSE
   OR evidence_scope <> 'LEGACY_SOURCE_ONLY'
   OR source_scope <> 'LOCAL_YUDAO_TRADE_CURRENT_STATE_NOT_YSHOPPING_PRODUCTION'
   OR data_freshness_at IS NULL;

SELECT 'legacy_commerce_source_metric_quality_rollup_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE quality_flag_count < 0
   OR quality_flag_count < unpaid_terminal_order_count
   OR quality_flag_count < refund_exceeds_paid_order_count
   OR quality_flag_count < paid_order_missing_pay_time_count
   OR quality_flag_count < active_item_on_deleted_order_count;

SELECT 'legacy_commerce_source_metric_payment_join_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE pay_order_row_count < active_pay_order_count
   OR active_pay_order_count < successful_pay_order_count
   OR successful_pay_order_count < successful_paid_buyer_count
   OR pay_order_row_count < trade_order_linked_pay_order_count
   OR pay_order_row_count < active_trade_order_linked_pay_order_count
   OR refund_row_count < active_refund_row_count
   OR refund_row_count < pay_order_linked_refund_count
   OR refund_row_count < trade_order_linked_refund_count
   OR pay_order_row_count < 0
   OR refund_row_count < 0;

SELECT 'legacy_commerce_source_metric_behavior_join_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE member_row_count < active_member_row_count
   OR browse_row_count < member_unresolved_browse_count
   OR active_browse_row_count < active_member_unresolved_browse_count
   OR browse_row_count < source_user_deleted_browse_count
   OR cart_row_count < selected_cart_row_count
   OR cart_row_count < member_unresolved_cart_count
   OR active_cart_row_count < active_member_unresolved_cart_count
   OR browse_row_count < 0
   OR cart_row_count < 0;

SELECT 'legacy_commerce_source_metric_rate_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_commerce_source_metrics
WHERE (pay_order_trade_order_link_rate IS NOT NULL
        AND (pay_order_trade_order_link_rate < 0 OR pay_order_trade_order_link_rate > 100))
   OR (refund_order_join_rate IS NOT NULL
        AND (refund_order_join_rate < 0 OR refund_order_join_rate > 100))
   OR (browse_unresolved_member_rate IS NOT NULL
        AND (browse_unresolved_member_rate < 0 OR browse_unresolved_member_rate > 100))
   OR (cart_unresolved_member_rate IS NOT NULL
        AND (cart_unresolved_member_rate < 0 OR cart_unresolved_member_rate > 100))
   OR average_refund_cycle_hours < 0;
