# Y Shopping lakehouse core

This is the first production-shaped local data path for CloudMold:

`yudao MySQL -> Flink 2.2.1 + Flink CDC 3.6.0 -> StarRocks 4.0.12`

It deliberately excludes the old experimental Airflow, Spark, Trino, MLflow,
Amoro, arbitrary-SQL API and Docker-socket services. Paimon and object storage
are a second-stage addition after CDC recovery, reconciliation and history
retention requirements are proven.

## Start

1. Start `yudao-mysql` and `yudao-redis` from `../yudao/docker-compose.yaml`.
2. Create a least-privilege MySQL CDC account (see below).
3. Copy `.env.example` to `.env` and replace the local CDC password.
4. Run `docker compose up -d --build starrocks jobmanager taskmanager`.
5. Run `docker compose --profile tools run --rm cdc-cli` once to submit the job.

The local UIs are StarRocks FE on port 8030 and Flink on port 8081.

## Governed procurement and inventory slice

The first executable vertical slice now has a versioned contract, current
dimensions, DWD line/movement facts, DWS summaries, ADS views and invariant
tests. Operate it through one entry point:

```bash
./scripts/lakehousectl config-check
./scripts/lakehousectl contract-test
./scripts/lakehousectl submit-catalog-cdc
./scripts/lakehousectl submit-event-cdc
./scripts/lakehousectl apply-models
./scripts/lakehousectl health
./scripts/lakehousectl test
./scripts/lakehousectl reconcile --tenant 1 --run-id <erp-scenario-run-id>
./scripts/lakehousectl reconcile-canonical-commerce-v2 --tenant 1 --run-id <commerce-v2-run-id>
./scripts/lakehousectl reconcile-canonical-paid-cancellation-saga --tenant 1 --run-id <paid-cancellation-run-id>
./scripts/lakehousectl reconcile-canonical-aftersales --tenant 1 --run-id <aftersales-run-id>
```

The models intentionally call `erp_product` an ERP projection. Canonical apparel
SPU/SKU is sourced from the Mall catalog through a separate Catalog CDC job;
`product_sku.stock` remains a legacy sales field and is not promoted as the
inventory-ledger authority. The current ODS is
a primary-key mirror: soft deletion is visible, but hard deletion does not leave
a tombstone and the current dimensions are not SCD2. See
`contracts/erp-procurement-inventory-v1.yaml` for the governed contract and
known limits.

## Canonical Listing, fulfillment and commerce v2

The commerce-v2 slice preserves the existing commerce-v1 views and adds the
governed channel-publication and physical-fulfillment facts required by the
Y-Shopping flow. `order.status.changed` v1 and v2 contracts coexist. V2 freezes
the exact Listing offer identity, revision/version, channel, shop, SKU, price
and currency on every order item. Fulfillment then links the same order item and
Inventory reservation through shipment and delivery milestones.

The happy path is deliberately exact:

- Listing: 6 status events plus 3 review events, ending `PUBLISHED/v6`.
- Inventory: 4 events (`TEST_FIXTURE` receipt, reserve, ship, return), ending
  `10/0/10/v4`.
- Order: 7 v2 events, ending `RETURNED/v7`.
- Payment: 2 events, ending `REFUNDED/v2`.
- Fulfillment: 4 events, ending `DELIVERED/v4`.
- 23 public business commands replay as duplicates. Including 16 Catalog
  events, the full vertical produces 42 Outbox events; the Listing-to-return
  slice itself produces 26.

The reserved-cancellation path executes 12 commands, produces 15 slice Outbox
events, requires a reservation release before `CANCELLED/v3`, and proves that
Payment and Fulfillment are absent. Definitions and exact link invariants are
versioned in `contracts/canonical-listing-fulfillment-commerce-v2.yaml`.

`models/apply-order-v1.txt` is the only model application order. Configuration
validation fails if any `models/**/*.sql` file is missing, duplicated or listed
more than once. Reconciliation rejects non-positive tenant IDs, empty results
and multiple rows; a zero-row SQL check is not accepted as evidence.

The normalized domain-event DWD exposes only relay-confirmed Outbox rows
(`status=20`, PUBLISHED). PENDING, CLAIMED and DEAD records remain in ODS for
operations and diagnosis but cannot advance Listing, Order, Payment,
Fulfillment or commerce readiness.

## Durable paid cancellation before shipment

The paid-but-unshipped slice keeps unpaid cancellation schema v1 and readiness
unchanged. Saga schema v2 fences an Order at `CANCELLATION_PENDING`, fences and
cancels one `CREATED` Fulfillment, refunds the exact captured Payment, releases
every exact Inventory reservation, finalizes the Order as `CANCELLED`, and then
marks the Saga `COMPLETED`. Participant event ordinals are Fulfillment 1,
Payment 2, Inventory 3 and Order 4; the terminal Saga ordinal is 5.

`dws_canonical_paid_order_cancellation_saga_current` preserves the recorded
time of every effect. Readiness requires nondecreasing Order-fence,
Fulfillment-cancel, Payment-refund, Inventory-release, Order-cancel and
Saga-complete times, exact participant identity, full CNY minor-unit refund,
zero shipment facts, stable idempotency evidence, and exact reservation links.
Retry and manual-review states remain operational evidence and cannot be
reported as reconciled. See
`contracts/canonical-paid-order-cancellation-saga-v2.yaml` and DQC 13.

## Canonical after-sales, refund and reverse fulfillment

The first after-sales slice adds an independent source of truth for a full
return and refund after forward delivery. It does not reuse the legacy Trade
after-sale tables as authoritative facts. Five versioned event families keep
the case, refund entitlement, return shipment, warehouse inspection and
durable resolution Saga separate. The 62-model manifest adds five DWD event
views, four current dimensions, a resolution DWS, the Y-Shopping-compatible
`dws_canonical_aftersales_buyer_1d` buyer/day summary and a terminal readiness
ADS.

The governed effect order is deliberately fail-closed:

1. return fulfillment reaches `INSPECTION_ACCEPTED` with quantity conservation;
2. Inventory records one exact `SALE_RETURN` for business type
   `AFTER_SALE_RETURN`;
3. Payment records the entitled CNY-minor refund;
4. Order reaches `RETURNED`;
5. the after-sale case and resolution Saga reach `COMPLETED`.

Readiness checks exact tenant-scoped IDs, aggregate-version continuity,
transition order, amount and quantity conservation, replay uniqueness, PII
isolation and recorded effect time. An Order cancellation Saga ID may never be
used as an after-sale resolution Saga ID, and a terminal after-sale row may not
end with Order `CANCELLED`. Run `tests/sql/14-canonical-aftersales-return-refund-contract.sql`
and reconcile the exact ERP Operator `run_id` with
`lakehousectl reconcile-canonical-aftersales`.

This slice intentionally supports one delivered Order item, one return
shipment, one warehouse inspection and a full accepted return/refund. Partial
acceptance, exchange, no-return refund, multi-item/multi-package returns,
appeal/compensation and production payment providers remain outside this first
contract. Compensation, coupon/discount allocation and nonzero return shipping
fees remain explicit future metrics rather than being inferred from refund
money. Empty after-sales tables prove only that the models and DQC parse;
they are not business acceptance evidence.

## CDC account

Run as a MySQL administrator and replace the password before use:

```sql
CREATE USER IF NOT EXISTS 'yshopping_cdc'@'%' IDENTIFIED BY '<local-secret>';
GRANT SELECT, RELOAD, SHOW DATABASES, REPLICATION SLAVE, REPLICATION CLIENT
  ON *.* TO 'yshopping_cdc'@'%';
FLUSH PRIVILEGES;
```

## Scope and acceptance

The initial job captures all current `erp_*` tables and routes them to
`yshopping_ods`. The first governed slice is inventory, purchasing and sales.
Before calling this production-ready, verify initial snapshot plus insert,
update, soft delete and hard delete; restart from a checkpoint; reconcile source
and sink row counts and keys; preserve decimal precision and timestamps; and
run a 72-hour soak test. Multi-tenant isolation is not considered complete
until the ERP `tenant_id` model is reconciled with the Java entities.
