# CloudMold HSF MCP contract

## Boundary

The supported call path is:

`DeerFlow/AI -> authenticated Streamable HTTP MCP -> CloudMold capability catalog/executor -> signed Dubbo -> domain Provider`

MCP carries tool discovery and AI invocation. Dubbo remains the internal typed business protocol. REST/OpenAPI is not used to compose internal workflows.

## Tools

- `cloudmold_capability_list`: list governed READ/WRITE capabilities.
- `cloudmold_capability_describe`: return one capability's argument and result schemas.
- `cloudmold_capability_read_invoke`: invoke only a catalogued READ capability with tenant/operator/Skill/run context.

Tool names are versioned compatibility surfaces. Change them only with a parallel migration and an updated DeerFlow MCP registration.
Additional domain tools may coexist only when their MCP annotations are read-only and non-destructive; business writes still enter the durable task plane.

## Write boundary

Direct MCP writes are forbidden. A WRITE capability passed to `cloudmold_capability_read_invoke` must fail before the Executor invokes Dubbo. Durable writes belong to `SkillTaskCommandApi`; the task ledger must own approval, stable idempotency keys, step leases, checkpoints, retries, resume, compensation, Outbox/CDC evidence, and final reconciliation.

Use these identity mappings when the durable layer is introduced:

- MCP/DeerFlow run ID -> Skill task ID
- Skill step code -> task-step identity
- task ID + step code -> stable business idempotency key
- task attempt -> lease/checkpoint history, never a new business identity

## Evidence policy

Persist protocol version, server identity, tool names, capability counts, selected capability IDs, run IDs, status, and small business-result summaries. Do not persist bearer tokens, model keys, cookie values, complete 50k+ capability catalogs, or unrestricted DeerFlow checkpoint state.
