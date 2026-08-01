---
name: cloudmold-pricing-reprice-lifecycle
description: Evaluate and execute governed repricing for eligible published offers with approval and immutable revision readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: pricing
    role: pricing-revenue-operator
---

# 定价与收益运营

用于对符合条件的已发布商品执行受控调价并回读不可变报价版本。执行前读取同目录 `skill-task.json`；成本、税费、毛利目标和收益归因是外部输入，缺失时只能提出调价建议。
