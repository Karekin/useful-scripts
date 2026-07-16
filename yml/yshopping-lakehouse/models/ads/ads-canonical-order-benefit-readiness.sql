CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_order_benefit_readiness AS
WITH funding_by_allocation AS (
    SELECT tenant_id, order_id, benefit_application_id, benefit_allocation_id,
           COUNT(*) AS funding_count,
           SUM(amount_minor) AS funding_amount_minor,
           COUNT(DISTINCT currency_code) AS funding_currency_count
    FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
    GROUP BY tenant_id, order_id, benefit_application_id, benefit_allocation_id
), allocation_by_application AS (
    SELECT allocation.tenant_id, allocation.order_id, allocation.benefit_application_id,
           COUNT(*) AS allocation_count,
           SUM(allocation.amount_minor) AS allocation_amount_minor,
           SUM(COALESCE(funding.funding_amount_minor, 0)) AS funding_amount_minor,
           SUM(CASE
                 WHEN funding.funding_count IS NULL
                   OR funding.funding_amount_minor <> allocation.amount_minor
                   OR funding.funding_currency_count <> 1
                 THEN 1 ELSE 0
               END) AS allocation_funding_mismatch_count
    FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
    LEFT JOIN funding_by_allocation funding
      ON funding.tenant_id = allocation.tenant_id
     AND funding.order_id = allocation.order_id
     AND funding.benefit_application_id = allocation.benefit_application_id
     AND funding.benefit_allocation_id = allocation.benefit_allocation_id
    GROUP BY allocation.tenant_id, allocation.order_id, allocation.benefit_application_id
), benefit_by_order AS (
    SELECT application.tenant_id, application.order_id, MIN(application.run_id) AS run_id,
           MIN(application.order_no) AS order_no,
           COUNT(*) AS application_count,
           COUNT(DISTINCT application.run_id) AS run_id_variant_count,
           COUNT(DISTINCT application.order_no) AS order_no_variant_count,
           SUM(application.amount_minor) AS application_amount_minor,
           SUM(COALESCE(allocation.allocation_amount_minor, 0)) AS allocation_amount_minor,
           SUM(COALESCE(allocation.funding_amount_minor, 0)) AS funding_amount_minor,
           SUM(COALESCE(allocation.allocation_count, 0)) AS allocation_count,
           SUM(CASE
                 WHEN allocation.allocation_count IS NULL
                   OR allocation.allocation_amount_minor <> application.amount_minor
                 THEN 1 ELSE 0
               END) AS application_allocation_mismatch_count,
           SUM(COALESCE(allocation.allocation_funding_mismatch_count, 0))
               AS allocation_funding_mismatch_count,
           SUM(CASE WHEN application.application_event_count <> 1 THEN 1 ELSE 0 END)
               AS mutable_application_count,
           COUNT(DISTINCT application.currency_code) AS application_currency_count,
           MAX(application.recorded_at) AS benefit_freshness_at
    FROM yshopping_dim.dim_canonical_order_benefit_application_current application
    LEFT JOIN allocation_by_application allocation
      ON allocation.tenant_id = application.tenant_id
     AND allocation.order_id = application.order_id
     AND allocation.benefit_application_id = application.benefit_application_id
    GROUP BY application.tenant_id, application.order_id
), item_by_order AS (
    SELECT tenant_id, order_id, COUNT(*) AS item_count,
           SUM(gross_amount_minor) AS gross_amount_minor,
           SUM(discount_amount_minor) AS item_discount_amount_minor,
           SUM(net_amount_minor) AS net_amount_minor,
           SUM(funding_mismatch_count) AS item_funding_mismatch_count,
           SUM(CASE
                 WHEN discount_amount_minor < 0 OR net_amount_minor < 0
                   OR gross_amount_minor <> discount_amount_minor + net_amount_minor
                 THEN 1 ELSE 0
               END) AS item_money_mismatch_count,
           MAX(COALESCE(benefit_freshness_at, item_freshness_at)) AS item_freshness_at
    FROM yshopping_dws.dws_canonical_order_item_benefit_current
    GROUP BY tenant_id, order_id
)
SELECT
    benefit.tenant_id,
    benefit.run_id,
    benefit.order_id,
    benefit.order_no,
    benefit.application_count,
    benefit.run_id_variant_count,
    benefit.order_no_variant_count,
    benefit.allocation_count,
    COALESCE(item.item_count, 0) AS item_count,
    order_current.discount_amount_minor AS header_discount_amount_minor,
    benefit.application_amount_minor,
    benefit.allocation_amount_minor,
    benefit.funding_amount_minor,
    COALESCE(item.gross_amount_minor, 0) AS gross_amount_minor,
    COALESCE(item.item_discount_amount_minor, 0) AS item_discount_amount_minor,
    COALESCE(item.net_amount_minor, 0) AS net_amount_minor,
    benefit.application_allocation_mismatch_count,
    benefit.allocation_funding_mismatch_count,
    benefit.mutable_application_count,
    COALESCE(item.item_funding_mismatch_count, 0) AS item_funding_mismatch_count,
    COALESCE(item.item_money_mismatch_count, 0) AS item_money_mismatch_count,
    CASE
      WHEN order_current.order_id IS NULL THEN 'ORDER_MISSING'
      WHEN benefit.application_count <= 0 OR benefit.allocation_count <= 0 OR COALESCE(item.item_count, 0) <= 0
        THEN 'EVIDENCE_MISSING'
      WHEN benefit.run_id_variant_count <> 1 OR benefit.order_no_variant_count <> 1
        OR order_current.run_id <> benefit.run_id OR order_current.order_no <> benefit.order_no
        THEN 'ORDER_IDENTITY_MISMATCH'
      WHEN benefit.application_currency_count <> 1 OR order_current.currency_code <> 'CNY'
        THEN 'CURRENCY_MISMATCH'
      WHEN order_current.discount_amount_minor <> benefit.application_amount_minor
        OR benefit.application_amount_minor <> benefit.allocation_amount_minor
        OR benefit.allocation_amount_minor <> benefit.funding_amount_minor
        OR benefit.allocation_amount_minor <> COALESCE(item.item_discount_amount_minor, 0)
        OR COALESCE(item.gross_amount_minor, 0)
             <> COALESCE(item.item_discount_amount_minor, 0) + COALESCE(item.net_amount_minor, 0)
        OR benefit.application_allocation_mismatch_count <> 0
        OR benefit.allocation_funding_mismatch_count <> 0
        OR benefit.mutable_application_count <> 0
        OR COALESCE(item.item_funding_mismatch_count, 0) <> 0
        OR COALESCE(item.item_money_mismatch_count, 0) <> 0
        THEN 'INCONSISTENT'
      ELSE 'RECONCILED'
    END AS readiness_status,
    GREATEST(benefit.benefit_freshness_at, item.item_freshness_at, order_current.recorded_at)
        AS data_freshness_at,
    'NONEMPTY_IMMUTABLE_ORDER_BENEFIT_V1' AS evidence_semantics
FROM benefit_by_order benefit
LEFT JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = benefit.tenant_id AND order_current.order_id = benefit.order_id
LEFT JOIN item_by_order item
  ON item.tenant_id = benefit.tenant_id AND item.order_id = benefit.order_id;
