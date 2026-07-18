---
name: cloudmold-hsf-mcp-operator
description: Deploy-independent verification and read-only operation of the CloudMold DeerFlow-to-MCP-to-Dubbo/HSF control plane. Use when checking MCP authentication and protocol negotiation, auditing the governed capability catalog, proving an AI agent can discover MCP tools, invoking a tenant-aware READ capability through signed Dubbo, or confirming that direct MCP business writes are rejected before execution.
---

# CloudMold HSF MCP Operator

Verify the control path `DeerFlow/AI -> MCP -> governed Executor -> Dubbo -> Provider`. Treat MCP as the AI protocol adapter, not as a replacement for Dubbo or the future durable Skill Task Executor.

## Safety gates

- Run only against local or explicitly approved test environments.
- Read the MCP bearer token from the ignored mode-`0600` token file. Never print, copy into evidence, or commit it.
- Allow direct MCP invocation only for catalog inspection and READ capabilities.
- Require positive tenant/operator context and stable Skill/run IDs for a business read.
- Verify a WRITE capability is rejected by the MCP boundary; never alter its arguments to make the write succeed.
- Send business writes through the durable Skill Task command plane after it is available.

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
python3 scripts/hsf_mcp_operator.py deerflow-e2e --run-id <run-id>
```

Run `full` to execute protocol verification, an optional real business read, and the DeerFlow Agent call in dependency order. Pass `--capability-id` and `--arguments-json` to `full` to include the business read.

Evidence is written beneath `~/.cloudmold/runs/hsf-mcp/<run-id>/`. The runner stores summaries rather than full capability payloads or DeerFlow state so the ledger remains small.

## Acceptance gates

Do not declare the control plane ready unless all are true:

1. The MCP service health endpoint is `UP`.
2. An unauthenticated MCP initialize request returns HTTP 401.
3. MCP negotiates protocol `2025-11-25` and exposes all three required capability tools; any extension tool is explicitly read-only and non-destructive.
4. READ and WRITE capability catalogs are non-empty and their counts are recorded.
5. Passing a catalogued WRITE capability to the direct READ tool returns `SecurityException` without a domain write.
6. A supplied business READ returns `SUCCEEDED` through signed, tenant-aware Dubbo.
7. DeerFlow using the configured model discovers and calls `cloudmold-hsf_cloudmold_capability_list` with `operationType=READ`.

Read `references/contract.md` before changing tool names, trust boundaries, evidence fields, or the durable-write migration path.
