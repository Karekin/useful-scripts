---
name: cloudmold-quality-inspection-recall-lifecycle
description: Coordinate governed quality inspection, CAPA, recall, inventory isolation, and terminal evidence readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: quality
    role: quality-operations
---

# 质量运营

用于质检、CAPA、召回和库存隔离编排。执行前读取同目录 `skill-task.json`；外部实验室结果和全量批次追溯属于权威事实，质量写操作必须保留审批和证据链。
