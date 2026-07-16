CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_after_sale_benefit_reversal_current AS
WITH expected_entitlements AS (
    SELECT after_sale.tenant_id, after_sale.after_sale_id,
           COUNT(DISTINCT application.benefit_application_id) AS entitlement_application_count
    FROM yshopping_dim.dim_canonical_after_sale_current after_sale
    JOIN yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
      ON allocation.tenant_id = after_sale.tenant_id
     AND allocation.order_id = after_sale.order_id
     AND allocation.order_item_id = after_sale.order_item_id
    JOIN yshopping_dim.dim_canonical_order_benefit_application_current application
      ON application.tenant_id = allocation.tenant_id
     AND application.order_id = allocation.order_id
     AND application.benefit_application_id = allocation.benefit_application_id
     AND application.entitlement_id IS NOT NULL
    GROUP BY after_sale.tenant_id, after_sale.after_sale_id
), reversal_exactness AS (
    SELECT reversal.tenant_id, reversal.after_sale_id, reversal.reversal_batch_id,
           COUNT(*) AS benefit_reversal_count,
           COUNT(DISTINCT reversal.idempotency_key) AS benefit_reversal_idempotency_count,
           COUNT(DISTINCT reversal.entitlement_id) AS returned_entitlement_count,
           SUM(reversal.amount_minor) AS benefit_reversal_amount_minor,
           SUM(CASE WHEN reversal.payload_benefit_reversal_id <> reversal.benefit_reversal_id
                  OR reversal.reversal_event_count <> 1
                  OR allocation.benefit_allocation_id IS NULL
                  OR application.benefit_application_id IS NULL
                  OR reversal.order_id <> allocation.order_id
                  OR reversal.order_item_id <> allocation.order_item_id
                  OR reversal.benefit_application_id <> allocation.benefit_application_id
                  OR reversal.amount_minor <> allocation.amount_minor
                  OR reversal.currency_code <> allocation.currency_code
                  OR reversal.benefit_type <> application.benefit_type
                  OR reversal.benefit_source_type <> application.benefit_source_type
                  OR reversal.benefit_source_id <> application.benefit_source_id
                  OR reversal.benefit_source_version <> application.benefit_source_version
                  OR NOT (reversal.entitlement_id <=> application.entitlement_id)
               THEN 1 ELSE 0 END) AS allocation_reversal_mismatch_count,
           SUM(CASE WHEN reversal.entitlement_id IS NULL
                          AND reversal.entitlement_effect_status = 'NOT_REQUIRED' THEN 0
                    WHEN reversal.entitlement_id IS NOT NULL
                          AND reversal.entitlement_effect_status = 'RETURNED'
                          AND reversal.benefit_type = 'COUPON'
                          AND reversal.benefit_source_type = 'COUPON_ENTITLEMENT'
                          AND reversal.benefit_source_id = reversal.entitlement_id
                          AND entitlement.entitlement_id IS NOT NULL
                          AND entitlement.current_status = 'RETURNED'
                          AND entitlement.aggregate_version = reversal.benefit_source_version + 1
                          AND entitlement.order_ref = reversal.run_id THEN 0
                    ELSE 1 END) AS entitlement_effect_mismatch_count,
           MAX(reversal.recorded_at) AS benefit_reversal_recorded_at
    FROM yshopping_dim.dim_canonical_after_sale_benefit_reversal_current reversal
    LEFT JOIN yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
      ON allocation.tenant_id = reversal.tenant_id
     AND allocation.order_id = reversal.order_id
     AND allocation.benefit_allocation_id = reversal.benefit_allocation_id
    LEFT JOIN yshopping_dim.dim_canonical_order_benefit_application_current application
      ON application.tenant_id = reversal.tenant_id
     AND application.order_id = reversal.order_id
     AND application.benefit_application_id = reversal.benefit_application_id
    LEFT JOIN yshopping_dim.dim_canonical_coupon_entitlement_current entitlement
      ON entitlement.tenant_id = reversal.tenant_id
     AND entitlement.entitlement_id = reversal.entitlement_id
    GROUP BY reversal.tenant_id, reversal.after_sale_id, reversal.reversal_batch_id
), funding_exactness AS (
    SELECT funding.tenant_id, funding.after_sale_id, funding.reversal_batch_id,
           COUNT(*) AS funding_reversal_count,
           SUM(funding.amount_minor) AS funding_reversal_amount_minor,
           SUM(CASE WHEN original.benefit_funding_id IS NULL
                  OR funding.benefit_allocation_id <> original.benefit_allocation_id
                  OR funding.funder_type <> original.funder_type
                  OR funding.funder_id <> original.funder_id
                  OR funding.amount_minor <> original.amount_minor
                  OR funding.currency_code <> original.currency_code
               THEN 1 ELSE 0 END) AS funding_reversal_mismatch_count
    FROM yshopping_dwd.dwd_canonical_after_sale_benefit_funding_reversal_event funding
    LEFT JOIN yshopping_dwd.dwd_canonical_order_benefit_funding_event original
      ON original.tenant_id = funding.tenant_id
     AND original.order_id = funding.order_id
     AND original.benefit_funding_id = funding.benefit_funding_id
    GROUP BY funding.tenant_id, funding.after_sale_id, funding.reversal_batch_id
)
SELECT reversal.*, COALESCE(expected.entitlement_application_count, 0) AS entitlement_application_count,
       funding.funding_reversal_count, funding.funding_reversal_amount_minor,
       funding.funding_reversal_mismatch_count
FROM reversal_exactness reversal
LEFT JOIN expected_entitlements expected
  ON expected.tenant_id = reversal.tenant_id
 AND expected.after_sale_id = reversal.after_sale_id
LEFT JOIN funding_exactness funding
  ON funding.tenant_id = reversal.tenant_id
 AND funding.after_sale_id = reversal.after_sale_id
 AND funding.reversal_batch_id = reversal.reversal_batch_id;
