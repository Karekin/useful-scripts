CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_commerce_readiness AS
SELECT
    order_current.tenant_id,
    order_current.run_id,
    order_current.order_id,
    order_current.order_no,
    order_current.order_event_count,
    COALESCE(payment.payment_event_count, 0) AS payment_event_count,
    order_current.current_status AS order_status,
    payment.current_status AS payment_status,
    order_current.payable_amount_minor,
    payment.captured_amount_minor,
    payment.refunded_amount_minor,
    order_current.currency_code,
    payment.currency_code AS payment_currency_code,
    COALESCE(items.item_count, 0) AS item_count,
    COALESCE(items.total_quantity, 0) AS total_quantity,
    COALESCE(items.item_amount_minor, 0) AS item_amount_minor,
    COALESCE(inventory.commerce_inventory_event_count, 0) AS commerce_inventory_event_count,
    CASE
        WHEN order_current.current_status = 'RETURNED'
         AND payment.current_status = 'REFUNDED'
         AND order_current.payable_amount_minor = payment.captured_amount_minor
         AND payment.captured_amount_minor = payment.refunded_amount_minor
         AND order_current.currency_code = payment.currency_code
         AND COALESCE(inventory.commerce_inventory_event_count, 0) = 3
         AND COALESCE(items.item_amount_minor, 0) = order_current.product_amount_minor
        THEN 'RECONCILED'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    GREATEST(order_current.recorded_at, payment.recorded_at) AS data_freshness_at
FROM yshopping_dim.dim_canonical_order_current order_current
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = order_current.tenant_id AND payment.payment_id = order_current.payment_id
LEFT JOIN (
    SELECT tenant_id, order_id, COUNT(*) AS item_count, SUM(quantity) AS total_quantity,
           SUM(line_amount_minor) AS item_amount_minor
    FROM yshopping_dws.dws_canonical_order_item_current
    GROUP BY tenant_id, order_id
) items ON items.tenant_id = order_current.tenant_id AND items.order_id = order_current.order_id
LEFT JOIN (
    SELECT tenant_id, business_id AS order_id, COUNT(*) AS commerce_inventory_event_count
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE business_type = 'TRADE_ORDER'
      AND movement_type IN ('RESERVATION', 'SALE_SHIPMENT', 'SALE_RETURN')
    GROUP BY tenant_id, business_id
) inventory ON inventory.tenant_id = order_current.tenant_id AND inventory.order_id = order_current.order_id;
