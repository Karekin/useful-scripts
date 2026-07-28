# CloudMold Replenishment Prepare Skill

## Purpose

This governed skill converts an already approved replenishment recommendation into a real downstream
draft document. It is intentionally narrow:

- It does **not** run BPM approval.
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

The caller must provide one `CONVERT_REPLENISHMENT` command whose recommendation has already been
approved by the upstream business policy.

The command is submitted to the canonical supply-planning command surface and must include:

- tenant-scoped envelope fields
- `replenishmentConversion.recommendationId`
- exact `expectedVersion`
- `targetType`
- governed mapping evidence
- the exact legacy ERP/WMS mapping identifiers required by the downstream adapter

## Output contract

The step returns a truthful preparation result only:

- purchase draft: `YUDAO_ERP / PURCHASE_ORDER / PREPARE`
- transfer draft: `YUDAO_WMS / MOVEMENT_ORDER / PREPARE`

The downstream next wait is carried as stable fields:

- `nextWaitingEventCode`
- `nextWaitingEventLabel`

See `references/wait-events.json`.
