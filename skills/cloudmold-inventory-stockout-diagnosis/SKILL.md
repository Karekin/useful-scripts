---
name: cloudmold-inventory-stockout-diagnosis
description: Diagnose apparel color-size stockout risk from canonical Catalog and Inventory facts through the durable CloudMold Skill Task control plane. Use for inventory-control role work that needs a deterministic P1/P2/P3 size-gap result without exposing RPC or SkillTask parameters in the role conversation.
---

# CloudMold Inventory Stockout Diagnosis

Run the governed R1 diagnosis only after Agent Control has created and assigned
an inventory-control work order. The role Agent supplies business intent; the
server-side ActionAssembler freezes tenant, operator, run, replay key, input,
Skill identity, and execution binding.

## Business input

The business request identifies the apparel style or SKU scope and optional
stockout thresholds. Do not accept tenant, operator, approval, idempotency, RPC,
or raw SkillTask fields from the model or browser.

## Execute

Use `skill-task.json` with:

- skill ID `skill.cloudmold.inventory.stockout-diagnosis.v1`
- version `1.0.0`
- R1 read-only risk
- capability `InventoryStockoutDiagnosisQueryApi.diagnose`

The query joins active Catalog color-size facts with Inventory v3 balances and
must include active SKUs whose balance row has not yet been created.

## Verify

Require a `SUCCEEDED` terminal task, matching definition/input hashes, an
accepted Agent Control execution binding, and a business result containing the
diagnosed P1/P2/P3 facts. Replaying the same frozen request must not create a
second task or result.

Fail closed on missing role grant, changed work-order input, cross-tenant facts,
unknown technical fields, non-terminal execution proof, or absent Catalog
identity. This Skill never creates procurement, transfer, price, or customer
effects.
