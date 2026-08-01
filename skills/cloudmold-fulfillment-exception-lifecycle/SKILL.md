---
name: cloudmold-fulfillment-exception-lifecycle
description: Detect governed fulfillment exceptions, coordinate recovery actions, and verify order and logistics terminal states.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: fulfillment
    role: logistics-operations
---

# 物流运营

用于发现履约异常、创建处置动作并回读订单和物流状态。执行前读取同目录 `skill-task.json`；实时轨迹和签收事实以承运商权威回执为准，缺少证据时保持待处理状态。
