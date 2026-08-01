---
name: cloudmold-crossborder-fulfillment-compliance-lifecycle
description: Coordinate governed cross-border order, logistics, document, compliance-exception, and readback steps.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: fulfillment
    role: crossborder-operations
---

# 跨境运营

用于编排跨境订单、物流、单证和合规异常。执行前读取同目录 `skill-task.json` 并按冻结定义运行；承运商轨迹、税务结果和通关回执是外部事实门禁，缺失时必须反馈缺口而不是推断成功。
