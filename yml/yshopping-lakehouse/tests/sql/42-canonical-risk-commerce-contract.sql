SELECT 'risk_order_case_orphan_review' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_risk_order_case_current review
LEFT JOIN yshopping_dim.dim_canonical_risk_review_case_current base
  ON base.tenant_id = review.tenant_id AND base.case_id = review.case_id
WHERE base.case_id IS NULL;

SELECT 'risk_order_case_orphan_order' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_risk_order_case_current review
LEFT JOIN yshopping_dim.dim_canonical_order_current ord
  ON ord.tenant_id = review.tenant_id AND ord.order_id = review.order_id
WHERE ord.order_id IS NULL;

SELECT 'risk_dispute_orphan_payment' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_risk_payment_dispute_current dispute
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = dispute.tenant_id AND payment.payment_id = dispute.payment_id
WHERE payment.payment_id IS NULL OR payment.order_id <> dispute.order_id;

SELECT 'risk_dispute_resolution_shape_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_risk_payment_dispute_current
WHERE (current_status = 'OPEN' AND resolved_at IS NOT NULL)
   OR (current_status <> 'OPEN' AND resolved_at IS NULL);

SELECT 'risk_loss_orphan_order' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_loss_entry_event loss
LEFT JOIN yshopping_dim.dim_canonical_order_current ord
  ON ord.tenant_id = loss.tenant_id AND ord.order_id = loss.order_id
WHERE ord.order_id IS NULL;

SELECT 'risk_loss_chargeback_without_dispute' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_risk_loss_entry_event loss
LEFT JOIN yshopping_dim.dim_canonical_risk_payment_dispute_current dispute
  ON dispute.tenant_id = loss.tenant_id AND dispute.dispute_id = loss.dispute_id
WHERE loss.entry_type = 'CHARGEBACK_LOSS'
  AND (dispute.dispute_id IS NULL OR dispute.dispute_type <> 'CHARGEBACK');
