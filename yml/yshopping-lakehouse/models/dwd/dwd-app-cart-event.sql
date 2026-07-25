CREATE OR REPLACE VIEW yshopping_dwd.dwd_app_cart_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS cart_id,
    aggregate_version AS cart_version,
    event_sequence,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.buyer_principal_id') AS buyer_principal_id,
    CAST(get_json_string(payload, '$.line_count') AS INT) AS line_count,
    CAST(get_json_string(payload, '$.selected_line_count') AS INT) AS selected_line_count,
    json_query(payload, '$.lines') AS lines,
    get_json_string(headers, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'app.cart.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-app-commerce';
