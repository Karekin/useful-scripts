---
name: cloudmold-dreamplant-knowledge
description: Build and verify the DreamPlant knowledge-graph learning loop entirely through governed Dubbo capabilities. It binds a real canonical CloudMold product to its HSF capability, evidence, KPI, CDC checkpoint, drift and autonomous exploration, without REST or UI orchestration.
---
# CloudMold DreamPlant Knowledge

This Skill turns one product's retained full-chain evidence into a DreamPlant knowledge-graph node and proves the AI-facing control plane over Dubbo.

## Contract

- Transport is Dubbo only. REST/OpenAPI and browser routes are not accepted as business evidence.
- Inputs must come from retained, successful Merchant/Warehouse and Catalog ledgers.
- The graph stores opaque references and hashes; it never copies credentials, customer PII, or ERP transaction payloads.
- Every write carries a stable idempotency key, run trace, optimistic version and governed source/evidence reference.
- The Skill owns orchestration only. DreamPlant and the source domains remain authoritative for validation and state transitions.

## Execute

```bash
python3 scripts/run_hsf_knowledge_chain.py \
  --master-ledger ~/.cloudmold/runs/merchant-warehouse/<run-id>/ledger.json \
  --catalog-ledger ~/.cloudmold/runs/catalog/<run-id>/ledger.json \
  --run-id <run-id> \
  --tenant-id 1 --operator-id 1 --operator-type 1
```

The retained ledger is written below `~/.cloudmold/runs/dreamplant-knowledge/<run-id>/run.json` and must finish `SUCCEEDED`. A valid run proves asset and relation writes, evidence/KPI/sync/drift learning records, their typed reads, world-map projection publication, exploration submission, worker dispatch and terminal exploration readback.

## Acceptance

Accept the run only when all 25 live DreamPlant capability IDs have at least one successful HSF invocation, the graph product ID points to the same canonical SKU as the Catalog ledger, the public and tenant projections are readable, and the submitted exploration becomes `SUCCEEDED`.
