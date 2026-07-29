# CloudMold Replenishment Prepare Skill

## Purpose

This governed skill turns a persisted, ready replenishment execution proposal into a real downstream
draft document. It runs as a two-stage operating workflow:

- `resolve_execution_proposal` re-reads the domain proposal and verifies that it is still READY, that
  the recommendation is still APPROVED at the exact proposed version, and that no conversion exists.
- `convert_replenishment` consumes the frozen routing/mapping decision only after the enclosing
  Temporal approval gate has produced approval proof.
- It does **not** start a second BPM process.
- It does **not** wait for supplier confirmation, ASN, receipt, or putaway.
- It does **not** claim that procurement, inbound, or shelving is complete.

Those concerns belong to:

- `Agent Control` + `yudao BPM` for R2/R3 approval.
- `Temporal` for long-running waits and resume.
- Domain services for the authoritative business state.

## Skill identity

- `skill_id`: `skill.cloudmold.supply-planning.prepare.v1`
- `skill_version`: `1.0.0`

## Input contract

The daily Temporal discovery supplies only:

- `proposalId`: the persisted governed execution proposal
- `conversionId`: a deterministic conversion identity derived from the proposal candidate

The skill deliberately does not trust a caller-supplied conversion command. It rehydrates the exact
recommendation version, target type, mapping evidence, ERP/WMS identifiers, actor principal and policy
from the authoritative proposal before the write step.

## Output contract

The step returns a truthful preparation result only:

- purchase draft: `YUDAO_ERP / PURCHASE_ORDER / PREPARE`
- transfer draft: `YUDAO_WMS / MOVEMENT_ORDER / PREPARE`

The downstream next wait is carried as stable fields:

- `nextWaitingEventCode`
- `nextWaitingEventLabel`

See `references/wait-events.json`.

## Rotating test-data tool

`scripts/seed_replenishment_proposal.py` creates a new business chain through the stable
`/cloudmold/supply-planning/command` API:

`forecast → published forecast → supply plan → evaluated/selected scenario → approved plan
→ approved replenishment recommendation → READY execution proposal`

The scenario file must normally contain at least two entries. The tool selects entries round-robin by
business date, so consecutive daily runs do not keep reusing the same SKU and warehouse. For WMS
transfers it reads both warehouses' live SKU inventory first, preserves the configured source reserve,
caps each move to a configured fraction, rounds down to the minimum-order step, and checks destination
capacity. A governed Dubbo preflight may supply the two quantities explicitly when the Admin operator
does not hold WMS query permission; the tool requires the pair together and records that transport in
its result. It fails closed when no safe quantity remains. It stops at the READY proposal; the daily
Temporal workflow remains responsible for discovery, approval and conversion.

Credentials are supplied only at runtime through `CLOUDMOLD_ACCESS_TOKEN`; the tool never persists
tokens and never inserts business rows directly.
