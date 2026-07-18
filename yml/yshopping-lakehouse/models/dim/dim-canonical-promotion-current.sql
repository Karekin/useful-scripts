CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_promotion_campaign_current AS
SELECT event_id, tenant_id, campaign_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, campaign_code, campaign_kind, campaign_name,
       previous_status, current_status, starts_at, ends_at, operation, campaign_event_count FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, campaign_id) AS campaign_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, campaign_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_promotion_campaign_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_coupon_template_current AS
SELECT event_id, tenant_id, template_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, template_code, campaign_id, title, benefit_type,
       face_amount_minor, threshold_minor, discount_basis_points, cap_amount_minor, currency_code,
       funder_type, merchant_id, valid_from, valid_to, previous_status, current_status, operation,
       template_event_count FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, template_id) AS template_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, template_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_coupon_template_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_coupon_entitlement_current AS
SELECT event_id, tenant_id, entitlement_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, entitlement_code, template_id, campaign_id,
       principal_id, order_ref, previous_status, current_status, face_amount_minor, threshold_minor,
       currency_code, operation, ledger_entry_id, reason, entitlement_event_count FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, entitlement_id) AS entitlement_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, entitlement_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_coupon_entitlement_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_advertising_placement_current AS
SELECT event_id, tenant_id, placement_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, placement_code, campaign_id, placement_name,
       channel_code, page_code, slot_code, creative_ref, valid_from, valid_to, previous_status,
       current_status, operation, placement_event_count FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, placement_id) AS placement_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, placement_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_advertising_placement_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_promotion_experiment_result_current AS
SELECT event_id, tenant_id, experiment_id, aggregate_version, event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, experiment_code, campaign_id, merchant_id,
       measured_from, measured_to, baseline_contribution_profit_minor,
       treatment_contribution_profit_minor, incremental_contribution_profit_minor,
       promotion_cost_minor, eligible_population_count, treatment_population_count,
       control_population_count, currency_code, methodology_ref, experiment_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, experiment_id) AS experiment_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, experiment_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_promotion_experiment_result_event event
) ranked WHERE row_num = 1;
