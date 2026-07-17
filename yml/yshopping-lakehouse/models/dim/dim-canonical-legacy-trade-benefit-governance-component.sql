CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_benefit_governance_component AS
SELECT
    event.tenant_id,
    event.governance_run_id,
    event.source_migration_run_id,
    event.candidate_id,
    event.legacy_order_id,
    get_json_string(component.`value`, '$.component_governance_id') AS component_governance_id,
    get_json_string(component.`value`, '$.component_id') AS component_id,
    get_json_string(component.`value`, '$.component_type') AS component_type,
    CAST(get_json_string(component.`value`, '$.component_amount_minor') AS BIGINT) AS component_amount_minor,
    get_json_string(component.`value`, '$.source_reference') AS source_reference,
    get_json_string(component.`value`, '$.source_component_evidence_hash') AS source_component_evidence_hash,
    get_json_string(component.`value`, '$.current_reference_status') AS current_reference_status,
    get_json_string(component.`value`, '$.observed_source_table') AS observed_source_table,
    CAST(get_json_string(component.`value`, '$.observed_source_id') AS BIGINT) AS observed_source_id,
    CAST(REPLACE(SUBSTR(get_json_string(component.`value`, '$.observed_source_created_at'), 1, 19), 'T', ' ')
        AS DATETIME) AS observed_source_created_at,
    CAST(REPLACE(SUBSTR(get_json_string(component.`value`, '$.observed_source_updated_at'), 1, 19), 'T', ' ')
        AS DATETIME) AS observed_source_updated_at,
    get_json_string(component.`value`, '$.observed_source_status') AS observed_source_status,
    CAST(get_json_string(component.`value`, '$.observed_source_deleted') AS BOOLEAN) AS observed_source_deleted,
    CAST(get_json_string(component.`value`, '$.observed_source_spu_id') AS BIGINT) AS observed_source_spu_id,
    get_json_string(component.`value`, '$.current_reference_snapshot_hash') AS current_reference_snapshot_hash,
    get_json_string(component.`value`, '$.identity_qualification_id') AS identity_qualification_id,
    get_json_string(component.`value`, '$.historical_identity_status') AS historical_identity_status,
    CAST(get_json_string(component.`value`, '$.funding_share_count') AS BIGINT) AS funding_share_count,
    CAST(get_json_string(component.`value`, '$.funding_amount_minor') AS BIGINT) AS funding_amount_minor,
    get_json_string(component.`value`, '$.funding_resolution_status') AS funding_resolution_status,
    get_json_string(component.`value`, '$.governance_status') AS governance_status,
    json_query(component.`value`, '$.blocker_codes') AS blocker_codes,
    CAST(get_json_string(component.`value`, '$.governance_admission_allowed') AS BOOLEAN)
        AS governance_admission_allowed,
    CAST(get_json_string(component.`value`, '$.canonical_import_allowed') AS BOOLEAN) AS canonical_import_allowed,
    get_json_string(component.`value`, '$.evidence_hash') AS evidence_hash,
    event.assessed_at
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_governance_event event,
     LATERAL json_each(event.components) component;
