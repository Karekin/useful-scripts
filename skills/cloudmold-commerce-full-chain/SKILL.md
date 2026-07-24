---
name: cloudmold-commerce-full-chain
description: Execute one canonical product through Catalog, yudao compatibility projection, Merchant/Shop and Warehouse authority, Listing, Inventory, Order, Payment, Fulfillment, AfterSale, refund, return-to-stock, Outbox, CDC, lakehouse reconciliation, and DQC using governed Dubbo capabilities only. Use for local/test full-chain business proof, immutable replay, HSF dyeing, or AI orchestration without a UI or HTTP business endpoint.
---

# CloudMold Commerce HSF Full Chain

This Skill is the canonical entrypoint for the product-level commerce chain. Its implementation, scenarios, and tests are owned below this directory; the Obsidian project Skill is documentation/discovery only and is not a runtime dependency.

## Contract

- Transport is Dubbo only. The runner sets `CLOUDMOLD_INTERNAL_TRANSPORT=dubbo`; a REST/OpenAPI fallback is forbidden.
- Start the Provider, Nacos, MySQL, Redis, Kafka, Flink, and StarRocks base stack before execute. One-shot Agent Executors use `--no-deps` and never recreate that stack.
- Resolve a real ACTIVE System user and ERP warehouse source ID. Merchant, Shop, OWNER assignment, Warehouse, Zone, and Location are built as the governed prerequisite flow; never use `internal-company` or `internal-shop`.
- Writes are limited to `local`, `demo`, or `test`. Evidence is retained under `~/.cloudmold/runs`; do not delete refunded/returned business evidence.
- A successful run must finish with Catalog ACTIVE, 18 compatibility projections, Listing PUBLISHED, Fulfillment DELIVERED, AfterSale COMPLETED, Resolution Saga COMPLETED, Payment REFUNDED, Order RETURNED, returned stock restored, immutable command replay, published Outbox, CDC checkpoint, exact lakehouse reconciliation, and zero DQC violations.

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

Submit that file only through the fixed MCP tool for `skill.cloudmold.commerce.full-chain-hsf.v1@1.2.0`. The durable parent composes five registered child definitions in dependency order: Catalog matrix, legacy projection plan, governed master data, AfterSale Saga, and terminal readback. The parent and child ledgers, not the DeerFlow session, own resumption and idempotency.

## Accept evidence

Accept a run only when the parent ledger is `SUCCEEDED`, the HSF trace contains no HTTP transport, all intended commands replay as duplicates, the same canonical SKU is present from Catalog through AfterSale, and post-write reconciliation is read-only. Use `cloudmold-full-chain-qa` afterward to refresh live HSF coverage; a successful vertical does not by itself clear unrelated capability gaps.

After a successful parent run, execute `scripts/run_hsf_readback.py` with the successful Catalog, Merchant/Warehouse, and AfterSale child ledgers. The readback flow calls the terminal Query/Validation ports for the same exact product and identities; it must not synthesize IDs or perform writes.

For a durable R3 run, also execute `lakehousectl reconcile-canonical-aftersales --tenant <tenant> --run-id <run-id>-aftersale`. Accept only a non-empty `RECONCILED` row with exact quantity and money conservation, after the Outbox CDC job has a successful checkpoint. This lakehouse check is currently an external read-only acceptance gate; it is not yet a sixth persisted SkillTask child.
