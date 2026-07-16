CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_order_benefit_application_current AS
SELECT
    event_id, schema_version, source_system, tenant_id, aggregate_type, envelope_order_id, aggregate_version,
    event_sequence, occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    run_id, order_id, order_no, benefit_application_id, application_key, benefit_type,
    benefit_source_type, benefit_source_id, benefit_source_version, entitlement_id,
    amount_minor, currency_code, calculation_digest, application_event_count
FROM (
    SELECT application.*,
           COUNT(*) OVER (
               PARTITION BY tenant_id, order_id, benefit_application_id
           ) AS application_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, order_id, benefit_application_id
               ORDER BY event_sequence DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_order_benefit_application_event application
) ranked
WHERE row_num = 1;
