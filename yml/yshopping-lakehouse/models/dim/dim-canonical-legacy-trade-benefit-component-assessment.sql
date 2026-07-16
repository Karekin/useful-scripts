CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_benefit_component_assessment AS
SELECT
    event.tenant_id,
    event.migration_run_id,
    event.candidate_id,
    event.legacy_order_id,
    event.legacy_order_no,
    event.assessment_status AS order_assessment_status,
    get_json_string(component.`value`, '$.component_id') AS component_id,
    get_json_string(component.`value`, '$.component_type') AS component_type,
    CAST(get_json_string(component.`value`, '$.amount_minor') AS BIGINT) AS component_amount_minor,
    get_json_string(component.`value`, '$.source_reference') AS source_reference,
    get_json_string(component.`value`, '$.identity_resolution_status') AS identity_resolution_status,
    get_json_string(component.`value`, '$.funding_resolution_status') AS funding_resolution_status,
    CAST(get_json_string(component.`value`, '$.canonical_import_allowed') AS BOOLEAN)
        AS canonical_import_allowed,
    event.source_updated_at,
    event.assessed_at
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event event,
     LATERAL json_each(event.components) component;
