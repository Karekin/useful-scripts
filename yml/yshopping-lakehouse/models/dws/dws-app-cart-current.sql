CREATE OR REPLACE VIEW yshopping_dws.dws_app_cart_current AS
WITH current_items AS (
    SELECT
        item.tenant_id,
        item.cart_id,
        item.cart_version,
        COUNT(*) AS line_row_count,
        COUNT(DISTINCT CASE WHEN item.selected THEN item.line_id END) AS selected_item_row_count,
        SUM(item.quantity) AS total_quantity,
        SUM(CASE WHEN item.selected THEN item.quantity ELSE 0 END) AS selected_quantity,
        MAX(item.occurred_at) AS latest_item_at
    FROM yshopping_dwd.dwd_app_cart_item_event item
    JOIN yshopping_dim.dim_app_cart_current cart
      ON cart.tenant_id = item.tenant_id
     AND cart.cart_id = item.cart_id
     AND cart.cart_version = item.cart_version
    GROUP BY item.tenant_id, item.cart_id, item.cart_version
)
SELECT
    cart.tenant_id,
    cart.cart_id,
    cart.cart_version,
    cart.buyer_principal_id,
    cart.line_count,
    cart.selected_line_count,
    COALESCE(items.line_row_count, 0) AS line_row_count,
    COALESCE(items.selected_item_row_count, 0) AS selected_item_row_count,
    items.total_quantity,
    items.selected_quantity,
    cart.operation AS latest_operation,
    cart.occurred_at AS latest_cart_changed_at,
    items.latest_item_at,
    'APP_CART_CURRENT_STATE_ONLY_NO_EXACT_CHECKOUT_ORDER_LINK' AS model_semantics
FROM yshopping_dim.dim_app_cart_current cart
LEFT JOIN current_items items
  ON items.tenant_id = cart.tenant_id
 AND items.cart_id = cart.cart_id
 AND items.cart_version = cart.cart_version;
