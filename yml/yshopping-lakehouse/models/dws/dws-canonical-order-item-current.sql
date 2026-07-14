CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_order_item_current AS
SELECT
    item.tenant_id,
    item.run_id,
    item.order_id,
    item.order_no,
    item.order_item_id,
    item.schema_version,
    item.canonical_sku_id,
    item.quantity,
    item.unit_price_minor,
    item.line_amount_minor,
    item.reservation_id,
    item.listing_id,
    item.listing_offer_id,
    item.listing_revision,
    item.listing_version,
    item.channel_code,
    item.shop_id,
    order_current.buyer_id,
    order_current.current_status AS order_status,
    order_current.payable_amount_minor,
    order_current.currency_code,
    order_current.payment_id,
    order_current.fulfillment_id,
    order_current.shipment_id,
    payment.current_status AS payment_status,
    payment.captured_amount_minor,
    payment.refunded_amount_minor,
    item.recorded_at AS item_freshness_at,
    order_current.recorded_at AS order_freshness_at,
    payment.recorded_at AS payment_freshness_at
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, order_id, order_item_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_order_item_event event
) item
JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = item.tenant_id AND order_current.order_id = item.order_id
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = order_current.tenant_id AND payment.payment_id = order_current.payment_id
WHERE item.row_num = 1;
