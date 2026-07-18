# CloudMold DeerFlow control plane

This directory deploys the official DeerFlow `v2.0.0` release as CloudMold's
AI control plane. DeerFlow selects and coordinates Skills; it does not replace
the durable CloudMold Skill Task Executor, Dubbo/HSF domain services, Saga,
Outbox, CDC, or lakehouse reconciliation.

## Security and persistence decisions

- Bind the UI and gateway proxy only to `127.0.0.1:2026`.
- Use the local sandbox with host bash disabled.
- Do not mount the host Docker socket or the full `~/.codex`/`~/.claude` trees.
- Inject the model key from the process environment; never persist it here.
- Use an isolated Docker client configuration for public images so a blocked
  desktop credential helper cannot stall deployment or expose registry auth.
- Mount `useful-scripts/skills` read-only as DeerFlow's Skill catalog.
- Persist the unified SQLite database and run events under the ignored
  `runtime/home` directory.
- Keep custom-agent and Skill self-evolution write APIs disabled until the
  CloudMold approval and audit boundary is implemented.

## Operations

The official repository must exist at `../deer-flow` and be checked out at
tag `v2.0.0` (`7e7f0410797693cf882594555ba414e0361d4c6f`).

```bash
scripts/deerflowctl doctor
scripts/deerflowctl up
scripts/deerflowctl status
scripts/deerflowctl logs gateway
scripts/deerflowctl down
```

`OPENAI_API_KEY` and `OPENAI_BASE_URL` must be present in the calling
environment for `up`. The current verified provider is the OpenAI-compatible
Moonshot endpoint and the configured model is `kimi-k2.5`.

Rollback is deterministic: run `scripts/deerflowctl down`, check out the prior
tag in the external DeerFlow repository, update `DEER_FLOW_EXPECTED_VERSION`,
then rebuild. Preserve `runtime/home` to retain task history, or copy it before
a database migration.
