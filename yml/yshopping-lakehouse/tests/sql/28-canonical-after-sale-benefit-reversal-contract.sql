SELECT 'after_sale_benefit_reversal_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT event_id FROM yshopping_dwd.dwd_canonical_after_sale_benefit_reversal_event
    GROUP BY event_id HAVING COUNT(*) <> 1
) v
UNION ALL
SELECT 'after_sale_benefit_reversal_payload_identity_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_benefit_reversal_event
WHERE payload_benefit_reversal_id <> benefit_reversal_id
   OR aggregate_version <> 1 OR schema_version <> 1
   OR amount_minor <= 0 OR currency_code <> 'CNY'
   OR NOT ((entitlement_id IS NULL AND entitlement_effect_status = 'NOT_REQUIRED')
       OR (entitlement_id IS NOT NULL AND entitlement_effect_status = 'RETURNED'
           AND benefit_type = 'COUPON' AND benefit_source_type = 'COUPON_ENTITLEMENT'
           AND benefit_source_id = entitlement_id));

SELECT 'after_sale_benefit_reversal_allocation_not_exact', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_benefit_reversal_current
WHERE allocation_reversal_mismatch_count <> 0
UNION ALL
SELECT 'after_sale_benefit_reversal_entitlement_not_exact', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_benefit_reversal_current
WHERE entitlement_effect_mismatch_count <> 0
UNION ALL
SELECT 'after_sale_benefit_reversal_entitlement_cardinality_invalid', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_benefit_reversal_current
WHERE entitlement_application_count <> returned_entitlement_count
UNION ALL
SELECT 'after_sale_benefit_reversal_funding_not_exact', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_benefit_reversal_current
WHERE funding_reversal_count IS NULL OR funding_reversal_count <= 0
   OR funding_reversal_mismatch_count <> 0
   OR funding_reversal_amount_minor <> benefit_reversal_amount_minor
UNION ALL
SELECT 'after_sale_benefit_reversal_idempotency_invalid', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_benefit_reversal_current
WHERE benefit_reversal_idempotency_count <> benefit_reversal_count;

SELECT 'after_sale_benefit_reversal_saga_money_invalid', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_resolution_current
WHERE reported_benefit_amount_minor > 0
  AND (reported_gross_amount_minor <> reported_benefit_amount_minor + reported_net_amount_minor
    OR reported_net_amount_minor <> approved_amount_minor
    OR benefit_reversal_status = 'RECORDED'
       AND (benefit_reversal_amount_minor <> reported_benefit_amount_minor
         OR recorded_benefit_reversal_amount_minor <> reported_benefit_amount_minor
         OR funding_reversal_amount_minor <> reported_benefit_amount_minor))
UNION ALL
SELECT 'after_sale_benefit_reversal_effect_order_invalid', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_resolution_current
WHERE reported_benefit_amount_minor > 0 AND saga_status = 'COMPLETED'
  AND (inventory_returned_recorded_at > benefit_reversal_recorded_at
    OR benefit_reversal_recorded_at > refund_succeeded_recorded_at);

SELECT 'after_sale_benefit_reversal_completed_unreconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_after_sale_readiness
WHERE reported_benefit_amount_minor > 0 AND saga_status = 'COMPLETED'
  AND readiness_status <> 'RECONCILED'
UNION ALL
SELECT 'after_sale_benefit_reversal_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'after_sale.benefit_reversal.recorded'
  AND regexp(get_json_string(payload, '$'),
      '(buyer_name|buyer_phone|receiver_name|receiver_phone|address|authorization|secret|token)');
