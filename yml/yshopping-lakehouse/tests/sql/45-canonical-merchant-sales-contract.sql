SELECT 'merchant_sales_negative_net_amount' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
WHERE merchant_net_sales_amount_minor < 0;

SELECT 'merchant_sales_formula_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
WHERE merchant_net_sales_amount_minor
   <> merchant_booked_sales_amount_minor
      - merchant_refund_deduction_amount_minor
      - merchant_cancellation_deduction_amount_minor;

SELECT 'merchant_sales_frozen_offer_mapping_missing', COUNT(*)
FROM yshopping_dws.dws_canonical_order_item_profitability_current item
LEFT JOIN yshopping_dws.dws_canonical_merchant_order_item_sales_current merchant
  ON merchant.tenant_id = item.tenant_id
 AND merchant.order_item_id = item.order_item_id
WHERE item.listing_offer_id IS NOT NULL
  AND merchant.order_item_id IS NULL;

SELECT 'merchant_sales_frozen_offer_mapping_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current merchant
JOIN yshopping_dws.dws_canonical_listing_offer_current offer
  ON offer.tenant_id = merchant.tenant_id
 AND offer.listing_offer_id = merchant.listing_offer_id
WHERE offer.listing_id <> merchant.listing_id
   OR offer.canonical_sku_id <> merchant.canonical_sku_id
   OR offer.merchant_id <> merchant.merchant_id
   OR offer.shop_id <> merchant.shop_id
   OR offer.channel_code <> merchant.channel_code;

SELECT 'merchant_sales_cancellation_residual_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
WHERE (merchant_cancellation_saga_id IS NULL AND merchant_cancellation_deduction_amount_minor <> 0)
   OR (merchant_cancellation_saga_id IS NOT NULL
       AND merchant_cancellation_deduction_amount_minor
           <> GREATEST(merchant_booked_sales_amount_minor - merchant_refund_deduction_amount_minor, 0));

SELECT 'merchant_sales_ads_rollup_mismatch', COUNT(*)
FROM yshopping_ads.ads_canonical_merchant_sales_metrics metric
JOIN (
    SELECT tenant_id, merchant_id,
           SUM(merchant_net_sales_amount_minor) AS expected_minor,
           COUNT(*) AS expected_rows
    FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
    GROUP BY tenant_id, merchant_id
) expected
  ON expected.tenant_id = metric.tenant_id
 AND expected.merchant_id = metric.merchant_id
WHERE metric.metric_id <> 'merchant.net_sales_yuan'
   OR metric.numerator <> CAST(expected.expected_minor AS DECIMAL(38,6))
   OR metric.metric_value <> CAST(expected.expected_minor / 100.0 AS DECIMAL(38,6))
   OR metric.source_row_count <> expected.expected_rows;
