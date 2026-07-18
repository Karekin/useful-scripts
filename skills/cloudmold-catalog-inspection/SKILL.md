---
name: cloudmold-catalog-inspection
description: Inspect one active canonical CloudMold apparel SKU through the durable Skill Task control plane and typed Dubbo/HSF capability. Use when an Agent must verify Catalog identity, status, apparel attributes, or barcode projection without using HTTP, a page, or a direct database query.
---

# CloudMold Catalog Inspection

Submit a governed R1 task to read one ACTIVE canonical SKU. Keep DeerFlow and
MCP on the control plane; let the persistent Skill Task Executor invoke Dubbo
and retain step, lease, result-hash, and audit evidence in MySQL.

## Input

Require a positive tenant and authenticated operator plus:

```json
{"skuId":"<canonical UUID>"}
```

Use a stable `clientRequestKey` for replay. The same key and input must return
the original task; a changed input must fail closed.

## Execute

Use `skill-task.json` with:

- skill ID `skill.cloudmold.catalog.inspect-active-sku.v1`
- version `1.0.0`
- risk `R1`; no write approval is permitted or required
- capability `CatalogSkuProjectionApi.getActiveSku`

Submit, query, and list steps only through typed Skill Task Dubbo APIs. Never
replace the internal path with REST/OpenAPI or read Catalog tables directly.

## Verify

Require terminal task state `SUCCEEDED`, step state `SUCCEEDED`, non-empty
request/result SHA-256 values, the requested canonical `skuId`, ACTIVE Catalog
status, and a durable history sequence. Re-submit the same request key and
confirm no extra task or step is created.

Fail closed on tenant ambiguity, missing/non-ACTIVE SKU, changed replay input,
unsigned RPC context, unavailable provider, or missing checkpoint evidence.
