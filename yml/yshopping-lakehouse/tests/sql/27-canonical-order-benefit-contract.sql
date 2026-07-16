SELECT 'order_benefit_envelope_identity_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_order_benefit_application_event
WHERE source_system <> 'cloudmold-order'
   OR aggregate_type <> 'order'
   OR envelope_order_id <> order_id
   OR aggregate_version <> 1
   OR event_sequence < 2
UNION ALL
SELECT 'order_benefit_status_sequence_anchor_missing', COUNT(*)
FROM yshopping_dim.dim_canonical_order_benefit_application_current application
LEFT JOIN yshopping_dwd.dwd_domain_event status_event
  ON status_event.tenant_id = application.tenant_id
 AND status_event.aggregate_type = 'order'
 AND status_event.aggregate_id = application.order_id
 AND status_event.aggregate_version = 1
 AND status_event.event_sequence = 1
 AND status_event.event_type = 'order.status.changed'
 AND status_event.source_system = 'cloudmold-order'
WHERE status_event.event_id IS NULL
UNION ALL
SELECT 'order_benefit_event_sequence_not_contiguous', COUNT(*)
FROM (
  SELECT tenant_id, order_id
  FROM yshopping_dwd.dwd_canonical_order_benefit_application_event
  GROUP BY tenant_id, order_id
  HAVING MIN(event_sequence) <> 2
      OR MAX(event_sequence) <> COUNT(*) + 1
      OR COUNT(DISTINCT event_sequence) <> COUNT(*)
) invalid
UNION ALL
SELECT 'order_benefit_application_not_immutable', COUNT(*)
FROM (
  SELECT tenant_id, order_id, benefit_application_id
  FROM yshopping_dwd.dwd_canonical_order_benefit_application_event
  GROUP BY tenant_id, order_id, benefit_application_id
  HAVING COUNT(*) <> 1
) invalid
UNION ALL
SELECT 'order_benefit_application_business_key_duplicate', COUNT(*)
FROM (
  SELECT tenant_id, order_id, application_key
  FROM yshopping_dim.dim_canonical_order_benefit_application_current
  GROUP BY tenant_id, order_id, application_key
  HAVING COUNT(*) <> 1
) invalid
UNION ALL
SELECT 'order_benefit_allocation_business_key_duplicate', COUNT(*)
FROM (
  SELECT tenant_id, order_id, benefit_application_id
  FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event
  GROUP BY tenant_id, order_id, benefit_application_id
  HAVING COUNT(*) <> COUNT(DISTINCT benefit_allocation_id)
      OR COUNT(*) <> COUNT(DISTINCT allocation_key)
) invalid
UNION ALL
SELECT 'order_benefit_funding_business_key_duplicate', COUNT(*)
FROM (
  SELECT tenant_id, order_id, benefit_application_id, benefit_allocation_id
  FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
  GROUP BY tenant_id, order_id, benefit_application_id, benefit_allocation_id
  HAVING COUNT(*) <> COUNT(DISTINCT benefit_funding_id)
      OR COUNT(*) <> COUNT(DISTINCT funding_key)
) invalid
UNION ALL
SELECT 'order_benefit_payload_domain_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_benefit_application_event
WHERE amount_minor <= 0
   OR benefit_source_version <= 0
   OR benefit_type NOT IN ('COUPON', 'PROMOTION', 'ALLOWANCE', 'CAMPAIGN')
   OR currency_code <> 'CNY'
   OR NOT (calculation_digest REGEXP '^[0-9a-f]{64}$')
   OR CHAR_LENGTH(application_key) NOT BETWEEN 1 AND 128
   OR CHAR_LENGTH(benefit_source_type) NOT BETWEEN 1 AND 32
   OR NOT (benefit_source_type REGEXP '^[A-Z][A-Z0-9_]*$')
   OR CHAR_LENGTH(benefit_source_id) NOT BETWEEN 1 AND 128
   OR (entitlement_id IS NOT NULL AND CHAR_LENGTH(entitlement_id) NOT BETWEEN 1 AND 128)
UNION ALL
SELECT 'order_benefit_allocation_domain_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event
WHERE amount_minor <= 0
   OR currency_code <> 'CNY'
   OR application_currency_code <> currency_code
   OR line_key IS NULL OR line_key = ''
   OR CHAR_LENGTH(line_key) > 128
   OR CHAR_LENGTH(allocation_key) NOT BETWEEN 1 AND 128
UNION ALL
SELECT 'order_benefit_funding_domain_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
WHERE amount_minor <= 0
   OR currency_code <> 'CNY'
   OR allocation_currency_code <> currency_code
   OR funder_type NOT IN ('PLATFORM', 'MERCHANT', 'PARTNER')
   OR funder_id IS NULL OR funder_id = ''
   OR CHAR_LENGTH(funder_id) > 128
   OR CHAR_LENGTH(funding_key) NOT BETWEEN 1 AND 128
UNION ALL
SELECT 'order_benefit_application_allocation_not_conserved', COUNT(*)
FROM yshopping_dim.dim_canonical_order_benefit_application_current application
LEFT JOIN (
  SELECT tenant_id, order_id, benefit_application_id,
         COUNT(*) AS allocation_count, SUM(amount_minor) AS allocation_amount_minor
  FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event
  GROUP BY tenant_id, order_id, benefit_application_id
) allocation
  ON allocation.tenant_id = application.tenant_id
 AND allocation.order_id = application.order_id
 AND allocation.benefit_application_id = application.benefit_application_id
WHERE COALESCE(allocation.allocation_count, 0) NOT BETWEEN 1 AND 100
   OR application.amount_minor <> COALESCE(allocation.allocation_amount_minor, 0)
UNION ALL
SELECT 'order_benefit_allocation_funding_not_conserved', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
LEFT JOIN (
  SELECT tenant_id, order_id, benefit_application_id, benefit_allocation_id,
         COUNT(*) AS funding_count, SUM(amount_minor) AS funding_amount_minor
  FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
  GROUP BY tenant_id, order_id, benefit_application_id, benefit_allocation_id
) funding
  ON funding.tenant_id = allocation.tenant_id
 AND funding.order_id = allocation.order_id
 AND funding.benefit_application_id = allocation.benefit_application_id
 AND funding.benefit_allocation_id = allocation.benefit_allocation_id
WHERE COALESCE(funding.funding_count, 0) NOT BETWEEN 1 AND 10
   OR allocation.amount_minor <> COALESCE(funding.funding_amount_minor, 0)
UNION ALL
SELECT 'order_benefit_order_header_not_conserved', COUNT(*)
FROM (
  SELECT tenant_id, order_id, MIN(run_id) AS run_id, MIN(order_no) AS order_no,
         COUNT(DISTINCT run_id) AS run_id_variant_count,
         COUNT(DISTINCT order_no) AS order_no_variant_count,
         SUM(amount_minor) AS application_amount_minor
  FROM yshopping_dim.dim_canonical_order_benefit_application_current
  GROUP BY tenant_id, order_id
) benefit
LEFT JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = benefit.tenant_id AND order_current.order_id = benefit.order_id
WHERE order_current.order_id IS NULL
   OR benefit.run_id_variant_count <> 1
   OR benefit.order_no_variant_count <> 1
   OR order_current.run_id <> benefit.run_id
   OR order_current.order_no <> benefit.order_no
   OR order_current.discount_amount_minor <> benefit.application_amount_minor
UNION ALL
SELECT 'order_benefit_order_item_orphan', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
LEFT JOIN yshopping_dws.dws_canonical_order_item_current item
  ON item.tenant_id = allocation.tenant_id
 AND item.order_id = allocation.order_id
 AND item.order_item_id = allocation.order_item_id
WHERE item.order_item_id IS NULL
UNION ALL
SELECT 'order_benefit_item_line_key_inconsistent', COUNT(*)
FROM (
  SELECT tenant_id, order_id, order_item_id
  FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event
  GROUP BY tenant_id, order_id, order_item_id
  HAVING COUNT(DISTINCT line_key) <> 1
) invalid
UNION ALL
SELECT 'order_benefit_item_money_not_conserved', COUNT(*)
FROM yshopping_dws.dws_canonical_order_item_benefit_current
WHERE discount_amount_minor <> funding_amount_minor
   OR discount_amount_minor < 0
   OR net_amount_minor < 0
   OR gross_amount_minor <> discount_amount_minor + net_amount_minor
   OR funding_mismatch_count <> 0
UNION ALL
SELECT 'order_benefit_readiness_unproven', COUNT(*)
FROM yshopping_ads.ads_canonical_order_benefit_readiness
WHERE readiness_status = 'RECONCILED'
  AND (application_count <= 0 OR allocation_count <= 0 OR item_count <= 0
       OR header_discount_amount_minor <> application_amount_minor
       OR application_amount_minor <> allocation_amount_minor
       OR allocation_amount_minor <> funding_amount_minor
       OR funding_amount_minor <> item_discount_amount_minor
       OR gross_amount_minor <> item_discount_amount_minor + net_amount_minor
       OR evidence_semantics <> 'NONEMPTY_IMMUTABLE_ORDER_BENEFIT_V1');
