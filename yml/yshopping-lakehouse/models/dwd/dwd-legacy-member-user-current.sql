-- Sanitized current-state projection of legacy member rows.
-- PII, credentials, and profile free text stay excluded; this view only supports join coverage.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_member_user_current AS
SELECT
    'yudao-commerce-observability' AS source_system,
    'member_user' AS source_table,
    member.tenant_id,
    member.id AS legacy_member_user_id,
    CONCAT('yudao-commerce-observability:', CAST(member.tenant_id AS STRING), ':member_user:', CAST(member.id AS STRING))
        AS legacy_member_user_key,
    member.status AS legacy_status_code,
    member.register_terminal,
    member.level_id,
    member.group_id,
    member.create_time AS source_created_at,
    member.update_time AS source_updated_at,
    member.deleted AS is_deleted,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.member_user member;
