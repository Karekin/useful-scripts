---
name: cloudmold-erp-procurement
description: Create and approve a yudao ERP purchase order, bind its typed line to a supplier receipt promise, receive it, and verify the physical document chain through governed Dubbo capabilities. Use it for procurement automation after canonical Supplier, ERP Product/UOM, Account, Merchant, Shop, and operator ledgers are resolved; it never uses REST or UI clicks.
---

# CloudMold ERP Procurement

Run `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario references/scenario.json` first. Execute only in local/test with an approved input ledger and `--write-approved`.

The input JSON must contain `authority`, `command`, `promise`, and `purchaseIn`. `authority.reference` identifies the canonical Merchant/Shop and `authority.operator` identifies its OWNER assignment; both are validated through Dubbo before the first write. `command` matches `YudaoErpCommandApi.PurchaseOrderCommand`. IDs must come from canonical-to-yudao mappings; never invent `internal-company` or `internal-shop`.

The Skill creates and approves the order, discovers its persisted line through `listPurchaseOrderLines`, saves and reads the line-level promise, creates and approves the physical purchase-in document, then reads both ERP documents back. Treat the run as failed unless the promise is `ACTIVE/v1` and both documents are status `20`. Do not obtain a line ID through SQL or an Admin controller; the typed line query exists specifically so an AI can compose this flow through HSF alone.

Use `python3 ../../scripts/yudao_dubbo_flow.py execute --scenario references/scenario.json --input-json <ledger.json> --tenant-id <id> --operator-id <id> --operator-type <id> --skill-id skill.cloudmold.erp.procurement.v1 --run-id <id> --write-approved`.

For a full replay, use a new evidence `--run-id` and pass the original stable business key through `--idempotency-key <original-key>`. Never reuse a run directory and never generate a new business key merely because the first response timed out.
The promise's persisted `runId` deliberately uses that stable business key, not the evidence-directory run ID; otherwise a legitimate replay would alter the command digest.
