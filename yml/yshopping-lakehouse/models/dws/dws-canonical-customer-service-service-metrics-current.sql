CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_customer_service_service_metrics_current AS
WITH ticket_timeline AS (
    SELECT tenant_id,
           ticket_id,
           MIN(occurred_at) AS ticket_created_at,
           MIN(CASE WHEN current_status = 'RESOLVED' THEN occurred_at END) AS first_resolved_at,
           MAX(CASE WHEN current_status = 'CLOSED' THEN occurred_at END) AS last_closed_at,
           SUM(CASE WHEN previous_status IN ('RESOLVED', 'CLOSED') AND current_status = 'OPEN' THEN 1 ELSE 0 END)
               AS reopen_count,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_customer_service_ticket_event
    GROUP BY tenant_id, ticket_id
),
message_timeline AS (
    SELECT tenant_id,
           ticket_id,
           MIN(CASE WHEN direction = 'INBOUND' AND sender_type = 'CUSTOMER' THEN occurred_at END)
               AS first_customer_inbound_at,
           MIN(CASE WHEN direction = 'OUTBOUND' AND sender_type = 'AGENT' THEN occurred_at END)
               AS first_agent_outbound_at,
           MAX(CASE WHEN direction = 'INBOUND' AND sender_type = 'CUSTOMER' THEN occurred_at END)
               AS last_customer_inbound_at,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_customer_service_message_event
    GROUP BY tenant_id, ticket_id
),
feedback_by_ticket AS (
    SELECT tenant_id,
           ticket_id,
           SUM(valid_feedback_count) AS valid_feedback_count,
           SUM(satisfied_feedback_count) AS satisfied_feedback_count,
           SUM(neutral_feedback_count) AS neutral_feedback_count,
           SUM(dissatisfied_feedback_count) AS dissatisfied_feedback_count,
           MAX(latest_feedback_at) AS latest_feedback_at,
           MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_customer_service_buyer_csat_current
    GROUP BY tenant_id, ticket_id
),
fcr_followup AS (
    SELECT ticket.tenant_id,
           ticket.ticket_id,
           COUNT(*) AS followup_count
    FROM yshopping_dim.dim_canonical_customer_service_ticket_current ticket
    JOIN ticket_timeline timeline
      ON timeline.tenant_id = ticket.tenant_id
     AND timeline.ticket_id = ticket.ticket_id
    JOIN yshopping_dwd.dwd_canonical_customer_service_message_event followup
      ON followup.tenant_id = ticket.tenant_id
     AND followup.ticket_id = ticket.ticket_id
     AND followup.direction = 'INBOUND'
     AND followup.sender_type = 'CUSTOMER'
     AND followup.occurred_at > timeline.first_resolved_at
     AND followup.occurred_at <= DATE_ADD(timeline.first_resolved_at, INTERVAL ticket.fcr_window_hours HOUR)
    WHERE ticket.fcr_window_hours IS NOT NULL
      AND timeline.first_resolved_at IS NOT NULL
    GROUP BY ticket.tenant_id, ticket.ticket_id
),
claim_by_ticket AS (
    SELECT tenant_id,
           ticket_id,
           COUNT(*) AS claim_count,
           SUM(CASE WHEN current_status IN ('REQUESTED', 'APPROVED') THEN 1 ELSE 0 END) AS open_claim_count,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_customer_service_claim_current
    GROUP BY tenant_id, ticket_id
)
SELECT ticket.tenant_id,
       ticket.ticket_id,
       ticket.ticket_no,
       ticket.customer_principal_id,
       ticket.channel_code,
       ticket.priority,
       ticket.category_code,
       ticket.sla_policy_code,
       ticket.sla_policy_version,
       ticket.resolution_deadline_at,
       ticket.fcr_window_hours,
       ticket.current_status,
       ticket.primary_order_ref,
       ticket.primary_after_sale_ref,
       timeline.ticket_created_at,
       timeline.first_resolved_at,
       timeline.last_closed_at,
       timeline.reopen_count,
       message.first_customer_inbound_at,
       message.first_agent_outbound_at,
       message.last_customer_inbound_at,
       COALESCE(feedback.valid_feedback_count, 0) AS valid_feedback_count,
       COALESCE(feedback.satisfied_feedback_count, 0) AS satisfied_feedback_count,
       COALESCE(feedback.neutral_feedback_count, 0) AS neutral_feedback_count,
       COALESCE(feedback.dissatisfied_feedback_count, 0) AS dissatisfied_feedback_count,
       feedback.latest_feedback_at,
       COALESCE(claim.claim_count, 0) AS claim_count,
       COALESCE(claim.open_claim_count, 0) AS open_claim_count,
       CASE WHEN ticket.resolution_deadline_at IS NOT NULL AND timeline.first_resolved_at IS NOT NULL THEN 1 ELSE 0 END
           AS resolution_sla_eligible_flag,
       CASE
           WHEN ticket.resolution_deadline_at IS NOT NULL
            AND timeline.first_resolved_at IS NOT NULL
            AND timeline.first_resolved_at <= ticket.resolution_deadline_at
           THEN 1 ELSE 0
       END AS resolution_sla_met_flag,
       CASE WHEN ticket.fcr_window_hours IS NOT NULL AND timeline.first_resolved_at IS NOT NULL THEN 1 ELSE 0 END
           AS fcr_eligible_flag,
       CASE
           WHEN ticket.fcr_window_hours IS NOT NULL
            AND timeline.first_resolved_at IS NOT NULL
            AND timeline.reopen_count = 0
            AND COALESCE(followup.followup_count, 0) = 0
           THEN 1 ELSE 0
       END AS fcr_success_flag,
       CASE
           WHEN ticket.primary_order_ref IS NOT NULL
             AND (
                 COALESCE(feedback.dissatisfied_feedback_count, 0) > 0
                 OR COALESCE(claim.claim_count, 0) > 0
                 OR timeline.reopen_count > 0
             )
           THEN 1 ELSE 0
       END AS order_defect_case_flag,
       GREATEST(
           ticket.recorded_at,
           COALESCE(timeline.data_freshness_at, ticket.recorded_at),
           COALESCE(message.data_freshness_at, ticket.recorded_at),
           COALESCE(feedback.data_freshness_at, ticket.recorded_at),
           COALESCE(claim.data_freshness_at, ticket.recorded_at)
       ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_customer_service_ticket_current ticket
LEFT JOIN ticket_timeline timeline
  ON timeline.tenant_id = ticket.tenant_id
 AND timeline.ticket_id = ticket.ticket_id
LEFT JOIN message_timeline message
  ON message.tenant_id = ticket.tenant_id
 AND message.ticket_id = ticket.ticket_id
LEFT JOIN feedback_by_ticket feedback
  ON feedback.tenant_id = ticket.tenant_id
 AND feedback.ticket_id = ticket.ticket_id
LEFT JOIN fcr_followup followup
  ON followup.tenant_id = ticket.tenant_id
 AND followup.ticket_id = ticket.ticket_id
LEFT JOIN claim_by_ticket claim
  ON claim.tenant_id = ticket.tenant_id
 AND claim.ticket_id = ticket.ticket_id;
