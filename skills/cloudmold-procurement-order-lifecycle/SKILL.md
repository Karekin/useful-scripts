---
name: cloudmold-procurement-order-lifecycle
description: Create governed procurement orders, collect supplier confirmation, and verify purchasing terminal states.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: supply-chain
    role: procurement-order-operator
---

# 采购订单运营

用于采购订单下发、供应商确认和状态回读。执行前读取同目录 `skill-task.json`；实物收货和供应商绩效必须由采购、仓储或供应商权威渠道提供，不得由 Agent 模拟成真实事实。
