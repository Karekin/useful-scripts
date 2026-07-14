CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_fulfillment_item_current AS
SELECT
    item.tenant_id,
    item.run_id,
    item.fulfillment_id,
    item.fulfillment_no,
    item.order_id,
    item.order_no,
    item.fulfillment_item_id,
    item.order_item_id,
    item.canonical_sku_id,
    item.quantity,
    item.reservation_id,
    fulfillment.current_status AS fulfillment_status,
    fulfillment.shipment_id,
    fulfillment.warehouse_id,
    order_item.schema_version AS order_schema_version,
    order_item.listing_id,
    order_item.listing_offer_id,
    order_item.listing_revision,
    order_item.listing_version,
    CASE
        WHEN order_item.order_item_id IS NOT NULL
         AND order_item.canonical_sku_id = item.canonical_sku_id
         AND order_item.quantity = item.quantity
         AND order_item.reservation_id = item.reservation_id
        THEN TRUE ELSE FALSE
    END AS order_item_link_valid,
    item.recorded_at AS item_freshness_at,
    fulfillment.recorded_at AS fulfillment_freshness_at,
    order_item.item_freshness_at AS order_item_freshness_at
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, fulfillment_id, fulfillment_item_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_fulfillment_item_event event
) item
JOIN yshopping_dim.dim_canonical_fulfillment_current fulfillment
  ON fulfillment.tenant_id = item.tenant_id AND fulfillment.fulfillment_id = item.fulfillment_id
LEFT JOIN yshopping_dws.dws_canonical_order_item_current order_item
  ON order_item.tenant_id = item.tenant_id
 AND order_item.order_id = item.order_id
 AND order_item.order_item_id = item.order_item_id
WHERE item.row_num = 1;
