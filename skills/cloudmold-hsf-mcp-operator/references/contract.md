# CloudMold HSF MCP contract

## Boundary

The supported call path is:

`DeerFlow/AI -> authenticated Streamable HTTP MCP -> CloudMold capability catalog/executor -> signed Dubbo -> domain Provider`

MCP carries tool discovery and AI invocation. Dubbo remains the internal typed business protocol. REST/OpenAPI is not used to compose internal workflows.

## Tools

- `cloudmold_capability_list`: list governed READ/WRITE capabilities.
- `cloudmold_capability_describe`: return one capability's argument and result schemas.
- `cloudmold_capability_read_invoke`: invoke only a catalogued READ capability with tenant/operator/Skill/run context.
- `cloudmold_skill_task_submit_r1`: idempotently submit a versioned R1 Skill definition to the persistent executor.
- `cloudmold_skill_task_get`: read one durable task by task ID.
- `cloudmold_skill_task_get_by_request_key`: resolve a task by Skill ID and client request key.
- `cloudmold_skill_task_list_steps`: read persisted step status, attempts and request/result hashes.
- `cloudmold_skill_task_retry_r1`: move a `NEEDS_REVIEW` R1 task back to `QUEUED` with an expected version and reason.

Tool names are versioned compatibility surfaces. Change them only with a parallel migration and an updated DeerFlow MCP registration.
Additional domain tools may coexist only when their MCP annotations are read-only and non-destructive. The two R1 task command tools are the only MCP write-shaped tools; they may change task-control state but never invoke an arbitrary domain WRITE directly.

## Write boundary

Direct MCP domain writes are forbidden. A WRITE capability passed to `cloudmold_capability_read_invoke` must fail before the Executor invokes Dubbo. MCP may submit or retry R1 work only through the fixed `SkillTaskCommandApi` capabilities. The task ledger owns stable idempotency keys, step leases, checkpoints, retries and resume. R2/R3 submission remains unavailable until approval references can be validated against the Risk/approval authority rather than trusted as caller-provided text. Compensation, Outbox/CDC evidence and final reconciliation remain requirements of each production Skill definition.

Use these identity mappings when the durable layer is introduced:

- MCP/DeerFlow control run ID -> task submission/query audit context
- Skill task ID -> durable business run ID returned by `SkillTaskCommandApi`
- Skill step code -> task-step identity
- task ID + step code -> stable business idempotency key
- task attempt -> lease/checkpoint history, never a new business identity

## Evidence policy

Persist protocol version, server identity, tool names, capability counts, selected capability IDs, run IDs, status, and small business-result summaries. Do not persist bearer tokens, model keys, cookie values, complete 50k+ capability catalogs, or unrestricted DeerFlow checkpoint state.
