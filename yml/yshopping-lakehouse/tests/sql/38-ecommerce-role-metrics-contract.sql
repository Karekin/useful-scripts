-- Do not place an unfiltered global aggregation above this wide UNION ALL view.
-- StarRocks expands every metric branch and can exhaust the memo planner before it
-- produces an executable plan. Row ownership, required fields, units, numeric ranges,
-- and denominators are checked by the bounded theme contracts (39-51) and by the
-- versioned 76-KPI snapshot contract. This file retains only cross-metric
-- reconciliations and pushes an exact metric-id predicate into the wide view so the
-- optimizer can prune unrelated branches.

SELECT 'ecommerce_role_metric_inventory_complement_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT
        offer.tenant_id,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                            THEN offer.listing_offer_id END) AS observable_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                             AND inventory.available_quantity > 0
                            THEN offer.listing_offer_id END) AS in_stock_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                             AND inventory.available_quantity = 0
                            THEN offer.listing_offer_id END) AS out_of_stock_offer_count
    FROM yshopping_dws.dws_canonical_listing_offer_current offer
    LEFT JOIN (
        SELECT tenant_id, canonical_sku_id,
               SUM(CASE WHEN health_status NOT IN ('INVALID', 'NON_SELLABLE')
                        THEN available_quantity ELSE 0 END) AS available_quantity
        FROM yshopping_ads.ads_canonical_inventory_health
        GROUP BY tenant_id, canonical_sku_id
    ) inventory
      ON inventory.tenant_id = offer.tenant_id
     AND inventory.canonical_sku_id = offer.canonical_sku_id
    WHERE offer.enabled = TRUE
      AND offer.listing_status = 'PUBLISHED'
      AND offer.catalog_sku_status = 'ACTIVE'
      AND offer.merchant_shop_active = TRUE
    GROUP BY offer.tenant_id
) inventory
WHERE observable_offer_count <> in_stock_offer_count + out_of_stock_offer_count;

SELECT 'ecommerce_role_metric_aov_reconciliation_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT
        orders.tenant_id,
        SUM(payment.captured_amount_minor) / 100.0 AS gmv_yuan,
        COUNT(DISTINCT orders.order_id) AS order_count,
        SUM(payment.captured_amount_minor) /
            NULLIF(COUNT(DISTINCT orders.order_id), 0) / 100.0 AS aov_yuan
    FROM yshopping_dim.dim_canonical_order_current orders
    JOIN yshopping_dim.dim_canonical_payment_current payment
      ON payment.tenant_id = orders.tenant_id
     AND payment.payment_id = orders.payment_id
    WHERE payment.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND payment.captured_amount_minor > 0
    GROUP BY orders.tenant_id
) commerce
WHERE gmv_yuan IS NOT NULL AND order_count > 0 AND aov_yuan IS NOT NULL
  AND ABS(gmv_yuan / order_count - aov_yuan) > 0.000001;

SELECT 'ecommerce_role_metric_merchant_net_sales_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT
        metric.tenant_id,
        metric.metric_value,
        merchant_sales.net_sales_minor
    FROM yshopping_ads.ads_ecommerce_merchant_role_metrics metric
    JOIN (
        SELECT
            tenant_id,
            SUM(merchant_net_sales_amount_minor) AS net_sales_minor
        FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
        GROUP BY tenant_id
    ) merchant_sales ON merchant_sales.tenant_id = metric.tenant_id
    WHERE metric.metric_id = 'merchant.net_sales_yuan'
) merchant_net_sales
WHERE ABS(metric_value - net_sales_minor / 100.0) > 0.000001;
