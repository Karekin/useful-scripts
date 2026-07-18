# CloudMold Dubbo contract

## Boundary

- Provider contracts are the public interfaces listed in `yudao-cloud/cloudmold-rpc/src/main/resources/cloudmold-dubbo-services.txt`.
- Group is `cloudmold-internal`; contract version is `1.0.0`; registry group is `CLOUDMOLD_DUBBO`.
- Capability IDs are stable: `capability.cloudmold.<domain>.<interface-kebab>.<method-kebab>.v1`.
- Non-overloaded methods use the readable base capability ID. Existing overloaded methods append a stable
  `sig-<12 hex>` suffix derived from parameter types so every Java signature still maps to one capability ID.

## Context and security

Every request carries tenant ID, operator ID/type, Skill ID, run ID, timestamp, nonce, capability ID, and an HMAC-SHA256 signature. Providers reject missing/tampered attachments and JVM-observed nonce replay before entering domain code. The provider maps verified identity into `TenantContextHolder` and `SecurityContextHolder`, then restores the previous thread context.

Dubbo class checking stays `STRICT`. Existing API DTOs predate RPC and do not consistently implement Java `Serializable`, so Hessian temporarily permits non-`Serializable` POJOs on both ends while retaining strict class checking. New and migrated contract DTOs should implement `Serializable`; remove this compatibility switch after the full contract inventory is clean.

The checked-in `security/serialize.allowlist` trusts only CloudMold API package prefixes used by published contracts. Do not widen it to the whole CloudMold implementation namespace; service, persistence, and framework classes are not wire contracts.

For multiple provider replicas, replace the JVM nonce cache with a shared short-TTL nonce ledger before production rollout.

## Migration

Dubbo is the internal orchestration authority. Existing Feign and Admin REST endpoints remain compatibility adapters for UI/external clients during migration. A compatibility adapter may call a Dubbo/domain atomic capability, but a Skill must not assemble its canonical business workflow through OpenAPI.

## Writes

The generic Executor denies capabilities classified as writes unless the caller supplies explicit approval. Domain command APIs remain responsible for idempotency keys, optimistic version checks, invariants, Outbox emission, and Saga state. The Executor must not recreate these rules.
