---
name: cloudmold-hsf-mcp-operator
description: Verify and operate the CloudMold DeerFlow-to-MCP-to-Dubbo/HSF control plane, including durable R1 Skill Tasks. Use when checking MCP authentication and protocol negotiation, auditing the governed capability catalog, proving an AI agent can discover MCP tools, invoking a tenant-aware READ capability, submitting/querying/retrying a persistent R1 Skill Task, or confirming that direct MCP domain writes are rejected before execution.
---

# CloudMold HSF MCP Operator

Verify the control path `DeerFlow/AI -> MCP -> governed Executor -> Dubbo -> Provider`. Treat MCP as the AI protocol adapter, not as a replacement for Dubbo. Durable work belongs to the persistent Skill Task Executor and its MySQL ledger.

## Safety gates

- Run only against local or explicitly approved test environments.
- Read the MCP bearer token from the ignored mode-`0600` token file. Never print, copy into evidence, or commit it.
- Allow direct capability invocation only for READ operations.
- Require positive tenant/operator context and stable Skill/run IDs for a business read.
- Verify a WRITE capability is rejected by the MCP boundary; never alter its arguments to make the write succeed.
- Submit and retry only R1 tasks through the dedicated durable MCP tools. R2/R3 remain blocked until approval evidence is cryptographically verifiable.
- Never call a domain WRITE capability from MCP; Skill steps own business idempotency and recovery.

## Workflow

From this Skill directory:

```bash
python3 scripts/hsf_mcp_operator.py plan
python3 scripts/hsf_mcp_operator.py verify --run-id <run-id>
python3 scripts/hsf_mcp_operator.py invoke-read \
  --capability-id capability.cloudmold.<domain>.<interface>.<method>.v1 \
  --arguments-json '[...]' \
  --tenant-id 1 --operator-id 1 --operator-type 1 \
  --skill-id skill.cloudmold.<flow>.v1 --run-id <run-id>
python3 scripts/hsf_mcp_operator.py invoke-task-r1 \
  --run-id <run-id> \
  --target-skill-id skill.cloudmold.<flow>.v1 \
  --target-skill-version 1.0.0 \
  --client-request-key <stable-key> \
  --input-json '{"businessKey":"value"}'
python3 scripts/hsf_mcp_operator.py deerflow-e2e --run-id <run-id>
python3 scripts/hsf_mcp_operator.py deerflow-task-e2e \
  --run-id <run-id> \
  --target-skill-id skill.cloudmold.<flow>.v1 \
  --input-json '{"businessKey":"value"}'
```

Run `full` to execute protocol verification, an optional real business read, and the DeerFlow Agent call in dependency order. Pass `--capability-id` and `--arguments-json` to `full` to include the business read.

Evidence is written beneath `~/.cloudmold/runs/hsf-mcp/<run-id>/`. The runner stores summaries rather than full capability payloads or DeerFlow state so the ledger remains small.

## Acceptance gates

Do not declare the control plane ready unless all are true:

1. The MCP service health endpoint is `UP`.
2. An unauthenticated MCP initialize request returns HTTP 401.
3. MCP negotiates protocol `2025-11-25`, exposes the three capability tools and five durable Skill Task tools, and reports accurate read-only/idempotency annotations.
4. READ and WRITE capability catalogs are non-empty and their counts are recorded.
5. Passing a catalogued WRITE capability to the direct READ tool returns `SecurityException` without a domain write.
6. A supplied business READ returns `SUCCEEDED` through signed, tenant-aware Dubbo.
7. DeerFlow using the configured model discovers and calls `cloudmold-hsf_cloudmold_capability_list` with `operationType=READ`.
8. An R1 task submitted through MCP persists a task ID and step checkpoints, then reaches `SUCCEEDED` through typed Dubbo.
9. DeerFlow using the configured model can submit the exact R1 task and query the returned task ID to `SUCCEEDED`.

Read `references/contract.md` before changing tool names, trust boundaries, evidence fields, or the durable-write migration path.
