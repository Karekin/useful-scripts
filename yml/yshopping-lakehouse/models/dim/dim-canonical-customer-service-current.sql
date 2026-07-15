CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_customer_service_ticket_current AS
SELECT event_id, tenant_id, ticket_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, run_id, ticket_no, customer_principal_id, channel_code,
       priority, category_code, previous_status, current_status, assigned_agent_principal_id,
       primary_order_ref, primary_after_sale_ref, operation, ticket_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, ticket_id) AS ticket_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, ticket_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_customer_service_ticket_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_customer_service_claim_current AS
SELECT event_id, tenant_id, claim_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, run_id, claim_code, ticket_id, claim_type, order_ref,
       after_sale_ref, previous_status, current_status, requested_amount_minor, approved_amount_minor,
       paid_amount_minor, currency_code, reason_code, compensation_entry_id, operation, claim_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, claim_id) AS claim_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, claim_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_customer_service_claim_event event
) ranked WHERE row_num = 1;
