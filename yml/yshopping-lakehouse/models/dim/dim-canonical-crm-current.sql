CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_crm_customer_current AS
SELECT
    status.tenant_id,
    status.customer_id,
    status.customer_code,
    status.customer_aggregate_id,
    status.aggregate_version AS customer_aggregate_version,
    status.occurred_at AS status_occurred_at,
    status.recorded_at AS status_recorded_at,
    status.correlation_id,
    status.causation_id,
    status.idempotency_key,
    status.run_id,
    COALESCE(owner.current_owner_principal_id, status.owner_principal_id) AS current_owner_principal_id,
    owner.previous_owner_principal_id,
    owner.handover_reason_code,
    owner.transferred_at AS owner_transferred_at,
    status.previous_status,
    status.current_status,
    status.follow_up_status,
    status.deal_status,
    status.lock_status,
    status.source_code,
    status.industry_code,
    status.level_code,
    status.last_follow_up_at,
    status.next_contact_at,
    status.linked_contact_count,
    status.linked_opportunity_count,
    status.customer_status_event_count,
    COALESCE(owner.owner_change_count, 0) AS owner_change_count,
    GREATEST(status.recorded_at, COALESCE(owner.data_freshness_at, status.recorded_at)) AS data_freshness_at
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, customer_id) AS customer_status_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, customer_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_crm_customer_status_event event
) status
LEFT JOIN (
    SELECT tenant_id, customer_id, previous_owner_principal_id, current_owner_principal_id,
           handover_reason_code, transferred_at, owner_change_count, data_freshness_at
    FROM (
        SELECT event.*,
               COUNT(*) OVER (PARTITION BY tenant_id, customer_id) AS owner_change_count,
               MAX(recorded_at) OVER (PARTITION BY tenant_id, customer_id) AS data_freshness_at,
               ROW_NUMBER() OVER (PARTITION BY tenant_id, customer_id
                                  ORDER BY transferred_at DESC, recorded_at DESC, event_id DESC) AS row_num
        FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event event
    ) ranked
    WHERE row_num = 1
) owner ON owner.tenant_id = status.tenant_id AND owner.customer_id = status.customer_id
WHERE status.row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_crm_lead_current AS
SELECT event_id, tenant_id, lead_id, lead_code, lead_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, run_id, owner_principal_id, previous_status, current_status,
       follow_up_status, source_code, industry_code, level_code, converted_customer_id,
       last_follow_up_at, next_contact_at, lead_status_event_count, data_freshness_at
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, lead_id) AS lead_status_event_count,
           MAX(recorded_at) OVER (PARTITION BY tenant_id, lead_id) AS data_freshness_at,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, lead_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_crm_lead_status_event event
) ranked
WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_crm_contact_current AS
SELECT event_id, tenant_id, contact_id, contact_code, contact_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, run_id, customer_id, owner_principal_id,
       previous_status, current_status, follow_up_status, master_decision_maker, post_code, parent_contact_id,
       last_follow_up_at, next_contact_at, contact_status_event_count, data_freshness_at
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, contact_id) AS contact_status_event_count,
           MAX(recorded_at) OVER (PARTITION BY tenant_id, contact_id) AS data_freshness_at,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, contact_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_crm_contact_status_event event
) ranked
WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_crm_opportunity_current AS
SELECT event_id, tenant_id, opportunity_id, opportunity_code, opportunity_aggregate_id, aggregate_version,
       occurred_at, recorded_at, correlation_id, causation_id, idempotency_key, run_id, customer_id,
       owner_principal_id, previous_stage_code, current_stage_code, previous_pipeline_status,
       current_pipeline_status, follow_up_status, expected_deal_at, total_amount_minor, currency_code,
       win_probability_basis_points, linked_contact_count, last_follow_up_at, next_contact_at,
       opportunity_stage_event_count,
       CASE WHEN current_pipeline_status = 'OPEN' THEN total_amount_minor ELSE 0 END AS open_pipeline_amount_minor,
       CASE
           WHEN current_pipeline_status = 'OPEN'
           THEN CAST(total_amount_minor * win_probability_basis_points / 10000.0 AS DECIMAL(38,2))
           ELSE CAST(0 AS DECIMAL(38,2))
       END AS weighted_pipeline_amount_minor,
       CASE WHEN current_pipeline_status = 'WON' THEN total_amount_minor ELSE 0 END AS won_amount_minor,
       data_freshness_at
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, opportunity_id) AS opportunity_stage_event_count,
           MAX(recorded_at) OVER (PARTITION BY tenant_id, opportunity_id) AS data_freshness_at,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, opportunity_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_crm_opportunity_stage_event event
) ranked
WHERE row_num = 1;
