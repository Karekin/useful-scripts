CREATE OR REPLACE VIEW yshopping_dim.dim_app_cart_current AS
SELECT
    ranked.event_id,
    ranked.tenant_id,
    ranked.cart_id,
    ranked.cart_version,
    ranked.event_sequence,
    ranked.occurred_at,
    ranked.recorded_at,
    ranked.correlation_id,
    ranked.causation_id,
    ranked.idempotency_key,
    ranked.buyer_principal_id,
    ranked.line_count,
    ranked.selected_line_count,
    ranked.operation,
    ranked.lines
FROM (
    SELECT
        event.*,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, cart_id
            ORDER BY cart_version DESC, recorded_at DESC, event_id DESC
        ) AS row_num
    FROM yshopping_dwd.dwd_app_cart_event event
) ranked
WHERE ranked.row_num = 1;
