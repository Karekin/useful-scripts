-- Lightweight governed KPI surface for Customer Service & After Sales.
-- Buyer CSAT is buyer-authored feedback only; internal review scores remain
-- outside the metric. FCR and SLA use explicit ticket eligibility flags.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_service_role_metrics AS
WITH service AS (
    SELECT *
    FROM yshopping_ads.ads_canonical_customer_service_service_metrics_readiness
    WHERE readiness_status = 'READY_FOR_ORDER_LINKED_PROXY'
), csat AS (
    SELECT
        tenant_id,
        SUM(satisfied_feedback_count) AS satisfied_feedback_count,
        SUM(valid_feedback_count) AS valid_feedback_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_buyer_csat_readiness
    GROUP BY tenant_id
), metric_rows AS (
    SELECT
        tenant_id,
        'service.first_contact_resolution_rate' AS metric_id,
        first_contact_resolution_rate_percent AS metric_value,
        CAST(fcr_success_ticket_count AS DECIMAL(38,6)) AS numerator,
        CAST(fcr_eligible_ticket_count AS DECIMAL(38,6)) AS denominator,
        'percent' AS unit,
        fcr_eligible_ticket_count AS source_row_count,
        'Eligible resolved tickets closed without reopen or repeated customer contact' AS evidence_note,
        data_freshness_at
    FROM service
    UNION ALL
    SELECT
        tenant_id,
        'service.resolution_sla_rate',
        resolution_sla_rate_percent,
        CAST(resolution_sla_met_ticket_count AS DECIMAL(38,6)),
        CAST(resolution_sla_eligible_ticket_count AS DECIMAL(38,6)),
        'percent',
        resolution_sla_eligible_ticket_count,
        'Resolved tickets completed by their frozen versioned SLA deadline',
        data_freshness_at
    FROM service
    UNION ALL
    SELECT
        tenant_id,
        'service.order_defect_rate',
        metric_value,
        numerator,
        denominator,
        unit,
        source_row_count,
        evidence_note,
        data_freshness_at
    FROM yshopping_ads.ads_canonical_risk_commerce_metrics
    WHERE metric_id = 'service.order_defect_rate'
    UNION ALL
    SELECT
        tenant_id,
        'buyer.csat',
        CAST(satisfied_feedback_count * 100.0 / NULLIF(valid_feedback_count, 0) AS DECIMAL(38,6)),
        CAST(satisfied_feedback_count AS DECIMAL(38,6)),
        CAST(valid_feedback_count AS DECIMAL(38,6)),
        'percent',
        valid_feedback_count,
        'Buyer-authored satisfied feedback divided by valid buyer feedback; internal QA excluded',
        data_freshness_at
    FROM csat
)
SELECT
    tenant_id,
    metric_id,
    metric_value,
    numerator,
    denominator,
    unit,
    'LOCAL_TEST_CANONICAL_CURRENT' AS evidence_scope,
    source_row_count,
    evidence_note,
    data_freshness_at
FROM metric_rows
WHERE metric_value IS NOT NULL;
