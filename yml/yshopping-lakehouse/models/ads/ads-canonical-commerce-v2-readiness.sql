CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_commerce_v2_readiness AS
WITH order_items AS (
    SELECT
        item.tenant_id,
        item.order_id,
        COUNT(*) AS item_count,
        COUNT(DISTINCT item.listing_id) AS listing_count,
        COUNT(IF(
            offer.listing_offer_id IS NOT NULL
            AND offer.canonical_sku_id = item.canonical_sku_id
            AND offer.price_minor = item.unit_price_minor
            AND offer.currency_code = 'CNY'
            AND offer.channel_code = item.channel_code
            AND offer.shop_id = item.shop_id,
            1, NULL
        )) AS exact_listing_offer_link_count,
        SUM(item.quantity) AS total_quantity,
        SUM(item.line_amount_minor) AS item_amount_minor
    FROM yshopping_dws.dws_canonical_order_item_current item
    LEFT JOIN yshopping_dwd.dwd_canonical_listing_offer_event offer
      ON offer.tenant_id = item.tenant_id
     AND offer.listing_id = item.listing_id
     AND offer.listing_offer_id = item.listing_offer_id
     AND offer.listing_revision = item.listing_revision
     AND offer.listing_version = item.listing_version
     AND offer.listing_status = 'PUBLISHED'
    WHERE item.schema_version = 2
    GROUP BY item.tenant_id, item.order_id
), listing_links AS (
    SELECT
        item.tenant_id,
        item.order_id,
        COUNT(DISTINCT item.listing_id) AS listing_count,
        COUNT(DISTINCT IF(listing.readiness_status = 'LISTING_PUBLISHED', item.listing_id, NULL)) AS ready_listing_count,
        SUM(listing.listing_event_count) AS listing_event_count,
        SUM(listing.review_event_count) AS listing_review_event_count,
        MAX(listing.data_freshness_at) AS data_freshness_at
    FROM (
        SELECT DISTINCT tenant_id, order_id, listing_id
        FROM yshopping_dws.dws_canonical_order_item_current
        WHERE schema_version = 2
    ) item
    LEFT JOIN yshopping_ads.ads_canonical_listing_readiness listing
      ON listing.tenant_id = item.tenant_id AND listing.listing_id = item.listing_id
    GROUP BY item.tenant_id, item.order_id
), inventory AS (
    SELECT
        order_current.tenant_id,
        order_current.order_id,
        COUNT(*) AS commerce_inventory_event_count
    FROM yshopping_dim.dim_canonical_order_current order_current
    JOIN yshopping_dwd.dwd_canonical_inventory_movement movement
      ON movement.tenant_id = order_current.tenant_id
     AND (
          (movement.business_type = 'TEST_FIXTURE'
           AND movement.business_id = order_current.run_id
           AND movement.movement_type = 'PURCHASE_RECEIPT')
       OR (movement.business_type = 'TRADE_ORDER'
           AND movement.business_id = order_current.order_id
           AND movement.movement_type IN ('RESERVATION', 'SALE_SHIPMENT', 'SALE_RETURN'))
     )
    WHERE order_current.schema_version = 2
    GROUP BY order_current.tenant_id, order_current.order_id
), order_milestones AS (
    SELECT
        tenant_id,
        order_id,
        MAX(IF(current_status = 'SHIPPED', occurred_at, NULL)) AS order_shipped_at,
        MAX(IF(current_status = 'COMPLETED', occurred_at, NULL)) AS order_completed_at
    FROM yshopping_dwd.dwd_canonical_order_status_event
    WHERE schema_version = 2
    GROUP BY tenant_id, order_id
)
SELECT
    order_current.tenant_id,
    order_current.run_id,
    order_current.order_id,
    order_current.order_no,
    order_current.order_event_count,
    COALESCE(payment.payment_event_count, 0) AS payment_event_count,
    COALESCE(listing.listing_event_count, 0) AS listing_event_count,
    COALESCE(listing.listing_review_event_count, 0) AS listing_review_event_count,
    COALESCE(fulfillment.fulfillment_event_count, 0) AS fulfillment_event_count,
    order_current.current_status AS order_status,
    payment.current_status AS payment_status,
    fulfillment.fulfillment_status,
    order_current.payable_amount_minor,
    payment.captured_amount_minor,
    payment.refunded_amount_minor,
    order_current.currency_code,
    payment.currency_code AS payment_currency_code,
    COALESCE(items.item_count, 0) AS item_count,
    COALESCE(items.exact_listing_offer_link_count, 0) AS exact_listing_offer_link_count,
    COALESCE(listing.listing_count, 0) AS listing_count,
    COALESCE(listing.ready_listing_count, 0) AS ready_listing_count,
    COALESCE(fulfillment.item_count, 0) AS fulfillment_item_count,
    COALESCE(fulfillment.valid_order_item_link_count, 0) AS valid_fulfillment_item_link_count,
    COALESCE(inventory.commerce_inventory_event_count, 0) AS commerce_inventory_event_count,
    CASE
        WHEN order_current.current_status = 'RETURNED'
         AND order_current.order_event_count = 7
         AND payment.current_status = 'REFUNDED'
         AND payment.payment_event_count = 2
         AND order_current.payable_amount_minor = payment.captured_amount_minor
         AND payment.captured_amount_minor = payment.refunded_amount_minor
         AND order_current.currency_code = payment.currency_code
         AND COALESCE(items.item_count, 0) > 0
         AND items.item_count = items.exact_listing_offer_link_count
         AND COALESCE(listing.listing_count, 0) > 0
         AND listing.listing_count = listing.ready_listing_count
         AND fulfillment.readiness_status = 'FULFILLMENT_DELIVERED'
         AND fulfillment.order_id = order_current.order_id
         AND fulfillment.fulfillment_id = order_current.fulfillment_id
         AND fulfillment.shipment_id = order_current.shipment_id
         AND fulfillment.item_count = items.item_count
         AND fulfillment.valid_order_item_link_count = items.item_count
         AND order_milestones.order_shipped_at >= CAST(REPLACE(SUBSTR(fulfillment.shipped_at, 1, 19), 'T', ' ') AS DATETIME)
         AND order_milestones.order_completed_at >= CAST(REPLACE(SUBSTR(fulfillment.delivered_at, 1, 19), 'T', ' ') AS DATETIME)
         AND COALESCE(inventory.commerce_inventory_event_count, 0) = 4
         AND COALESCE(items.item_amount_minor, 0) = order_current.product_amount_minor
        THEN 'RECONCILED'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    GREATEST(order_current.recorded_at, payment.recorded_at,
             COALESCE(listing.data_freshness_at, order_current.recorded_at),
             COALESCE(fulfillment.data_freshness_at, order_current.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_order_current order_current
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = order_current.tenant_id AND payment.payment_id = order_current.payment_id
LEFT JOIN order_items items
  ON items.tenant_id = order_current.tenant_id AND items.order_id = order_current.order_id
LEFT JOIN listing_links listing
  ON listing.tenant_id = order_current.tenant_id AND listing.order_id = order_current.order_id
LEFT JOIN yshopping_ads.ads_canonical_fulfillment_readiness fulfillment
  ON fulfillment.tenant_id = order_current.tenant_id AND fulfillment.fulfillment_id = order_current.fulfillment_id
LEFT JOIN inventory
  ON inventory.tenant_id = order_current.tenant_id AND inventory.order_id = order_current.order_id
LEFT JOIN order_milestones
  ON order_milestones.tenant_id = order_current.tenant_id AND order_milestones.order_id = order_current.order_id
WHERE order_current.schema_version = 2;
