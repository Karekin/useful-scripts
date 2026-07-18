CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_order_case_current AS
SELECT
    risk_case.event_id,
    risk_case.tenant_id,
    risk_case.order_risk_case_id,
    risk_case.case_id,
    risk_case.order_id,
    risk_case.payment_id,
    risk_case.risk_type,
    risk_case.reason_code,
    review.current_status AS review_status,
    decision.latest_decision_type,
    decision.latest_decision_at,
    risk_case.occurred_at,
    risk_case.recorded_at
FROM yshopping_dwd.dwd_canonical_risk_order_case_event risk_case
JOIN yshopping_dim.dim_canonical_risk_review_case_current review
  ON review.tenant_id = risk_case.tenant_id AND review.case_id = risk_case.case_id
LEFT JOIN (
    SELECT tenant_id, case_id,
           MAX_BY(decision_type, occurred_at) AS latest_decision_type,
           MAX(occurred_at) AS latest_decision_at
    FROM yshopping_dwd.dwd_canonical_risk_decision_event
    GROUP BY tenant_id, case_id
) decision
  ON decision.tenant_id = risk_case.tenant_id AND decision.case_id = risk_case.case_id;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_risk_payment_dispute_current AS
SELECT event_id, tenant_id, dispute_id, order_id, payment_id, case_id, decision_id, dispute_type,
       previous_status, current_status, reason_code, amount_minor, currency_code, external_ref, opened_at,
       resolved_at, occurred_at, recorded_at, dispute_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, dispute_id) AS dispute_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, dispute_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_risk_payment_dispute_event event
) ranked
WHERE row_num = 1;
