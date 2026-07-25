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
- A binding remains unavailable until its controller, contract test and runtime smoke
  all exist. `gate-execute` fails closed while any binding is unavailable.

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
- `POST /payments/internal-test/capture`
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

The plan has 28 ordered stages and a stable idempotency key for every stage. A
`BLOCKED_DEPENDENCY` result is correct while a Facade, Quality Skill, or lakehouse
reconcile command is not implemented and tested.

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

## Ordered execution

1. Resolve Member → canonical Principal through `/me`.
2. Use governed operator Skills to activate Merchant/Shop, Catalog SKU, Listing/Offer,
   Warehouse/Location, Quality release and exact sellable Inventory.
3. Start one App Session; list/search the published product and record search/exposure/
   click/PDP/cart/checkout behavior.
4. Preview checkout with exact Listing/Offer/SKU/version, create Canonical Order and
   capture only through `INTERNAL_TEST`.
5. Complete governed Fulfillment and read the same state from UniApp.
6. Create AfterSale from UniApp, complete reverse Fulfillment/inspection/refund/stock
   return through the governed operator Skill, and read the same terminal state.
7. Create a customer-service Ticket linked to the exact AfterSale.
8. Replay every write with the same idempotency key and require `DUPLICATE` with the
   same effect hash.
9. Reconcile non-empty behavior, commerce, AfterSale and customer-service facts after
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
