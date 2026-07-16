CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_order_item_benefit_current AS
WITH funding_by_allocation AS (
    SELECT tenant_id, order_id, benefit_application_id, benefit_allocation_id,
           COUNT(*) AS funding_count,
           SUM(amount_minor) AS funding_amount_minor,
           COUNT(DISTINCT currency_code) AS funding_currency_count
    FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
    GROUP BY tenant_id, order_id, benefit_application_id, benefit_allocation_id
), benefit_by_item AS (
    SELECT allocation.tenant_id, allocation.order_id, allocation.order_item_id,
           MIN(allocation.line_key) AS line_key,
           COUNT(DISTINCT allocation.benefit_application_id) AS benefit_application_count,
           COUNT(*) AS benefit_allocation_count,
           SUM(allocation.amount_minor) AS discount_amount_minor,
           SUM(COALESCE(funding.funding_amount_minor, 0)) AS funding_amount_minor,
           SUM(CASE
                 WHEN funding.funding_count IS NULL
                   OR funding.funding_amount_minor <> allocation.amount_minor
                   OR funding.funding_currency_count <> 1
                 THEN 1 ELSE 0
               END) AS funding_mismatch_count,
           MAX(allocation.recorded_at) AS benefit_freshness_at
    FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
    LEFT JOIN funding_by_allocation funding
      ON funding.tenant_id = allocation.tenant_id
     AND funding.order_id = allocation.order_id
     AND funding.benefit_application_id = allocation.benefit_application_id
     AND funding.benefit_allocation_id = allocation.benefit_allocation_id
    GROUP BY allocation.tenant_id, allocation.order_id, allocation.order_item_id
)
SELECT
    item.tenant_id,
    item.run_id,
    item.order_id,
    item.order_no,
    item.order_item_id,
    benefit.line_key,
    item.canonical_sku_id,
    item.quantity,
    item.unit_price_minor,
    item.line_amount_minor AS gross_amount_minor,
    COALESCE(benefit.discount_amount_minor, 0) AS discount_amount_minor,
    item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0) AS net_amount_minor,
    COALESCE(benefit.funding_amount_minor, 0) AS funding_amount_minor,
    COALESCE(benefit.benefit_application_count, 0) AS benefit_application_count,
    COALESCE(benefit.benefit_allocation_count, 0) AS benefit_allocation_count,
    COALESCE(benefit.funding_mismatch_count, 0) AS funding_mismatch_count,
    item.currency_code,
    item.order_status,
    item.item_freshness_at,
    benefit.benefit_freshness_at
FROM yshopping_dws.dws_canonical_order_item_current item
LEFT JOIN benefit_by_item benefit
  ON benefit.tenant_id = item.tenant_id
 AND benefit.order_id = item.order_id
 AND benefit.order_item_id = item.order_item_id
WHERE EXISTS (
    SELECT 1
    FROM yshopping_dim.dim_canonical_order_benefit_application_current application
    WHERE application.tenant_id = item.tenant_id
      AND application.order_id = item.order_id
);
