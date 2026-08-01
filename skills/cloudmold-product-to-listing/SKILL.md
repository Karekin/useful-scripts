---
name: cloudmold-product-to-listing
description: Publish governed, readiness-approved products to controlled listing channels and verify channel receipts.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: product
    role: product-listing-operator
---

# 商品铺品运营

用于将已满足商品、质量和素材条件的商品发布到受控渠道。执行前读取同目录 `skill-task.json`；真实渠道刊登和素材生产以外部回执为准，未满足门禁时只能返回缺口清单。
