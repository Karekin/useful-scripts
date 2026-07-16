# Y Shopping lakehouse core

This is the first production-shaped local data path for CloudMold:

`yudao MySQL -> Flink 2.2.1 + Flink CDC 3.6.0 -> StarRocks 4.0.12`

It deliberately excludes the old experimental Airflow, Spark, Trino, MLflow,
Amoro, arbitrary-SQL API and Docker-socket services. Paimon and object storage
are a second-stage addition after CDC recovery, reconciliation and history
retention requirements are proven.

## Start

> Persistence migration warning (2026-07-15): older Compose revisions mounted
> StarRocks volumes below `/opt/starrocks`, while the 4.0.12 all-in-one image
> writes to `/data/deploy/starrocks`. Do not recreate an existing container
> until `/data/deploy/starrocks/fe/meta` and `be/storage` have been copied to a
> verified backup and then restored into the corrected named volumes.

1. Start `yudao-mysql` and `yudao-redis` from `../yudao/docker-compose.yaml`.
2. Create a least-privilege MySQL CDC account (see below).
3. Copy `.env.example` to `.env` and replace the local CDC password.
4. Run `docker compose up -d --build starrocks jobmanager taskmanager`.
5. Submit the four bounded CDC jobs with `lakehousectl`: ERP, Catalog, Outbox and
   Legacy Mall alignment.

The local UIs are StarRocks FE on port 8030 and Flink on port 8081.

## Governed procurement and inventory slice

The first executable vertical slice now has a versioned contract, current
dimensions, DWD line/movement facts, DWS summaries, ADS views and invariant
tests. Operate it through one entry point:

```bash
./scripts/lakehousectl config-check
./scripts/lakehousectl contract-test
./scripts/lakehousectl submit-cdc
./scripts/lakehousectl submit-catalog-cdc
./scripts/lakehousectl submit-event-cdc
./scripts/lakehousectl submit-legacy-mall-cdc
./scripts/lakehousectl apply-models
./scripts/lakehousectl health
./scripts/lakehousectl test
./scripts/lakehousectl reconcile --tenant 1 --run-id <erp-scenario-run-id>
./scripts/lakehousectl reconcile-canonical-inventory-lot --tenant 1 --run-id <inventory-lot-run-id>
./scripts/lakehousectl reconcile-canonical-commerce-v2 --tenant 1 --run-id <commerce-v2-run-id>
./scripts/lakehousectl reconcile-canonical-paid-cancellation-saga --tenant 1 --run-id <paid-cancellation-run-id>
./scripts/lakehousectl reconcile-canonical-aftersales --tenant 1 --run-id <aftersales-run-id>
```

`contract-test` also validates `yshopping-model-alignment-v1.json`. The contract
locks the six Y-Shopping source documents, 22 coverage units and four detailed
contexts: Merchant/Shop/Identity, Warehouse/Location, production-pilot
admission and inventory shadow verification. It rejects source
drift, duplicate authorities, cross-system ID equivalence, incomplete
tenant-scoped keys, ungoverned PII or money, missing lakehouse layers, missing
event evidence and drift from the current 154 SQL files/207 model objects. A
`missing`, `legacy_only` or `partial` status is an explicit open gate, not proof
of complete alignment.

`./scripts/lakehousectl source-assets` runs the stricter source inventory used
for the 100% governed-semantic-alignment program. The locked snapshot contains
718 distinct layer-prefixed names and 752 `FROM`/`JOIN` occurrences across all
six documents. The inventory preserves both the layer declared by a name and
the document layer where it occurs; it classifies references as physical tables,
CTEs, Python imports, code symbols or unresolved prose instead of treating every
match as a table. Duplicate and wrong-layer occurrences retain their line and
heading context, and statement-like lines that still require manual disposition
are reported separately. The inventory is evidence input only: it never executes
or silently repairs prototype SQL. Every listed asset and every unparsed statement
must eventually receive an explicit semantic decision before 100% can be claimed.
`./scripts/lakehousectl source-disposition-status` separately reports routing
progress and final disposition progress. The ODS overview currently provides
authoritative Chinese-domain evidence for 281 of the 718 names; routing those
assets does not grant completion credit until row-level split decisions, grains,
SoR, field handling, targets and reconciliation evidence are all recorded.
`./scripts/lakehousectl semantic-status` reports the authoritative completion
score: all 22 declared units and both backend/lakehouse surfaces stay in the
denominator, and only gap-free `verified` surfaces earn credit. The older 95.24%
surface score remains useful for structural presence, but it is not a completion
gate and does not credit the 100% objective.

The models intentionally call `erp_product` an ERP projection. Canonical apparel
SPU/SKU is sourced from the Mall catalog through a separate Catalog CDC job;
`product_sku.stock` remains a legacy sales field and is not promoted as the
inventory-ledger authority. The current ODS is
a primary-key mirror: soft deletion is visible, but hard deletion does not leave
a tombstone and the current dimensions are not SCD2. See
`contracts/erp-procurement-inventory-v1.yaml` for the governed contract and
known limits.

## Legacy Mall alignment current-state slice

The fourth CDC job mirrors an exact allowlist of 11 existing Mall tables for
Coupon, six Promotion activity types, Trade order/allocation references and
Product Favorite. Twelve views add DWD, DIM, DWS and ADS current-state
projections for Coupon, Activity and Collect. Every model is explicitly marked
`LEGACY_CURRENT_STATE`; it is not a canonical identity, immutable event stream
or SCD2 history.

The verified local snapshot is non-empty and source-count exact: 35 coupons,
10 activity rows and 11 favorite rows reach the four layers. Readiness exposes,
rather than hides, one used coupon without a usable order link, one invalid
Seckill time window, ten unnormalized activity status rows and ten soft-deleted
favorites. All capability flags for canonical identity, allocation/refund
history, activity events, preference scoring and reminder effects remain
false. This raises structural model-surface similarity from 54.76% to 61.90%;
it does not close the canonical Coupon/Order/AfterSale design gaps.

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

## Canonical identity, merchant and warehouse master data

The first M0A implementation slice adds versioned event families for
Principal/source identity, Merchant/Shop onboarding and operator assignments,
plus Warehouse/Zone/Location, source mappings and operator assignments. The
current manifest also includes the Listing-owned sales-eligibility enforcement
Saga described below. `tenant_id` exists only in the common event envelope;
raw PII is excluded from event payloads.

These views prove contract shape, dependency order and executable StarRocks
SQL. The local `cmw15master` run now proves one non-empty path: System admin
source `SYSTEM/SYSTEM_ADMIN_USER/1` resolves to a distinct Principal, one
Merchant/Shop reaches `MERCHANT_SHOP_READY`, one authorized Listing reaches
`LISTING_PUBLISHED`, and ERP source warehouse `ERP/WAREHOUSE/3` resolves to a
distinct Warehouse/Zone/Location that reaches `WAREHOUSE_NETWORK_READY`. All
21 public writes replayed as immutable duplicates; all Outbox rows were
published before reconciliation. This is a controlled first-slice sample, not
historical or production backfill evidence. A controlled `cmsm15a` sample also
proves one effective `YSHOPPING/MERCHANT` source mapping, including revoke,
replacement, immutable replay and a unique current DIM row. Member/System
credentials remain outside Identity authority; Inventory remains the
quantity-ledger authority and WMS remains the physical operation authority.

`inventory.stock.changed` v3 is now an implemented shadow-ledger contract. The
`cinv315a` run proves RECEIVE, RESERVE, SHIP, RETURN, RESERVE and RELEASE against
one real canonical Warehouse/Location, with an explicitly null lot rather than
a fabricated default. StarRocks reconciles six events through version 6 to
on-hand/reserved/available `8/0/8`. This does not prove historical balance
backfill, production cutover, multi-location allocation, transfer, count,
quality transitions or WMS physical operations.

`inventory.lot.lifecycle.changed` v1 and
`inventory.lot.source_mapping.changed` v1 make Lot a canonical Inventory
identity instead of inferring it from a source batch string. The `clot15iso`
run proves REGISTER, qualified source link, exact-lot receipt/reserve/release,
RECALL, interval-boundary source replacement, post-recall allocation fencing
and immutable replay. The six Lot models preserve the exact
owner/SKU/Warehouse/Location/Lot/stock/quality/UOM balance grain; the ADS does
not sum allocatable stock across locations or UOMs. Y-Shopping `unique_id`
remains an individual P-code, and community `batch_no` remains a recall reason;
neither is silently coerced into canonical `lot_id`. The 18 legacy balances
remain blocked until explicit owner, Warehouse, Location, Lot policy and source
facts are qualified; no default Lot or Location is manufactured.

`inventory.migration.balance_assessed` v1/v2 implements the ASSESS stage of the
inventory migration state machine. Every v1 balance is snapshotted with source
version/time/hash, source classification, quantities, active reservations and
explicit blocker codes. Active v1 reservations are not represented as canonical
v3 allocations: both allocation fields remain zero until qualified lineage
exists. The DWD/DIM/DWS/ADS chain is keyed by migration run and source row, and
the `ASSESSED_ONLY` readiness fence rejects any `MIGRATION_OPENING` event.
`inventory.migration.balance_qualified` v1 then records exact Merchant, SKU,
Warehouse source mapping, Location and Lot policy evidence for an explicit
`CONTROLLED_CANARY`. `inventory.stock.changed` v4 permits one qualification-
linked `MIGRATION_OPENING` into a new zero v3 balance. The ADS exposes
`QUALIFIED_ONLY/QUALIFIED_RUNTIME_GATED` and `MIGRATED_CANARY/CANARY_RECONCILED`
separately. `cmig15canary2` reconciles one assessment, qualification and
opening at exactly `10/0/0`; an earlier canary with an existing target was
rejected before opening and remains auditable as `QUALIFIED_ONLY`.

V24 admission evidence now feeds a separate V25 shadow-verification contract.
Three immutable event families keep window state, atomic completed rounds and
per-item comparisons distinct. Window state follows
`OPEN -> OBSERVING -> VERIFIED`, while `verification_result` remains a separate
`PENDING/MATCH/DIFFERENT/UNCOMPARABLE` axis: `VERIFIED` means terminal evidence
validation, never success by itself. The DWS denominator starts from the
historical V24 `ADMISSION_PASSED` item set crossed with every round, then left
joins comparison evidence, so missing targets cannot disappear from counts.

The only target is the independent read-only
`CANONICAL_INVENTORY_V3_SHADOW_PROJECTION`. A missing projection is explicit
`UNCOMPARABLE/TARGET_MISSING`; the models never copy a source balance to
manufacture `MATCH`. Raw `MYSQL_GTID_SET` values are retained for audit, while
monotonicity and containment booleans must be derived by the backend validator
`MYSQL_GTID_SET_CONTAINS_V1`. The lakehouse validates the resulting chain and
lag without lexicographically ordering GTID strings. A false target-containment
result makes every item and the whole round `UNCOMPARABLE` with
`TARGET_WATERMARK_NOT_COVERED`; when differences and uncomparable items coexist,
the terminal result remains `UNCOMPARABLE` while difference counts stay visible.
Only terminal
`VERIFIED + MATCH` plus full duration, round, gap, watermark and
expected-items-by-round gates yields `SHADOW_MATCH_VERIFIED`. Execution,
cutover and target materialization remain false, and the models do not depend
on the mutable V24 current readiness ADS after the window opens.

Re-run the exact non-empty gates with canonical IDs from the operator ledger:

```bash
./scripts/lakehousectl reconcile-canonical-merchant --tenant 1 \
  --merchant-id <merchant-uuid> --source-system SYSTEM \
  --source-type SYSTEM_ADMIN_USER --source-id <system-user-id>
./scripts/lakehousectl reconcile-canonical-warehouse-network --tenant 1 \
  --warehouse-id <warehouse-uuid> --source-system ERP \
  --source-type WAREHOUSE --source-id <erp-warehouse-id>
./scripts/lakehousectl reconcile-canonical-inventory --tenant 1 \
  --run-id <inventory-v3-run-id>
./scripts/lakehousectl reconcile-canonical-inventory-lot --tenant 1 \
  --run-id clot15iso
./scripts/lakehousectl reconcile-canonical-inventory-migration --tenant 1 \
  --run-id <migration-run-uuid>
```

## Merchant and Shop sales-eligibility enforcement

`merchant.entity.status_changed` v2 is the source decision. A Merchant
SUSPEND or Shop PAUSE creates a Listing-owned durable Saga with an exact frozen
PUBLISHED Listing workset. Its worker emits physical UNPUBLISH events using the
source Merchant event ID as `causation_id`; Merchant/Shop resume never
republishes Listings automatically. The four added DWD/DIM/DWS/ADS models prove
the source decision, frozen count, reported progress and exact physical effects.

The controlled `cmse15phys` run completed one Merchant and one Shop Saga. Each
expected and unpublished exactly one Listing, produced exactly one matching
UNPUBLISH event, and reconciled as `COMPLETED/RECONCILED/NOT_REQUIRED`. Re-run
each exact gate with the Saga IDs stored in the operator ledger:

```bash
./scripts/lakehousectl reconcile-canonical-listing-unpublish-saga \
  --tenant 1 --run-id cmse15phys --saga-id <saga-uuid>
```

## Merchant deposit control

`merchant.deposit.ledger_posted` v1 carries integer minor-unit assessments,
payments, freezes, unfreezes, deductions and enforcement activation. The current
projection conserves `held = paid - deducted` and `available = held - frozen`.
Coverage is computed by integer cross multiplication: at least 60% is
`SUFFICIENT`, 20% through below 60% is `BID_RESTRICTED`, and below 20% is
`SALES_BLOCKED`. Only an ENFORCED crossing into the last state can suspend an
ACTIVE Merchant; its deposit event is the exact cause of the Merchant status
event and Listing-owned unpublish Saga.

The controlled `cmdp15phys` run emitted eight deposit ledger events, ended at
required/held/frozen/paid/deducted `10000/10000/0/18100/8100`, and reconciled one
Merchant suspension and one completed physical Listing unpublish Saga. Top-up
did not auto-resume or republish. Re-run the exact non-empty gate with:

```bash
./scripts/lakehousectl reconcile-canonical-merchant-deposit \
  --tenant 1 --run-id cmdp15phys \
  --merchant-id c07fdf45-c907-4f9a-b13e-cff066593fcb
```

The full gate currently validates 130 SQL files/129 model objects, 35 event
types/45 schema versions, 55 Python tests and all 22 SQL DQC groups.

A controlled local Docker recovery showed that recreating the current
StarRocks container did not retain its catalogs. The current models and all four
CDC snapshots rebuilt the verified data successfully, but local container
storage must not be treated as durable. Persistent-volume restore, Flink
savepoint recovery and a production-grade disaster-recovery drill remain
release gates.

## CDC account

Run as a MySQL administrator and replace the password before use:

```sql
CREATE USER IF NOT EXISTS 'yshopping_cdc'@'%'
  IDENTIFIED WITH mysql_native_password BY '<local-secret>';
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
