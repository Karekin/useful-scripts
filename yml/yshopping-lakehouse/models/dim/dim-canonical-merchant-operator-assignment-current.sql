CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_merchant_operator_assignment_current AS
SELECT
    event_id, tenant_id, assignment_id, merchant_id, shop_id, principal_id, role_code,
    previous_status, current_status, valid_from, aggregate_version, occurred_at, recorded_at,
    correlation_id
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, assignment_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_merchant_operator_assignment_event event
) ranked
WHERE row_num = 1;
