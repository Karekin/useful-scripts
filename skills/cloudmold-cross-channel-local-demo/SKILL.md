---
name: cloudmold-cross-channel-local-demo
description: Plan, gate, execute through existing CloudMold Skills/App Facades, and validate one local/demo/test business chain from merchant onboarding and canonical product release through UniApp discovery, checkout, INTERNAL_TEST payment, fulfillment, return/refund/restock, customer service, behavior events, immutable replay, and lakehouse reconciliation.
---

# CloudMold Cross-channel Local/Demo Chain

Use this Skill when the acceptance target is not “an admin API works” or “a mobile
page renders”, but one exact Principal, Listing, Offer, SKU, Order and AfterSale that
remain identical across the admin system, UniApp, Agent ledger and lakehouse.

## Safety boundary

- Default mode is `plan`. Planning is read-only.
- Execute is permitted only in `local`, `demo`, or `test`.
- Execute requires an unexpired `LOCAL_TEST_HUMAN_APPROVAL` bound to the exact
  `runId`, environment and `cross-channel:execute` scope.
- `production` is forbidden. The local approval file is not a production Risk
  Authority permit.
- Never mark a run successful from UI screenshots, HTTP 200 alone, empty DQC, mock
  fallback, or fixture data. The terminal ledger must be non-simulated and non-empty.
- Every binding is statically tied to a real controller or governed executable.
  `gate-execute` fails closed if a binding, approval, runtime receipt, or terminal
  reconciliation is unavailable.
- Consumer App requests and responses must not carry raw receiver name/mobile/address,
  restricted quality evidence, or internal task IDs. Real delivery stays blocked until
  an Address Vault can issue a restricted delivery token; the first Order slice accepts
  only `idempotencyKey` and `checkoutToken`.

## Machine contracts

- Scenario and evidence: `../../contracts/cross-channel-agent-scenario-v1.json`
- App Facade bindings: `../../contracts/cross-channel-app-facade-bindings-v1.json`
- Lakehouse reconciliation:
  `../../yml/yshopping-lakehouse/contracts/yshopping-cross-channel-agent-reconciliation-v1.json`

The frozen consumer contract is `/app-api/cloudmold/app/**`:

- `GET /me`
- `GET /products`, `GET /products/{listingId}`
- `POST /checkout/preview`
- `POST /orders`, `GET /orders/{orderId}`
- `POST /payments/internal-test/capture-with-attribution`
- `GET /fulfillments/by-order/{orderId}`
- `POST /after-sales`, `GET /after-sales/{afterSaleId}`
- `POST /customer-service/tickets`, `GET /customer-service/tickets/{ticketId}`

Anonymous session and sanitized behavior use the existing
`/app-api/cloudmold/commerce-behavior/**` contract.

## Plan

```bash
python3 scripts/cross_channel_agentctl.py plan \
  --run-id <stable-run-id> \
  --environment test \
  --output <plan.json>
```

The plan has 48 ordered stages and a stable idempotency key for every stage. The
current contracts are ready for an approved local/demo/test execute. Address Vault,
homepage recommendation, community feed/interaction, service cart, product review, and
the operator-side Catalog metadata/barcode plus supply PREPARE slices are now explicit
parts of the chain. Runtime evidence still fails closed when a Facade, quality receipt,
CDC checkpoint, non-empty model, or lakehouse reconciliation is unavailable.

## Gate execute

Create an approval object with:

- `schema_version=1`
- `approvalType=LOCAL_TEST_HUMAN_APPROVAL`
- exact `runId` and `environment`
- `approved=true`
- `approvedBy`, `approvedAt`, `expiresAt`
- `scopes=["cross-channel:execute"]`
- `approvalDigest`, calculated by canonical SHA-256 over the object without that field

Then run:

```bash
python3 scripts/cross_channel_agentctl.py gate-execute \
  --run-id <stable-run-id> \
  --environment test \
  --approval <approval.json> \
  --output <execute-gate.json>
```

Only `AUTHORIZED` permits the Agent to invoke existing typed Skills and App Facades.
The Agent must write each request/response/effect digest and Outbox event ID to the
same run ledger. It may never fill a missing receipt with a synthetic result.

## Runtime ledger

Initialize one governed runtime directory:

```bash
python3 scripts/cross_channel_agentctl.py execute \
  --run-id <stable-run-id> \
  --environment test \
  --approval <approval.json> \
  --runtime-root <runtime-root>
```

Then append recorded step receipts:

```bash
python3 scripts/cross_channel_agentctl.py resume \
  --run-id <stable-run-id> \
  --runtime-root <runtime-root> \
  --receipt <step-receipt.json>
```

Finally seal the terminal ledger from the persisted runtime receipts:

```bash
python3 scripts/cross_channel_agentctl.py replay \
  --run-id <stable-run-id> \
  --runtime-root <runtime-root> \
  --terminal-evidence <terminal-evidence.json> \
  --output <terminal-ledger.json>
```

`validate-ledger` now rejects terminal ledgers that are unsigned, missing runtime
receipts, stale, or whose request/response/effect hashes do not match the persisted
receipts.

## Ordered execution

1. Resolve Member → canonical Principal through `/me`.
2. Use governed operator Skills to activate Merchant/Shop, Catalog SKU, Listing/Offer,
   Warehouse/Location, Quality release and exact sellable Inventory.
3. Update canonical metadata/barcode, create one PREPARE replenishment draft, and
   bridge one WMS receipt into exact Canonical Inventory.
4. Start one App Session; fetch homepage recommendations, record recommendation
   exposure/click, inspect community feed/detail/interaction, then list/search the
   published product and record search/exposure/click/PDP/cart/checkout behavior.
5. Exercise the service cart, preview checkout from cart and directly from product
   detail, then create Canonical Order and capture only through `INTERNAL_TEST`.
6. Complete governed Fulfillment, create one product review, and read the same state
   from UniApp-facing APIs.
7. Create AfterSale from UniApp, complete reverse Fulfillment/inspection/refund/stock
   return through the governed operator Skill, and read the same terminal state.
8. Create a customer-service Ticket linked to the exact AfterSale.
9. Replay every write with the same idempotency key and require `DUPLICATE` with the
   same effect hash.
10. Reconcile non-empty behavior, commerce, AfterSale and customer-service facts after
   a successful Outbox CDC checkpoint; require zero source→fact, fact→projection,
   tenant, identity, product, money, quantity and DQC mismatches.

## Accept evidence

```bash
python3 scripts/cross_channel_agentctl.py validate-ledger \
  --ledger <terminal-ledger.json>
```

Accept only `status=valid`. The validator enforces:

- Member, Principal and Session identity continuity;
- Listing, Offer, SPU and SKU continuity;
- checkout payable = Order payable = captured = refunded in integer minor units;
- ordered = accepted return = returned-to-stock quantity;
- Inventory availability restored after accepted return;
- terminal `RETURNED/REFUNDED/DELIVERED/COMPLETED/INSPECTION_ACCEPTED`;
- required behavior events and exact customer-service linkage;
- non-empty governed lakehouse results, successful CDC checkpoint and zero mismatches;
- immutable replay for every write.

The result always carries `productionCredit=false`.
