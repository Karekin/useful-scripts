CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_fulfillment_readiness AS
SELECT
    fulfillment.tenant_id,
    fulfillment.run_id,
    fulfillment.fulfillment_id,
    fulfillment.fulfillment_no,
    fulfillment.order_id,
    fulfillment.shipment_id,
    fulfillment.fulfillment_status,
    fulfillment.fulfillment_event_count,
    COALESCE(items.item_count, 0) AS item_count,
    COALESCE(items.valid_order_item_link_count, 0) AS valid_order_item_link_count,
    fulfillment.carrier_code,
    fulfillment.waybill_no,
    fulfillment.shipped_at,
    fulfillment.in_transit_at,
    fulfillment.delivered_at,
    CASE
        WHEN fulfillment.fulfillment_status = 'DELIVERED'
         AND fulfillment.fulfillment_event_count = 4
         AND fulfillment.shipment_id IS NOT NULL
         AND fulfillment.carrier_code IS NOT NULL
         AND fulfillment.waybill_no IS NOT NULL
         AND fulfillment.milestone_time_valid = TRUE
         AND COALESCE(items.item_count, 0) > 0
         AND items.item_count = items.valid_order_item_link_count
        THEN 'FULFILLMENT_DELIVERED'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    GREATEST(fulfillment.data_freshness_at,
             COALESCE(items.item_freshness_at, fulfillment.data_freshness_at)) AS data_freshness_at
FROM yshopping_dws.dws_canonical_fulfillment_milestone_current fulfillment
LEFT JOIN (
    SELECT tenant_id, fulfillment_id,
           COUNT(*) AS item_count,
           COUNT(IF(order_item_link_valid = TRUE, 1, NULL)) AS valid_order_item_link_count,
           MAX(item_freshness_at) AS item_freshness_at
    FROM yshopping_dws.dws_canonical_fulfillment_item_current
    GROUP BY tenant_id, fulfillment_id
) items ON items.tenant_id = fulfillment.tenant_id
       AND items.fulfillment_id = fulfillment.fulfillment_id;
