---
name: cloudmold-data-quality-recovery
description: Diagnose governed data-quality failures, trace lineage, create recovery actions, and verify recovery evidence.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: risk-data
    role: data-ai-operations
---

# 数据质量与 AI 运营

用于执行 DQC、血缘核验、问题归因和恢复行动。执行前读取同目录 `skill-task.json`；生产湖仓作业和真实经营指标必须由数据平台回读，Agent 只输出可审计的发现、行动和待确认事项。
