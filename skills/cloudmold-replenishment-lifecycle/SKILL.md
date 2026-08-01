---
name: cloudmold-replenishment-lifecycle
description: Produce governed replenishment recommendations, controlled procurement or transfer drafts, and inventory readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: supply-chain
    role: replenishment-operator
---

# 补货运营

用于生成补货建议、采购或调拨草稿并回读库存变化。执行前读取同目录 `skill-task.json`；供应商 OTIF 和规范收货以供应商、采购和仓储系统事实为准。
