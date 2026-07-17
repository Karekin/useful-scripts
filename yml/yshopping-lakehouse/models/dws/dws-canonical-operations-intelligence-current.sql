CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_intelligence_observation_current AS
SELECT observation.tenant_id, observation.observation_id, observation.source_system, observation.source_event_id,
       observation.observation_type, observation.subject_type, observation.subject_ref, observation.observed_at,
       COALESCE(model_result.model_result_count, 0) AS model_result_count,
       COALESCE(model_result.succeeded_model_result_count, 0) AS succeeded_model_result_count,
       COALESCE(clue.clue_count, 0) AS clue_count,
       COALESCE(clue.accepted_clue_count, 0) AS accepted_clue_count,
       COALESCE(clue.rejected_clue_count, 0) AS rejected_clue_count,
       COALESCE(clue.pending_clue_count, 0) AS pending_clue_count
FROM yshopping_dim.dim_canonical_intelligence_observation_current observation
LEFT JOIN (
    SELECT tenant_id, observation_id, COUNT(*) AS model_result_count,
           SUM(CASE WHEN outcome_code = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded_model_result_count
    FROM yshopping_dim.dim_canonical_intelligence_model_result_current GROUP BY tenant_id, observation_id
) model_result ON model_result.tenant_id = observation.tenant_id
              AND model_result.observation_id = observation.observation_id
LEFT JOIN (
    SELECT tenant_id, observation_id, COUNT(*) AS clue_count,
           SUM(CASE WHEN current_status = 'ACCEPTED' THEN 1 ELSE 0 END) AS accepted_clue_count,
           SUM(CASE WHEN current_status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_clue_count,
           SUM(CASE WHEN current_status = 'OBSERVED' THEN 1 ELSE 0 END) AS pending_clue_count
    FROM yshopping_dim.dim_canonical_intelligence_clue_current GROUP BY tenant_id, observation_id
) clue ON clue.tenant_id = observation.tenant_id AND clue.observation_id = observation.observation_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_operations_alert_current AS
SELECT alert_state.tenant_id, alert_state.alert_id, alert_state.alert_code, alert_state.source_type,
       alert_state.source_ref, alert_state.severity, alert_state.category, alert_state.subcategory,
       alert_state.current_status, alert_state.actor_principal_id, alert_state.aggregate_version,
       alert_state.alert_event_count,
       CASE WHEN alert_state.source_type = 'OBSERVATION' AND observation.observation_id IS NULL THEN 1
            WHEN alert_state.source_type = 'CLUE' AND (clue.clue_id IS NULL OR clue.current_status <> 'ACCEPTED') THEN 1
            ELSE 0 END AS invalid_source_count,
       false AS automatic_enforcement_enabled
FROM yshopping_dim.dim_canonical_operations_alert_current alert_state
LEFT JOIN yshopping_dim.dim_canonical_intelligence_observation_current observation
  ON alert_state.source_type = 'OBSERVATION' AND observation.tenant_id = alert_state.tenant_id
 AND observation.observation_id = alert_state.source_ref
LEFT JOIN yshopping_dim.dim_canonical_intelligence_clue_current clue
  ON alert_state.source_type = 'CLUE' AND clue.tenant_id = alert_state.tenant_id AND clue.clue_id = alert_state.source_ref;
