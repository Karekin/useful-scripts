---
name: cloudmold-production-p4
description: Define and verify the fail-closed production P4 admission boundary for CloudMold cloud, payments, KMS/HSM, external logistics, consumer experience, data, resilience, and Agent execution.
---

# CloudMold Production P4

Use this Skill when the acceptance target is a real production P4 chain rather than
LOCAL/DEMO/TEST readiness.

## Safety boundary

- Readiness is read-only and never grants deploy, payment, import, or cutover authority.
- Production mutation requires a separate unexpired Risk Authority approval bound to
  the exact account, region, environment, action, resource scope, budget and rollback.
- Evidence must be observed in `production`, non-fixture, fresh, hashed, independently
  verified, retained in an immutable object-store version with an active retention lock,
  and signed by an asymmetric public key pinned in the reviewed trust policy. The object
  version and retention lock must also have a storage control-plane attestation whose
  signer is independently pinned; manifest fields alone are not proof of immutability.
- A locally generated manifest, synthetic timestamp, self-declared identity, screenshot,
  HTTP 200, empty dataset, or test PSP/WMS result earns no production credit.
- Structurally complete gate entries still score 0/16 when the global production trust
  anchor, manifest signature, collector attestation, or deployment identity is invalid.
- Secrets, private keys, PSP credentials and customer PII must never be put in evidence.

## Denominator

The reviewed registry has 16 mandatory gates:

1. isolated cloud identity/network;
2. immutable GitOps delivery and software supply chain;
3. managed database/cache/object storage;
4. KMS/HSM, rotation and repository secret hygiene;
5. real PSP capture/refund/webhook/settlement with exact money;
6. external WMS;
7. carrier;
8. reverse logistics;
9. realtime customer service;
10. content vault and moderation;
11. production recommendation/search;
12. observability, audit and incident response;
13. backup/restore and RPO/RTO;
14. 72-hour capacity/soak;
15. 718-asset production reconciliation;
16. Agent Risk Authority and immutable effect audit.

The denominator is fixed by
`references/production-p4-gates-v1.json`. A missing gate fails closed.

## Trust anchors

`references/production-trust-policy-v1.json` intentionally contains no signer until
the production owner completes onboarding. Add only a reviewed production public key
from Alibaba Cloud KMS asymmetric signing, an approved enterprise CA, or an approved
Sigstore export. Pin its SHA-256, allowed production account and allowed regions.
Never add a private key.

## Inspect requirements

```bash
python3 scripts/production_p4_gate.py requirements \
  --checked-at <explicit-UTC-timestamp>
```

This returns zero production credit until external evidence is supplied.

Scan a repository's current tracked tree without printing candidate values:

```bash
python3 scripts/secret_hygiene.py --repository <git-repository>
```

This is a current-tree preflight only. A gitleaks-equivalent full-history scan and
provider-side revocation/rotation remain mandatory before production admission.

## Verify production evidence

```bash
python3 scripts/production_p4_gate.py check \
  --manifest <operator-retained-evidence/manifest.json> \
  --checked-at <explicit-UTC-timestamp> \
  --output <readiness.json>
```

Only `status=PRODUCTION_P4_READY`, `production_credit=true`, 16/16 verified gates and
zero errors mean the evidence admission target is met. Even then, a separate deployment
or cutover approval is mandatory.
