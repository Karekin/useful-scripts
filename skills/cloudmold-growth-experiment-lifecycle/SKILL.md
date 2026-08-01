---
name: cloudmold-growth-experiment-lifecycle
description: Configure governed growth experiments, controlled assignment, observation, and attribution readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: growth-marketing
    role: growth-experiment-operator
---

# 增长实验运营

用于实验配置、受控分流、效果观测和归因回读。执行前读取同目录 `skill-task.json`；媒体增量归因和真实实验结论不能由 Agent 自证，必须引用权威数据和审批结果。
