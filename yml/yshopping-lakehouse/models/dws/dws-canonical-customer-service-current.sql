CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_customer_service_ticket_current AS
SELECT ticket.tenant_id, ticket.ticket_id, ticket.ticket_no, ticket.run_id, ticket.customer_principal_id,
       ticket.channel_code, ticket.priority, ticket.category_code, ticket.current_status,
       ticket.assigned_agent_principal_id, ticket.primary_order_ref, ticket.primary_after_sale_ref,
       ticket.ticket_event_count,
       COALESCE(message.message_count, 0) AS message_count,
       COALESCE(message.declared_attachment_count, 0) AS declared_attachment_count,
       response.first_customer_inbound_at,
       response.first_agent_outbound_at,
       CASE
           WHEN response.first_customer_inbound_at IS NOT NULL
            AND response.first_agent_outbound_at IS NOT NULL
            AND response.first_agent_outbound_at >= response.first_customer_inbound_at
           THEN CAST(
               TIMESTAMPDIFF(SECOND, response.first_customer_inbound_at, response.first_agent_outbound_at)
               / 60.0 AS DECIMAL(38,6)
           )
       END AS first_response_minutes,
       COALESCE(attachment.attachment_count, 0) AS attachment_count,
       COALESCE(attachment.unsafe_attachment_count, 0) AS unsafe_attachment_count,
       COALESCE(review.review_count, 0) AS review_count,
       review.latest_score_basis_points,
       COALESCE(claim.claim_count, 0) AS claim_count,
       COALESCE(claim.open_claim_count, 0) AS open_claim_count,
       COALESCE(claim.requested_amount_minor, 0) AS requested_amount_minor,
       COALESCE(claim.paid_amount_minor, 0) AS paid_amount_minor,
       GREATEST(ticket.recorded_at,
                COALESCE(message.data_freshness_at, ticket.recorded_at),
                COALESCE(response.data_freshness_at, ticket.recorded_at),
                COALESCE(attachment.data_freshness_at, ticket.recorded_at),
                COALESCE(review.data_freshness_at, ticket.recorded_at),
                COALESCE(claim.data_freshness_at, ticket.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_customer_service_ticket_current ticket
LEFT JOIN (
    SELECT tenant_id, ticket_id, COUNT(*) AS message_count,
           SUM(attachment_count) AS declared_attachment_count, MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_customer_service_message_event GROUP BY tenant_id, ticket_id
) message ON message.tenant_id = ticket.tenant_id AND message.ticket_id = ticket.ticket_id
LEFT JOIN (
    SELECT
        inbound.tenant_id,
        inbound.ticket_id,
        inbound.first_customer_inbound_at,
        MIN(outbound.occurred_at) AS first_agent_outbound_at,
        GREATEST(
            inbound.data_freshness_at,
            COALESCE(MAX(outbound.recorded_at), inbound.data_freshness_at)
        ) AS data_freshness_at
    FROM (
        SELECT
            tenant_id,
            ticket_id,
            MIN(occurred_at) AS first_customer_inbound_at,
            MAX(recorded_at) AS data_freshness_at
        FROM yshopping_dwd.dwd_canonical_customer_service_message_event
        WHERE direction = 'INBOUND'
          AND sender_type = 'CUSTOMER'
          AND occurred_at <= CURRENT_TIMESTAMP()
        GROUP BY tenant_id, ticket_id
    ) inbound
    LEFT JOIN yshopping_dwd.dwd_canonical_customer_service_message_event outbound
      ON outbound.tenant_id = inbound.tenant_id
     AND outbound.ticket_id = inbound.ticket_id
     AND outbound.direction = 'OUTBOUND'
     AND outbound.sender_type = 'AGENT'
     AND outbound.occurred_at >= inbound.first_customer_inbound_at
     AND outbound.occurred_at <= CURRENT_TIMESTAMP()
    GROUP BY inbound.tenant_id, inbound.ticket_id, inbound.first_customer_inbound_at, inbound.data_freshness_at
) response ON response.tenant_id = ticket.tenant_id AND response.ticket_id = ticket.ticket_id
LEFT JOIN (
    SELECT tenant_id, ticket_id, COUNT(*) AS attachment_count,
           SUM(CASE WHEN malware_scan_status <> 'CLEAN' THEN 1 ELSE 0 END) AS unsafe_attachment_count,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_customer_service_attachment_event GROUP BY tenant_id, ticket_id
) attachment ON attachment.tenant_id = ticket.tenant_id AND attachment.ticket_id = ticket.ticket_id
LEFT JOIN (
    SELECT tenant_id, ticket_id, COUNT(*) AS review_count,
           MAX(score_basis_points) AS latest_score_basis_points, MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_customer_service_quality_review_event GROUP BY tenant_id, ticket_id
) review ON review.tenant_id = ticket.tenant_id AND review.ticket_id = ticket.ticket_id
LEFT JOIN (
    SELECT tenant_id, ticket_id, COUNT(*) AS claim_count,
           SUM(CASE WHEN current_status IN ('REQUESTED','APPROVED') THEN 1 ELSE 0 END) AS open_claim_count,
           SUM(requested_amount_minor) AS requested_amount_minor,
           SUM(COALESCE(paid_amount_minor, 0)) AS paid_amount_minor,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_customer_service_claim_current GROUP BY tenant_id, ticket_id
) claim ON claim.tenant_id = ticket.tenant_id AND claim.ticket_id = ticket.ticket_id;
