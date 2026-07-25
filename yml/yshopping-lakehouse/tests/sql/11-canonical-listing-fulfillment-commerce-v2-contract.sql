SELECT 'canonical_listing_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, listing_id
  FROM yshopping_dwd.dwd_canonical_listing_status_event
  GROUP BY tenant_id, listing_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_listing_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, listing_id ORDER BY aggregate_version) AS expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_listing_status_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_listing_review_stage_unique', COUNT(*)
FROM (
  SELECT tenant_id, listing_id, revision, review_stage
  FROM yshopping_dwd.dwd_canonical_listing_review_event
  GROUP BY tenant_id, listing_id, revision, review_stage
  HAVING COUNT(*) > 1
) duplicate_stage
UNION ALL
SELECT 'canonical_listing_offer_revision_match', COUNT(*)
FROM yshopping_dwd.dwd_canonical_listing_offer_event
WHERE listing_revision <> offer_revision OR currency_code <> 'CNY' OR price_minor < 0
UNION ALL
SELECT 'canonical_listing_offer_catalog_authority', COUNT(*)
FROM yshopping_dim.dim_canonical_listing_offer_current offer
LEFT JOIN yshopping_dim.dim_canonical_catalog_sku_current sku
  ON sku.tenant_id = offer.tenant_id AND sku.canonical_sku_id = offer.canonical_sku_id
WHERE sku.canonical_sku_id IS NULL
   OR sku.canonical_spu_id <> offer.canonical_spu_id
UNION ALL
SELECT 'canonical_order_v2_listing_fields_required', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_item_event
WHERE schema_version = 2
  AND (listing_id IS NULL OR listing_id = ''
    OR listing_offer_id IS NULL OR listing_offer_id = ''
    OR listing_revision IS NULL OR listing_revision < 1
    OR listing_version IS NULL OR listing_version < 1
    OR channel_code IS NULL OR channel_code = ''
    OR shop_id IS NULL OR shop_id = '')
UNION ALL
SELECT 'canonical_order_v2_exact_published_offer_link', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_item_event item
LEFT JOIN yshopping_dwd.dwd_canonical_listing_offer_event offer
  ON offer.tenant_id = item.tenant_id
 AND offer.listing_id = item.listing_id
 AND offer.listing_offer_id = item.listing_offer_id
 AND offer.listing_revision = item.listing_revision
 AND offer.listing_version = item.listing_version
 AND offer.listing_status = 'PUBLISHED'
WHERE item.schema_version = 2
  AND (offer.listing_offer_id IS NULL
    OR offer.canonical_sku_id <> item.canonical_sku_id
    OR offer.price_minor <> item.unit_price_minor
    OR offer.currency_code <> 'CNY'
    OR offer.channel_code <> item.channel_code
    OR offer.shop_id <> item.shop_id)
UNION ALL
SELECT 'canonical_fulfillment_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, fulfillment_id
  FROM yshopping_dwd.dwd_canonical_fulfillment_status_event
  GROUP BY tenant_id, fulfillment_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_fulfillment_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, fulfillment_id ORDER BY aggregate_version) AS expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_fulfillment_status_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_fulfillment_exact_order_item_link', COUNT(*)
FROM yshopping_dws.dws_canonical_fulfillment_item_current
WHERE order_schema_version NOT IN (2, 3, 4) OR order_item_link_valid <> TRUE
UNION ALL
SELECT 'canonical_fulfillment_exact_inventory_reservation_link', COUNT(*)
FROM yshopping_dws.dws_canonical_fulfillment_item_current item
LEFT JOIN yshopping_dwd.dwd_canonical_inventory_movement movement
  ON movement.tenant_id = item.tenant_id
 AND movement.business_type = 'TRADE_ORDER'
 AND movement.business_id = item.order_id
 AND movement.business_item_id = item.order_item_id
 AND movement.reservation_id = item.reservation_id
 AND movement.movement_type = 'SALE_SHIPMENT'
WHERE item.fulfillment_status IN ('SHIPPED', 'IN_TRANSIT', 'DELIVERED')
  AND movement.event_id IS NULL
UNION ALL
SELECT 'canonical_fulfillment_shipment_timing', COUNT(*)
FROM yshopping_dws.dws_canonical_fulfillment_milestone_current
WHERE (fulfillment_status IN ('SHIPPED', 'IN_TRANSIT', 'DELIVERED')
       AND (shipment_id IS NULL OR carrier_code IS NULL OR waybill_no IS NULL OR shipped_at IS NULL))
   OR (fulfillment_status IN ('IN_TRANSIT', 'DELIVERED') AND in_transit_at IS NULL)
   OR (fulfillment_status = 'DELIVERED' AND (delivered_at IS NULL OR milestone_time_valid <> TRUE))
UNION ALL
SELECT 'canonical_v2_replay_event_uniqueness', COUNT(*)
FROM (
  SELECT tenant_id, event_type, idempotency_key
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN ('listing.status.changed', 'listing.review.decided', 'fulfillment.status.changed')
     OR (event_type = 'order.status.changed' AND schema_version IN (2, 4))
  GROUP BY tenant_id, event_type, idempotency_key
  HAVING COUNT(*) > 1
) duplicate_replay
UNION ALL
SELECT 'canonical_v2_reserved_cancellation_shape', COUNT(*)
FROM yshopping_dim.dim_canonical_order_current cancelled
WHERE cancelled.schema_version = 2
  AND cancelled.current_status = 'CANCELLED'
  AND ((cancelled.cancellation_saga_id IS NULL
        AND (cancelled.previous_status <> 'INVENTORY_RESERVED' OR cancelled.order_event_count <> 3))
    OR (cancelled.cancellation_saga_id IS NOT NULL
        AND (cancelled.previous_status <> 'CANCELLATION_PENDING'
          OR cancelled.pre_cancellation_status <> 'INVENTORY_RESERVED'
          OR cancelled.order_event_count <> 4))
    OR
       (cancelled.payment_id IS NOT NULL
        OR cancelled.fulfillment_id IS NOT NULL
        OR cancelled.shipment_id IS NOT NULL))
UNION ALL
SELECT 'canonical_v2_reserved_cancellation_release_link', COUNT(*)
FROM yshopping_dws.dws_canonical_order_item_current item
JOIN yshopping_dim.dim_canonical_order_current cancelled
  ON cancelled.tenant_id = item.tenant_id AND cancelled.order_id = item.order_id
LEFT JOIN yshopping_dwd.dwd_canonical_inventory_movement released
  ON released.tenant_id = item.tenant_id
 AND released.business_type = 'TRADE_ORDER'
 AND released.business_id = item.order_id
 AND released.business_item_id = item.order_item_id
 AND released.reservation_id = item.reservation_id
 AND released.movement_type = 'RESERVATION_RELEASE'
WHERE cancelled.schema_version = 2
  AND cancelled.current_status = 'CANCELLED'
  AND released.event_id IS NULL
UNION ALL
SELECT 'canonical_v2_cancelled_order_has_no_money_or_fulfillment', COUNT(*)
FROM yshopping_dim.dim_canonical_order_current cancelled
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = cancelled.tenant_id AND payment.order_id = cancelled.order_id
LEFT JOIN yshopping_dim.dim_canonical_fulfillment_current fulfillment
  ON fulfillment.tenant_id = cancelled.tenant_id AND fulfillment.order_id = cancelled.order_id
WHERE cancelled.schema_version = 2
  AND cancelled.current_status = 'CANCELLED'
  AND (payment.payment_id IS NOT NULL OR fulfillment.fulfillment_id IS NOT NULL)
UNION ALL
SELECT 'canonical_commerce_v2_terminal_reconciliation', COUNT(*)
FROM yshopping_ads.ads_canonical_commerce_v2_readiness commerce
WHERE commerce.order_status = 'RETURNED' AND commerce.readiness_status <> 'RECONCILED'
  -- Keep legacy direct-return regression coverage without misclassifying the
  -- independent AfterSale authority, whose readiness proves the reverse flow.
  AND NOT EXISTS (
    SELECT 1
    FROM yshopping_ads.ads_canonical_after_sale_readiness aftersale
    WHERE aftersale.tenant_id = commerce.tenant_id
      AND aftersale.order_id = commerce.order_id
      AND aftersale.readiness_status = 'RECONCILED'
  );
