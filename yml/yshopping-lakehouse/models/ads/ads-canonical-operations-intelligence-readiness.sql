-- Canonical replacement for the visual-only ads_ai_intelligence_target surface.
CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_ai_intelligence_readiness AS
SELECT tenant_id, COUNT(*) AS observation_count,
       SUM(model_result_count) AS model_result_count,
       SUM(succeeded_model_result_count) AS succeeded_model_result_count,
       SUM(clue_count) AS clue_count,
       SUM(accepted_clue_count) AS accepted_clue_count,
       SUM(rejected_clue_count) AS rejected_clue_count,
       SUM(pending_clue_count) AS pending_clue_count,
       CASE WHEN SUM(clue_count) = SUM(accepted_clue_count + rejected_clue_count) THEN 'HUMAN_REVIEW_GOVERNED'
            ELSE 'REVIEW_PENDING' END AS readiness_status,
       false AS raw_content_stored,
       false AS automatic_enforcement_enabled
FROM yshopping_dws.dws_canonical_intelligence_observation_current
GROUP BY tenant_id;

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_operations_alert_readiness AS
SELECT tenant_id, COUNT(*) AS alert_count,
       SUM(CASE WHEN current_status IN ('OPEN','NOTIFIED','CLAIMED') THEN 1 ELSE 0 END) AS active_alert_count,
       SUM(CASE WHEN current_status IN ('RESOLVED','INVALID','CLOSED_NO_ACTION') THEN 1 ELSE 0 END) AS terminal_alert_count,
       SUM(invalid_source_count) AS invalid_source_count,
       SUM(CASE WHEN alert_event_count <> aggregate_version THEN 1 ELSE 0 END) AS history_sequence_gap_count,
       CASE WHEN SUM(invalid_source_count) = 0
                  AND SUM(CASE WHEN alert_event_count <> aggregate_version THEN 1 ELSE 0 END) = 0
            THEN 'GOVERNED_ALERT_LIFECYCLE_READY' ELSE 'INCONSISTENT' END AS readiness_status,
       false AS automatic_enforcement_enabled
FROM yshopping_dws.dws_canonical_operations_alert_current
GROUP BY tenant_id;
