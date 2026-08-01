---
name: cloudmold-supply-planning-sop-lifecycle
description: Generate governed demand forecasts, S&OP proposals, supply-demand plans, and planning evidence.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: supply-chain
    role: supply-planning-manager
---

# 需求计划经理

用于预测、S&OP 和供需计划生成与回读。执行前读取同目录 `skill-task.json`；真实全量数据仓和跨部门供需平衡是外部事实，Agent 输出的是可审批计划而不是最终经营承诺。
