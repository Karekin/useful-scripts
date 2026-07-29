---
name: cloudmold-commerce-full-chain
description: Compose one fresh product-to-listing run with compatibility projection, a fresh governed order-to-return run, and terminal authority readback through registered SkillTask children. Use as an internal local/test proof and reusable parent capability; it is not a standalone business-role workflow or an independently scheduled operator.
---

# CloudMold Commerce HSF Full Chain

This Skill is the canonical internal composition entrypoint for the product-level commerce chain. Its implementation, scenarios, and tests are owned below this directory; the Obsidian project Skill is documentation/discovery only and is not a runtime dependency. The definition is `INTERNAL_SUBFLOW`: business-role schedules invoke the role owners that compose it, rather than scheduling this technical parent as another operator.

## Contract

- Transport is Dubbo only. The runner sets `CLOUDMOLD_INTERNAL_TRANSPORT=dubbo`; a REST/OpenAPI fallback is forbidden.
- Start the Provider, Nacos, MySQL, Redis, Kafka, Flink, and StarRocks base stack before execute. One-shot Agent Executors use `--no-deps` and never recreate that stack.
- Resolve a real ACTIVE System user and ERP warehouse source ID. Merchant, Shop, OWNER assignment, Warehouse, Zone, and Location are built as the governed prerequisite flow; never use `internal-company` or `internal-shop`.
- Writes are limited to `local`, `demo`, or `test`. Evidence is retained under `~/.cloudmold/runs`; do not delete refunded/returned business evidence.
- A successful `1.3.0` run must finish with a fresh Catalog product ACTIVE, its Listing PUBLISHED, 18 compatibility projections, a fresh Order RETURNED, Payment REFUNDED, positive Fulfillment DELIVERED, AfterSale COMPLETED, Resolution Saga COMPLETED, returned stock restored, and the terminal authority readback successful. Outbox/CDC/lakehouse reconciliation remains an external acceptance gate and must not be claimed merely because the persisted SkillTask parent succeeded.

## Run

Plan without writes:

```bash
python3 scripts/run_hsf_full_chain.py --mode plan --run-id <6-20-char-id>
```

Execute in local/test:

```bash
python3 scripts/run_hsf_full_chain.py \
  --mode execute \
  --run-id <6-20-char-id> \
  --system-admin-source-id <active-system-user-id> \
  --erp-warehouse-source-id <active-erp-warehouse-id>
```

The parent runner is `scripts/yshopping_aftersales_vertical_runner.py`. It composes the child runners and writes an atomic parent ledger before business mutation. Read `references/scenarios/yshopping-aftersales-vertical-v1.json` when changing the flow.

For the durable R3 path, generate the exact approved task input from compact source identities:

```bash
python3 scripts/build_skill_task_input.py \
  --run-id <6-20-char-id> \
  --system-admin-source-id <active-system-user-id> \
  --erp-warehouse-source-id <active-erp-warehouse-id> \
  --output <full-chain-input.json>
```

Submit that file only through the fixed MCP tool for `skill.cloudmold.commerce.full-chain-hsf.v1@1.3.0`. The durable parent composes four registered child definitions in dependency order: product-to-listing `1.1.0`, legacy projection plan `1.2.0`, AfterSale operator artery `1.4.0`, and terminal readback `1.2.0`. Product-to-listing owns fresh Catalog, governed Merchant/Warehouse prerequisites, and Listing publication; AfterSale owns only the fresh positive order, delivery, reverse logistics, AI disposition, inspection, refund, and restock artery. The parent and child ledgers, not the DeerFlow session, own resumption and idempotency.

## Accept evidence

Accept a run only when the parent ledger is `SUCCEEDED`, the trace contains no HTTP business fallback, all intended commands replay as duplicates, the same occurrence-created canonical SKU is present from Catalog through AfterSale, no Listing write occurs inside the AfterSale child, and post-write reconciliation is read-only. Use `cloudmold-full-chain-qa` afterward to refresh live coverage; a successful vertical does not by itself clear unrelated capability gaps.

After a successful parent run, execute `scripts/run_hsf_readback.py` with the successful Catalog, Merchant/Warehouse, and AfterSale child ledgers. The readback flow calls the terminal Query/Validation ports for the same exact product and identities; it must not synthesize IDs or perform writes.

For a durable R3 run, also execute `lakehousectl reconcile-canonical-aftersales --tenant <tenant> --run-id <run-id>-aftersale`. Accept only a non-empty `RECONCILED` row with exact quantity and money conservation, after the Outbox CDC job has a successful checkpoint. This lakehouse check is currently an external read-only acceptance gate; it is not yet a sixth persisted SkillTask child.
