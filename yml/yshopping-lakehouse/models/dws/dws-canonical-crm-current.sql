CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_crm_customer_profile_current AS
SELECT customer.tenant_id, customer.customer_id, customer.customer_code, customer.current_owner_principal_id,
       customer.current_status, customer.follow_up_status, customer.deal_status, customer.lock_status,
       customer.source_code, customer.industry_code, customer.level_code,
       COALESCE(contact.contact_count, 0) AS contact_count,
       COALESCE(contact.active_contact_count, 0) AS active_contact_count,
       COALESCE(contact.primary_decision_maker_count, 0) AS primary_decision_maker_count,
       COALESCE(opportunity.opportunity_count, 0) AS opportunity_count,
       COALESCE(opportunity.open_opportunity_count, 0) AS open_opportunity_count,
       COALESCE(opportunity.won_opportunity_count, 0) AS won_opportunity_count,
       COALESCE(opportunity.lost_opportunity_count, 0) AS lost_opportunity_count,
       COALESCE(opportunity.open_pipeline_amount_minor, 0) AS open_pipeline_amount_minor,
       COALESCE(opportunity.weighted_pipeline_amount_minor, CAST(0 AS DECIMAL(38,2)))
           AS weighted_pipeline_amount_minor,
       COALESCE(opportunity.won_amount_minor, 0) AS won_amount_minor,
       COALESCE(lead.converted_lead_count, 0) AS converted_lead_count,
       COALESCE(follow_up.follow_up_count, 0) AS follow_up_count,
       COALESCE(follow_up.customer_follow_up_count, 0) AS customer_follow_up_count,
       COALESCE(follow_up.contact_follow_up_count, 0) AS contact_follow_up_count,
       COALESCE(follow_up.opportunity_follow_up_count, 0) AS opportunity_follow_up_count,
       follow_up.last_follow_up_recorded_at,
       COALESCE(follow_up.last_follow_up_type_code, 'UNKNOWN') AS last_follow_up_type_code,
       CASE
           WHEN customer.current_status IN ('ACTIVE', 'AT_RISK')
            AND customer.next_contact_at IS NOT NULL
            AND customer.next_contact_at < CURRENT_TIMESTAMP()
           THEN 1 ELSE 0
       END AS overdue_follow_up_flag,
       GREATEST(customer.data_freshness_at,
                COALESCE(contact.data_freshness_at, customer.data_freshness_at),
                COALESCE(opportunity.data_freshness_at, customer.data_freshness_at),
                COALESCE(lead.data_freshness_at, customer.data_freshness_at),
                COALESCE(follow_up.data_freshness_at, customer.data_freshness_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_crm_customer_current customer
LEFT JOIN (
    SELECT tenant_id, customer_id,
           COUNT(*) AS contact_count,
           SUM(CASE WHEN current_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_contact_count,
           SUM(CASE WHEN current_status = 'ACTIVE' AND master_decision_maker THEN 1 ELSE 0 END)
               AS primary_decision_maker_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_contact_current
    GROUP BY tenant_id, customer_id
) contact ON contact.tenant_id = customer.tenant_id AND contact.customer_id = customer.customer_id
LEFT JOIN (
    SELECT tenant_id, customer_id,
           COUNT(*) AS opportunity_count,
           SUM(CASE WHEN current_pipeline_status = 'OPEN' THEN 1 ELSE 0 END) AS open_opportunity_count,
           SUM(CASE WHEN current_pipeline_status = 'WON' THEN 1 ELSE 0 END) AS won_opportunity_count,
           SUM(CASE WHEN current_pipeline_status = 'LOST' THEN 1 ELSE 0 END) AS lost_opportunity_count,
           SUM(open_pipeline_amount_minor) AS open_pipeline_amount_minor,
           CAST(SUM(weighted_pipeline_amount_minor) AS DECIMAL(38,2)) AS weighted_pipeline_amount_minor,
           SUM(won_amount_minor) AS won_amount_minor,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_opportunity_current
    GROUP BY tenant_id, customer_id
) opportunity ON opportunity.tenant_id = customer.tenant_id AND opportunity.customer_id = customer.customer_id
LEFT JOIN (
    SELECT tenant_id, converted_customer_id AS customer_id,
           COUNT(*) AS converted_lead_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_lead_current
    WHERE current_status = 'CONVERTED' AND converted_customer_id IS NOT NULL
    GROUP BY tenant_id, converted_customer_id
) lead ON lead.tenant_id = customer.tenant_id AND lead.customer_id = customer.customer_id
LEFT JOIN (
    SELECT customer_rollup.tenant_id, customer_rollup.customer_id,
           customer_rollup.follow_up_count,
           customer_rollup.customer_follow_up_count,
           customer_rollup.contact_follow_up_count,
           customer_rollup.opportunity_follow_up_count,
           last_event.occurred_at AS last_follow_up_recorded_at,
           last_event.follow_up_type_code AS last_follow_up_type_code,
           customer_rollup.data_freshness_at
    FROM (
        SELECT tenant_id, customer_id,
               COUNT(*) AS follow_up_count,
               SUM(CASE WHEN biz_type = 'CUSTOMER' THEN 1 ELSE 0 END) AS customer_follow_up_count,
               SUM(CASE WHEN biz_type = 'CONTACT' THEN 1 ELSE 0 END) AS contact_follow_up_count,
               SUM(CASE WHEN biz_type = 'OPPORTUNITY' THEN 1 ELSE 0 END) AS opportunity_follow_up_count,
               MAX(recorded_at) AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
        WHERE customer_id IS NOT NULL
        GROUP BY tenant_id, customer_id
    ) customer_rollup
    LEFT JOIN (
        SELECT tenant_id, customer_id, occurred_at, follow_up_type_code,
               ROW_NUMBER() OVER (PARTITION BY tenant_id, customer_id
                                  ORDER BY occurred_at DESC, recorded_at DESC, event_id DESC) AS row_num
        FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
        WHERE customer_id IS NOT NULL
    ) last_event
      ON last_event.tenant_id = customer_rollup.tenant_id
     AND last_event.customer_id = customer_rollup.customer_id
     AND last_event.row_num = 1
) follow_up ON follow_up.tenant_id = customer.tenant_id AND follow_up.customer_id = customer.customer_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_crm_funnel_current AS
SELECT owner.tenant_id, owner.owner_principal_id,
       COALESCE(lead.new_lead_count, 0) AS new_lead_count,
       COALESCE(lead.contacted_lead_count, 0) AS contacted_lead_count,
       COALESCE(lead.qualified_lead_count, 0) AS qualified_lead_count,
       COALESCE(lead.disqualified_lead_count, 0) AS disqualified_lead_count,
       COALESCE(lead.converted_lead_count, 0) AS converted_lead_count,
       COALESCE(customer.active_customer_count, 0) AS active_customer_count,
       COALESCE(customer.at_risk_customer_count, 0) AS at_risk_customer_count,
       COALESCE(customer.deal_customer_count, 0) AS deal_customer_count,
       COALESCE(opportunity.open_opportunity_count, 0) AS open_opportunity_count,
       COALESCE(opportunity.won_opportunity_count, 0) AS won_opportunity_count,
       COALESCE(opportunity.lost_opportunity_count, 0) AS lost_opportunity_count,
       COALESCE(opportunity.open_pipeline_amount_minor, 0) AS open_pipeline_amount_minor,
       COALESCE(opportunity.weighted_pipeline_amount_minor, CAST(0 AS DECIMAL(38,2)))
           AS weighted_pipeline_amount_minor,
       COALESCE(opportunity.won_amount_minor, 0) AS won_amount_minor,
       COALESCE(customer.overdue_customer_count, 0) AS overdue_customer_count,
       COALESCE(owner_event.transfer_in_count, 0) AS customer_transfer_in_count,
       COALESCE(owner_event.transfer_out_count, 0) AS customer_transfer_out_count,
       GREATEST(owner.data_freshness_at,
                COALESCE(lead.data_freshness_at, owner.data_freshness_at),
                COALESCE(customer.data_freshness_at, owner.data_freshness_at),
                COALESCE(opportunity.data_freshness_at, owner.data_freshness_at),
                COALESCE(owner_event.data_freshness_at, owner.data_freshness_at)) AS data_freshness_at
FROM (
    SELECT tenant_id, owner_principal_id, MAX(data_freshness_at) AS data_freshness_at
    FROM (
        SELECT tenant_id, owner_principal_id, data_freshness_at FROM yshopping_dim.dim_canonical_crm_lead_current
        UNION ALL
        SELECT tenant_id, current_owner_principal_id AS owner_principal_id, data_freshness_at
        FROM yshopping_dim.dim_canonical_crm_customer_current
        UNION ALL
        SELECT tenant_id, owner_principal_id, data_freshness_at FROM yshopping_dim.dim_canonical_crm_opportunity_current
        UNION ALL
        SELECT tenant_id, current_owner_principal_id AS owner_principal_id, recorded_at AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event
    ) owner_events
    WHERE owner_principal_id IS NOT NULL
    GROUP BY tenant_id, owner_principal_id
) owner
LEFT JOIN (
    SELECT tenant_id, owner_principal_id,
           SUM(CASE WHEN current_status = 'NEW' THEN 1 ELSE 0 END) AS new_lead_count,
           SUM(CASE WHEN current_status = 'CONTACTED' THEN 1 ELSE 0 END) AS contacted_lead_count,
           SUM(CASE WHEN current_status = 'QUALIFIED' THEN 1 ELSE 0 END) AS qualified_lead_count,
           SUM(CASE WHEN current_status = 'DISQUALIFIED' THEN 1 ELSE 0 END) AS disqualified_lead_count,
           SUM(CASE WHEN current_status = 'CONVERTED' THEN 1 ELSE 0 END) AS converted_lead_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_lead_current
    GROUP BY tenant_id, owner_principal_id
) lead ON lead.tenant_id = owner.tenant_id AND lead.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, current_owner_principal_id AS owner_principal_id,
           SUM(CASE WHEN current_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_customer_count,
           SUM(CASE WHEN current_status = 'AT_RISK' THEN 1 ELSE 0 END) AS at_risk_customer_count,
           SUM(CASE WHEN current_status = 'DEAL' THEN 1 ELSE 0 END) AS deal_customer_count,
           SUM(CASE
                   WHEN current_status IN ('ACTIVE', 'AT_RISK')
                    AND next_contact_at IS NOT NULL
                    AND next_contact_at < CURRENT_TIMESTAMP()
                   THEN 1 ELSE 0
               END) AS overdue_customer_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_customer_current
    GROUP BY tenant_id, current_owner_principal_id
) customer ON customer.tenant_id = owner.tenant_id AND customer.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, owner_principal_id,
           SUM(CASE WHEN current_pipeline_status = 'OPEN' THEN 1 ELSE 0 END) AS open_opportunity_count,
           SUM(CASE WHEN current_pipeline_status = 'WON' THEN 1 ELSE 0 END) AS won_opportunity_count,
           SUM(CASE WHEN current_pipeline_status = 'LOST' THEN 1 ELSE 0 END) AS lost_opportunity_count,
           SUM(open_pipeline_amount_minor) AS open_pipeline_amount_minor,
           CAST(SUM(weighted_pipeline_amount_minor) AS DECIMAL(38,2)) AS weighted_pipeline_amount_minor,
           SUM(won_amount_minor) AS won_amount_minor,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_opportunity_current
    GROUP BY tenant_id, owner_principal_id
) opportunity ON opportunity.tenant_id = owner.tenant_id AND opportunity.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, principal_id AS owner_principal_id,
           SUM(transfer_in_count) AS transfer_in_count,
           SUM(transfer_out_count) AS transfer_out_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM (
        SELECT tenant_id, current_owner_principal_id AS principal_id,
               COUNT(*) AS transfer_in_count, CAST(0 AS BIGINT) AS transfer_out_count,
               MAX(recorded_at) AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event
        GROUP BY tenant_id, current_owner_principal_id
        UNION ALL
        SELECT tenant_id, previous_owner_principal_id AS principal_id,
               CAST(0 AS BIGINT) AS transfer_in_count, COUNT(*) AS transfer_out_count,
               MAX(recorded_at) AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event
        WHERE previous_owner_principal_id IS NOT NULL
        GROUP BY tenant_id, previous_owner_principal_id
    ) owner_movements
    WHERE principal_id IS NOT NULL
    GROUP BY tenant_id, principal_id
) owner_event ON owner_event.tenant_id = owner.tenant_id
             AND owner_event.owner_principal_id = owner.owner_principal_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_crm_owner_performance_current AS
SELECT owner.tenant_id, owner.owner_principal_id,
       COALESCE(customer.managed_customer_count, 0) AS managed_customer_count,
       COALESCE(contact.managed_contact_count, 0) AS managed_contact_count,
       COALESCE(opportunity.managed_opportunity_count, 0) AS managed_opportunity_count,
       COALESCE(opportunity.open_pipeline_amount_minor, 0) AS open_pipeline_amount_minor,
       COALESCE(opportunity.won_amount_minor, 0) AS won_amount_minor,
       COALESCE(opportunity.won_opportunity_count, 0) AS won_opportunity_count,
       COALESCE(opportunity.closed_opportunity_count, 0) AS closed_opportunity_count,
       CASE
           WHEN COALESCE(opportunity.closed_opportunity_count, 0) = 0 THEN NULL
           ELSE CAST(ROUND(10000.0 * opportunity.won_opportunity_count
                           / opportunity.closed_opportunity_count, 0) AS INT)
       END AS win_rate_basis_points,
       COALESCE(follow_up.follow_up_count, 0) AS follow_up_count,
       COALESCE(follow_up.customer_follow_up_count, 0) AS customer_follow_up_count,
       COALESCE(follow_up.contact_follow_up_count, 0) AS contact_follow_up_count,
       COALESCE(follow_up.opportunity_follow_up_count, 0) AS opportunity_follow_up_count,
       COALESCE(owner_move.customer_transfer_in_count, 0) AS customer_transfer_in_count,
       COALESCE(owner_move.customer_transfer_out_count, 0) AS customer_transfer_out_count,
       COALESCE(customer.overdue_customer_count, 0) AS overdue_customer_count,
       GREATEST(owner.data_freshness_at,
                COALESCE(customer.data_freshness_at, owner.data_freshness_at),
                COALESCE(contact.data_freshness_at, owner.data_freshness_at),
                COALESCE(opportunity.data_freshness_at, owner.data_freshness_at),
                COALESCE(follow_up.data_freshness_at, owner.data_freshness_at),
                COALESCE(owner_move.data_freshness_at, owner.data_freshness_at)) AS data_freshness_at
FROM (
    SELECT tenant_id, owner_principal_id, MAX(data_freshness_at) AS data_freshness_at
    FROM (
        SELECT tenant_id, owner_principal_id, data_freshness_at FROM yshopping_dws.dws_canonical_crm_funnel_current
        UNION ALL
        SELECT tenant_id, actor_principal_id AS owner_principal_id, MAX(recorded_at) AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
        GROUP BY tenant_id, actor_principal_id
    ) owner_events
    WHERE owner_principal_id IS NOT NULL
    GROUP BY tenant_id, owner_principal_id
) owner
LEFT JOIN (
    SELECT tenant_id, current_owner_principal_id AS owner_principal_id,
           COUNT(*) AS managed_customer_count,
           SUM(CASE
                   WHEN current_status IN ('ACTIVE', 'AT_RISK')
                    AND next_contact_at IS NOT NULL
                    AND next_contact_at < CURRENT_TIMESTAMP()
                   THEN 1 ELSE 0
               END) AS overdue_customer_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_customer_current
    GROUP BY tenant_id, current_owner_principal_id
) customer ON customer.tenant_id = owner.tenant_id AND customer.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, owner_principal_id,
           COUNT(*) AS managed_contact_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_contact_current
    GROUP BY tenant_id, owner_principal_id
) contact ON contact.tenant_id = owner.tenant_id AND contact.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, owner_principal_id,
           COUNT(*) AS managed_opportunity_count,
           SUM(open_pipeline_amount_minor) AS open_pipeline_amount_minor,
           SUM(won_amount_minor) AS won_amount_minor,
           SUM(CASE WHEN current_pipeline_status = 'WON' THEN 1 ELSE 0 END) AS won_opportunity_count,
           SUM(CASE WHEN current_pipeline_status IN ('WON', 'LOST') THEN 1 ELSE 0 END) AS closed_opportunity_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_crm_opportunity_current
    GROUP BY tenant_id, owner_principal_id
) opportunity ON opportunity.tenant_id = owner.tenant_id
             AND opportunity.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, actor_principal_id AS owner_principal_id,
           COUNT(*) AS follow_up_count,
           SUM(CASE WHEN biz_type = 'CUSTOMER' THEN 1 ELSE 0 END) AS customer_follow_up_count,
           SUM(CASE WHEN biz_type = 'CONTACT' THEN 1 ELSE 0 END) AS contact_follow_up_count,
           SUM(CASE WHEN biz_type = 'OPPORTUNITY' THEN 1 ELSE 0 END) AS opportunity_follow_up_count,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
    GROUP BY tenant_id, actor_principal_id
) follow_up ON follow_up.tenant_id = owner.tenant_id AND follow_up.owner_principal_id = owner.owner_principal_id
LEFT JOIN (
    SELECT tenant_id, owner_principal_id,
           SUM(customer_transfer_in_count) AS customer_transfer_in_count,
           SUM(customer_transfer_out_count) AS customer_transfer_out_count,
           MAX(data_freshness_at) AS data_freshness_at
    FROM (
        SELECT tenant_id, owner_principal_id, customer_transfer_in_count, customer_transfer_out_count, data_freshness_at
        FROM yshopping_dws.dws_canonical_crm_funnel_current
    ) owner_movement
    GROUP BY tenant_id, owner_principal_id
) owner_move ON owner_move.tenant_id = owner.tenant_id
             AND owner_move.owner_principal_id = owner.owner_principal_id;
