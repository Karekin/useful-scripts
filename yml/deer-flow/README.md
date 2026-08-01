# CloudMold DeerFlow control plane

This directory deploys the official DeerFlow base plus the pinned CloudMold
`feature/cloudmold-agent-operations` branch as CloudMold's
AI control plane. DeerFlow selects and coordinates Skills; it does not replace
the durable CloudMold Skill Task Executor, Dubbo/HSF domain services, Saga,
Outbox, CDC, or lakehouse reconciliation.

## Security and persistence decisions

- Bind the UI and gateway proxy only to `127.0.0.1:2026`.
- Use the local sandbox with host bash disabled.
- Do not mount the host Docker socket or the full `~/.codex`/`~/.claude` trees.
- Inject the model key from the process environment, or read it from the
  Git-ignored `runtime/zhipu-api-key` file with mode `0600`; never put it in a
  tracked configuration file.
- Use an isolated Docker client configuration for public images so a blocked
  desktop credential helper cannot stall deployment or expose registry auth.
- Mount `useful-scripts/skills` read-only at DeerFlow's required
  `/app/skills/public` category path; `business-taxonomy.json` supplies the
  business-unit → domain → role hierarchy while package paths stay flat and
  compatible with existing SkillTask references.
- Persist the unified SQLite database and run events under the ignored
  `runtime/home` directory.
- Keep the generated local administrator password and cookie jar in the same
  ignored directory with mode `0600`; `deerflowctl up` initializes or logs in
  the local administrator without printing credentials.
- The Yudao provider mounts the ignored `.skill-catalog-auth-token` as a Docker
  secret. DeerFlow accepts that audience-limited credential only for the two
  read-only岗位能力 routes; Yudao never receives the Gateway-wide internal
  token, and the browser receives neither credential. Rotate it by recreating
  both DeerFlow and Yudao services.
- Keep Skill self-evolution write APIs disabled until the CloudMold approval and
  audit boundary is implemented. The custom-agent management API is enabled for
  the authenticated, localhost-only development control plane; do not expose
  port 2026 beyond the local machine without adding a stronger admin boundary.

## Operations

The deployment repository must exist at `../deer-flow` and be checked out at
the exact commit recorded by `DEER_FLOW_EXPECTED_COMMIT`. The default pin is
`feature/cloudmold-agent-operations@93917bb3b147b925728d8caa76b2d3659cbfa91c`.

```bash
scripts/deerflowctl doctor
scripts/deerflowctl up
scripts/deerflowctl bootstrap
scripts/deerflowctl status
scripts/deerflowctl smoke
scripts/deerflowctl logs gateway
scripts/deerflowctl down
```

The configured model is 智谱 `glm-5.2` through its OpenAI-compatible endpoint.
`deerflowctl up` first uses `DEER_FLOW_MODEL_API_KEY`, then the ignored
`runtime/zhipu-api-key`, and only then a generic `OPENAI_API_KEY` fallback.
`DEER_FLOW_MODEL_BASE_URL` can override the default 智谱 endpoint for controlled
testing. This precedence prevents unrelated shell-wide `OPENAI_*` variables
from silently keeping DeerFlow on a stale provider.

Rollback is deterministic: run `scripts/deerflowctl down`, check out the prior
commit in the external DeerFlow repository, update `DEER_FLOW_EXPECTED_COMMIT`,
then rebuild. Preserve `runtime/home` to retain task history, or copy it before
a database migration.

DeerFlow v2.0.0 still has a Store-provider compatibility gap: its Store reads
the legacy `checkpointer` field while its Checkpointer already honors the
unified `database` field. The CloudMold config intentionally points both fields
at `runtime/home/data/deerflow.db`; remove the compatibility field only after an
upstream version logs a persistent Store when configured with `database` alone.
