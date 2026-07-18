CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_risk_order_current AS
WITH customer_service_defect_orders AS (
    SELECT tenant_id, primary_order_ref AS order_id
    FROM yshopping_dim.dim_canonical_customer_service_ticket_current
    WHERE primary_order_ref IS NOT NULL
    UNION DISTINCT
    SELECT tenant_id, order_ref AS order_id
    FROM yshopping_dim.dim_canonical_customer_service_claim_current
    WHERE order_ref IS NOT NULL
)
SELECT
    orders.tenant_id,
    orders.order_id,
    orders.payment_id,
    COUNT(DISTINCT review.order_risk_case_id) AS order_risk_case_count,
    COUNT(DISTINCT CASE WHEN review.review_status IN ('OPEN', 'IN_REVIEW', 'DECIDED', 'CLOSED')
                        THEN review.order_risk_case_id END) AS flagged_review_count,
    COUNT(DISTINCT CASE WHEN review.latest_decision_type IN ('ESCALATE', 'CONFIRM_RISK')
                        THEN review.order_risk_case_id END) AS adjudicated_risk_case_count,
    COUNT(DISTINCT CASE WHEN dispute.current_status = 'OPEN' THEN dispute.dispute_id END) AS open_dispute_count,
    COUNT(DISTINCT CASE WHEN dispute.dispute_type = 'CHARGEBACK'
                          AND dispute.current_status IN ('OPEN', 'WON', 'LOST')
                        THEN dispute.dispute_id END) AS chargeback_dispute_count,
    COALESCE(SUM(loss.signed_amount_minor), 0) AS net_loss_amount_minor,
    MAX(CASE WHEN cs.order_id IS NOT NULL THEN 1 ELSE 0 END) AS has_customer_service_defect,
    MAX(GREATEST(
        COALESCE(review.recorded_at, orders.recorded_at),
        COALESCE(dispute.recorded_at, orders.recorded_at),
        COALESCE(loss.recorded_at, orders.recorded_at),
        orders.recorded_at
    )) AS data_freshness_at
FROM yshopping_dim.dim_canonical_order_current orders
LEFT JOIN yshopping_dim.dim_canonical_risk_order_case_current review
  ON review.tenant_id = orders.tenant_id AND review.order_id = orders.order_id
LEFT JOIN yshopping_dim.dim_canonical_risk_payment_dispute_current dispute
  ON dispute.tenant_id = orders.tenant_id AND dispute.order_id = orders.order_id
LEFT JOIN yshopping_dwd.dwd_canonical_risk_loss_entry_event loss
  ON loss.tenant_id = orders.tenant_id AND loss.order_id = orders.order_id
LEFT JOIN customer_service_defect_orders cs
  ON cs.tenant_id = orders.tenant_id AND cs.order_id = orders.order_id
GROUP BY orders.tenant_id, orders.order_id, orders.payment_id;
