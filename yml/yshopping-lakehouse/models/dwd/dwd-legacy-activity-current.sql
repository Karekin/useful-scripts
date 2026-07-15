-- Bounded union of six legacy promotion activity tables at current-row grain.
-- Source-qualified keys are not canonical activity IDs, events, or SCD2 history.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_activity_current AS
SELECT 'yudao-mall' AS source_system, 'promotion_bargain_activity' AS source_table,
       tenant_id, id AS legacy_activity_id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_bargain_activity:', CAST(id AS STRING)) AS legacy_activity_key,
       'BARGAIN' AS activity_kind, name AS activity_name, status AS activity_status_code,
       spu_id AS legacy_spu_id, sku_id AS legacy_sku_id, start_time, end_time,
       TRUE AS time_window_applicable, CAST(NULL AS VARCHAR(255)) AS remark,
       create_time AS source_created_at, update_time AS source_updated_at, deleted AS is_deleted,
       start_time >= end_time AS invalid_time_window_flag,
       'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.promotion_bargain_activity
UNION ALL
SELECT 'yudao-mall', 'promotion_combination_activity', tenant_id, id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_combination_activity:', CAST(id AS STRING)),
       'COMBINATION', name, status, spu_id, CAST(NULL AS BIGINT), start_time, end_time,
       TRUE, CAST(NULL AS VARCHAR(255)), create_time, update_time, deleted,
       start_time >= end_time, 'LEGACY_CURRENT_STATE_ROW'
FROM yshopping_ods.promotion_combination_activity
UNION ALL
SELECT 'yudao-mall', 'promotion_discount_activity', tenant_id, id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_discount_activity:', CAST(id AS STRING)),
       'DISCOUNT', name, status, CAST(NULL AS BIGINT), CAST(NULL AS BIGINT), start_time, end_time,
       TRUE, remark, create_time, update_time, deleted,
       start_time >= end_time, 'LEGACY_CURRENT_STATE_ROW'
FROM yshopping_ods.promotion_discount_activity
UNION ALL
SELECT 'yudao-mall', 'promotion_point_activity', tenant_id, id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_point_activity:', CAST(id AS STRING)),
       'POINT', CAST(NULL AS VARCHAR(255)), status, spu_id, CAST(NULL AS BIGINT),
       CAST(NULL AS DATETIME), CAST(NULL AS DATETIME), FALSE, remark,
       create_time, update_time, deleted, FALSE, 'LEGACY_CURRENT_STATE_ROW'
FROM yshopping_ods.promotion_point_activity
UNION ALL
SELECT 'yudao-mall', 'promotion_reward_activity', tenant_id, id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_reward_activity:', CAST(id AS STRING)),
       'REWARD', name, status, CAST(NULL AS BIGINT), CAST(NULL AS BIGINT), start_time, end_time,
       TRUE, remark, create_time, update_time, deleted,
       start_time >= end_time, 'LEGACY_CURRENT_STATE_ROW'
FROM yshopping_ods.promotion_reward_activity
UNION ALL
SELECT 'yudao-mall', 'promotion_seckill_activity', tenant_id, id,
       CONCAT('yudao-mall:', CAST(tenant_id AS STRING), ':promotion_seckill_activity:', CAST(id AS STRING)),
       'SECKILL', name, status, spu_id, CAST(NULL AS BIGINT), start_time, end_time,
       TRUE, remark, create_time, update_time, deleted,
       start_time >= end_time, 'LEGACY_CURRENT_STATE_ROW'
FROM yshopping_ods.promotion_seckill_activity;
