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
- `cloudmold_skill_task_submit_commerce_full_chain_r3`: submit only `skill.cloudmold.commerce.full-chain-hsf.v1@1.2.0` with an R3 approval reference bound to the exact tenant, operator, input hash and expiry.
- `cloudmold_skill_task_retry_commerce_full_chain_r3`: retry only that fixed R3 task after reading back and validating its persisted Skill ID, version and risk level.

Tool names are versioned compatibility surfaces. Change them only with a parallel migration and an updated DeerFlow MCP registration.
Additional domain tools may coexist only when their MCP annotations are read-only and non-destructive. The four task command tools are the only MCP write-shaped tools; they may change task-control state but never invoke an arbitrary domain WRITE directly. R1 remains generic only within the R1 boundary; R3 is a fixed allowlist surface.

## Write boundary

Direct MCP domain writes are forbidden. A WRITE capability passed to `cloudmold_capability_read_invoke` must fail before the Executor invokes Dubbo. MCP may submit or retry work only through fixed `SkillTaskCommandApi` capabilities. The task ledger owns stable idempotency keys, step leases, checkpoints, retries and resume. R2/R3 approval references use `cma1` HMAC evidence and are revalidated on submit, retry, every WRITE and every child submission; missing authority configuration, expiry, signature mismatch or scope mismatch fails closed. The current HMAC signer is a local/test authority, not the production Risk approval service. Compensation, Outbox/CDC evidence and final reconciliation remain requirements of each production Skill definition.

Use these identity mappings when the durable layer is introduced:

- MCP/DeerFlow control run ID -> task submission/query audit context
- Skill task ID -> durable business run ID returned by `SkillTaskCommandApi`
- Skill step code -> task-step identity
- task ID + step code -> stable business idempotency key
- task attempt -> lease/checkpoint history, never a new business identity

## Evidence policy

Persist protocol version, server identity, tool names, capability counts, selected capability IDs, run IDs, status, and small business-result summaries. Do not persist bearer tokens, model keys, cookie values, complete 50k+ capability catalogs, or unrestricted DeerFlow checkpoint state.

For R3 evidence, persist the input SHA-256, approval-reference SHA-256, DeerFlow thread ID, exact task ID, parent/child terminal statuses and step counts. Never persist the approval signature itself. A gateway HTTP timeout is not a task failure: recover only from the persisted DeerFlow thread, compare its exact tool arguments with the approved files, then query the durable task ledger.
