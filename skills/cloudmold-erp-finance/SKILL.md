---
name: cloudmold-erp-finance
description: Create, approve, and verify yudao ERP payment or receipt documents through governed Dubbo capabilities. Use it after supplier/customer, account, source document, currency/amount, Merchant/Shop, and operator ledgers are validated; it never routes internal finance through OpenAPI.
---

# CloudMold ERP Finance

Choose `references/payment-scenario.json` or `references/receipt-scenario.json`, then plan with the shared runner. Input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing; `command` must match the corresponding nested RPC command and reference an existing approved source document.

Execute only in local/test with skill ID `skill.cloudmold.erp.finance.v1`, a unique run ID, and `--write-approved`. Acceptance requires the final type and ERP audit status `20`; money amounts must also reconcile to the source document and lakehouse ledger.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the final document before deciding whether another write is permitted.
