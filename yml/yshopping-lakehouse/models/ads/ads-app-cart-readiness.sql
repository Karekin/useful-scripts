CREATE OR REPLACE VIEW yshopping_ads.ads_app_cart_readiness AS
SELECT
    tenant_id,
    DATE(latest_cart_changed_at) AS metric_date,
    COUNT(*) AS current_cart_count,
    SUM(CASE WHEN line_count > 0 THEN 1 ELSE 0 END) AS non_empty_cart_count,
    SUM(CASE WHEN selected_line_count > 0 THEN 1 ELSE 0 END) AS selectable_cart_count,
    SUM(line_count) AS declared_line_count,
    SUM(line_row_count) AS materialized_line_count,
    SUM(selected_line_count) AS declared_selected_line_count,
    SUM(selected_item_row_count) AS materialized_selected_line_count,
    SUM(total_quantity) AS total_quantity,
    SUM(selected_quantity) AS selected_quantity,
    MAX(COALESCE(latest_item_at, latest_cart_changed_at)) AS data_freshness_at,
    CASE
        WHEN COUNT(*) = 0 THEN 'EMPTY'
        WHEN SUM(CASE WHEN line_count = line_row_count
                        AND selected_line_count = selected_item_row_count
                        THEN 1 ELSE 0 END) = COUNT(*)
            THEN 'READY'
        ELSE 'PARTIAL'
    END AS readiness_status,
    'APP_CART_CURRENT_STATE_ONLY_NO_EXACT_CHECKOUT_ORDER_LINK' AS model_semantics
FROM yshopping_dws.dws_app_cart_current
GROUP BY tenant_id, DATE(latest_cart_changed_at);
