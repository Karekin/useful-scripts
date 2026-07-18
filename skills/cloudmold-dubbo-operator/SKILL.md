---
name: cloudmold-dubbo-operator
description: Deploy, inspect, and verify the governed CloudMold Dubbo capability plane for AI/Skill orchestration. Use it when starting Nacos and Dubbo Admin, building or launching the CloudMold provider, persistent Skill Task Executor, or one-shot Executor, auditing the 85-service allowlist, listing machine-callable capabilities, invoking an authenticated read-only or approved write RPC, or diagnosing missing Dubbo registrations.
---

# CloudMold Dubbo Operator

Operate the internal capability plane as `Skill -> Executor -> Dubbo -> domain service`. Keep HTTP/OpenAPI as an external compatibility plane; never use it as the internal workflow bus.

## Safety gates

- Run only against local or explicitly approved test environments.
- Require the Docker secret file `data/secrets/cloudmold-rpc-shared-secret` with at least 32 bytes. Never print it or commit it.
- Default invocations to read-only. Pass `--write-approved` only after the caller explicitly approves the exact write and tenant.
- Require positive tenant, operator, and operator-type IDs plus stable skill/run IDs.
- Treat the checked-in 85-interface allowlist as the RPC exposure boundary. Do not export arbitrary Spring beans.
- Preserve the legacy Feign/Admin REST plane during migration; remove it only after equivalent Skill evidence exists.

## Workflow

From this Skill directory:

```bash
python3 scripts/dubbo_operator.py plan
python3 scripts/dubbo_operator.py deploy-registry
python3 scripts/dubbo_operator.py build
python3 scripts/dubbo_operator.py start-provider --run-id <run-id>
python3 scripts/dubbo_operator.py verify --minimum-services 85
```

Use `full` to run the same dependency-ordered deployment sequence. It stops at the first failed gate and writes evidence beneath `~/.cloudmold/runs/dubbo/<run-id>/`. Complete deployment acceptance with a separate signed `invoke` using a real read-only business key.

## Invoke one capability

List capability IDs through the Executor:

```bash
python3 scripts/dubbo_operator.py capabilities
```

Invoke a read capability:

```bash
python3 scripts/dubbo_operator.py invoke \
  --capability-id capability.cloudmold.<domain>.<interface>.<method>.v1 \
  --arguments-json '[...]' \
  --tenant-id 1 --operator-id 1 --operator-type 1 \
  --skill-id skill.cloudmold.<flow>.v1 --run-id <run-id>
```

The Executor rejects unknown capabilities, wrong arity, missing context, unsigned calls, replayed nonces, and writes without `--write-approved`. It persists the parsed business response as `capability-result.json`; a zero exit code without a structured `SUCCEEDED` response is a failure.

## Evidence gates

Do not declare Dubbo deployed until all are true:

1. Nacos liveness succeeds.
2. Provider build succeeds.
3. Dubbo Admin is healthy at `http://127.0.0.1:38080/admin/` and discovers the Nacos control plane.
4. Yudao Provider exports 83 domain capabilities and the persistent Skill Task Executor exports its two command/query contracts.
5. Nacos reports at least 85 governed providers in `CLOUDMOLD_DUBBO`.
6. A signed, tenant-aware, read-only RPC returns through the containerized Executor.
7. RPC unit tests pass, including allowlist, capability uniqueness, signature, and replay rejection.

Read `references/contract.md` when changing versioning, identity propagation, security, or the migration boundary.
