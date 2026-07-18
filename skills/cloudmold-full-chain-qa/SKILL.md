---
name: cloudmold-full-chain-qa
description: Audit and execute CloudMold full-chain automation across the Vben admin UI, legacy Yudao ERP/Mall/WMS APIs, canonical CloudMold Skills, Outbox/CDC, and lakehouse evidence. Use it to build route-to-API-to-Skill coverage matrices, run read-only browser smoke coverage, produce code-dye reports, and classify unexecuted code as missing workflow, optional/error branch, or redundancy candidate.
---

# CloudMold Full-chain QA

This Skill treats coverage as business evidence, not a single percentage. It links:

`business goal -> UI route -> UI API -> backend atomic capability -> workflow Skill -> event -> lakehouse reconciliation`.

## Safety rules

- Default to `plan` or `inspect`. Browser coverage is read-only after local test login.
- Execute only against an explicitly supplied local/test base URL and tenant.
- Never store access/refresh tokens, passwords, raw PII, or response bodies in reports.
- Do not infer that zero coverage means dead code. Apply the classification rules below.
- Do not count a page load as a business workflow success. A workflow requires state, replay, rejection/recovery, and reconciliation evidence.
- Canonical consistency remains server-owned. This Skill may start/query a persisted Saga; it must not reimplement Saga state in the browser runner.

## Modes

### Plan

```bash
python3 scripts/full_chain_qa_runner.py plan
```

Print the test layers, commands, evidence paths, and side-effect policy. It performs no network or business writes.

### Inspect

```bash
python3 scripts/flow_coverage_audit.py \
  --workspace /Users/karekin/Downloads/coding/project/CloudMold \
  --output-dir ~/.cloudmold/runs/full-chain-qa/<run-id>/static
```

Inventory UI sources/tests/API wrappers, legacy ERP REST routes, and endpoints referenced by workflow runners. The report is deterministic and contains no credentials.

When a governed canonical commerce run already exists, bind it into the same evidence bundle with `--canonical-run-id <run_id>`. The gate requires a SUCCEEDED parent plus Catalog ACTIVE, three legacy identity projections per SKU, ACTIVE Merchant/Shop/Warehouse master data, completed fulfillment/after-sales/refund Saga, and immutable command replay. It emits `canonical-evidence.json` with a product-centric view and never replays irreversible business writes.

### Execute UI smoke and runtime dye

Start the local backend and Vben frontend first. Then provide credentials through environment variables:

```bash
export CLOUDMOLD_QA_USERNAME=admin
export CLOUDMOLD_QA_PASSWORD='<local-test-password>'
node scripts/ui_runtime_coverage.mjs \
  --ui-root /Users/karekin/Downloads/coding/project/CloudMold/yudao-ui-admin-vben \
  --base-url http://127.0.0.1:5666 \
  --tenant-id 1 \
  --scenario references/scenarios/business-ui-flow-coverage-v1.json \
  --output ~/.cloudmold/runs/full-chain-qa/<run-id>/runtime.json
```

The runner logs in through the normal UI, visits only declared read pages, records failed HTTP responses, and collects Chromium precise function coverage per route.

### Execute the governed suite

```bash
python3 scripts/full_chain_qa_runner.py execute \
  --workspace /Users/karekin/Downloads/coding/project/CloudMold \
  --run-id <run-id> \
  --canonical-run-id <retained-canonical-run-id> \
  --base-url http://127.0.0.1:5666 \
  --tenant-id 1
```

The suite runs in this order:

1. QA Skill regression tests plus Vben unit baseline, typecheck, lint, and active app build.
2. UI read-only runtime coverage for declared and live-menu routes.
3. Static route/API/Skill coverage audit enriched with runtime calls.
4. Live HSF export-to-Skill-to-execution coverage audit; missing live exports fail the suite.
5. Optional retained canonical product-chain ledger gate.
6. ERP Operator runner tests.
7. Lakehouse Python contract/model tests.

It stops on dependency failure but still writes a ledger containing completed steps and the blocker.

## Coverage classification

Every unexecuted file or endpoint receives one of these non-overlapping labels:

- `FLOW_GAP`: reachable production surface, but no complete workflow Skill or runtime scenario proves its business goal.
- `TEST_GAP`: the flow exists and is evidenced elsewhere, but this suite did not execute the page/function/endpoint.
- `ROLE_OR_DATA_GATED`: valid route or branch requires another role, tenant feature, fixture, approval, or non-empty data.
- `ERROR_OR_RECOVERY_BRANCH`: defensive, timeout, rejection, compensation, or recovery code that requires a deliberate fault scenario.
- `ADAPTER_OR_MIGRATION_PENDING`: intended compatibility/cutover code whose upstream mapping, backfill, or adapter is not production-ready.
- `REDUNDANCY_CANDIDATE`: no live menu, static import, API consumer, Skill reference, event/model reference, or documented target purpose was found.
- `GENERATED_OR_FRAMEWORK`: generated Vben/framework glue; evaluate at package level rather than as a business workflow.

Only `REDUNDANCY_CANDIDATE` is eligible for deletion review. Deletion still requires history inspection, owner confirmation, and a regression test.
Static API imports without a runtime call are `TEST_GAP`, not `FLOW_GAP`: a read-only smoke run normally does not exercise create, update, delete, approval, compensation, or role-gated branches. Promote an item to `FLOW_GAP` only when route, caller, Skill, or lineage evidence proves an actual break.

## Required evidence

The run directory must contain:

- `run.json`
- `commands.jsonl`
- `runtime.json`
- `static/coverage.json`
- `static/coverage.md`
- `static/hsf-coverage.json`
- `static/hsf-coverage.md`
- `canonical-evidence.json` when `--canonical-run-id` is supplied
- `test-results.json`
- `evidence-manifest.sha256`

Reports must state the denominator. “Loaded source files” and “executed transformed functions” are runtime-smoke denominators; they are not total source-line coverage.

## Interpretation gates

- Vben shared-package unit tests do not count as business-page coverage.
- A menu entry proves discoverability, not workflow completion.
- A UI API wrapper proves a client contract, not a backend atomic contract.
- A runner string match proves orchestration reference, not a successful run.
- DQC on an empty dataset cannot upgrade a workflow to verified.
- Canonical CloudMold coverage and legacy Yudao coverage must remain separate; connect them with migration/adapter edges, never `same_as`.

## References

- Scenario: `references/scenarios/business-ui-flow-coverage-v1.json`
- Static auditor: `scripts/flow_coverage_audit.py`
- Runtime dye runner: `scripts/ui_runtime_coverage.mjs`
- Governed suite: `scripts/full_chain_qa_runner.py`
