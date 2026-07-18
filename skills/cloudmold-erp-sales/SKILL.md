---
name: cloudmold-erp-sales
description: Create, approve, and verify a yudao ERP sales order through governed Dubbo capabilities. Use it after canonical Customer, ERP Product/UOM, Account, Merchant, Shop, inventory, and operator ledgers are resolved; it never depends on a page or HTTP request.
---

# CloudMold ERP Sales

Run `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario references/scenario.json`. The input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing; `command` matches `YudaoErpCommandApi.SaleOrderCommand`, and all legacy IDs must be backed by canonical mapping ledgers.

Execute in local/test with the shared runner, positive tenant/operator context, skill ID `skill.cloudmold.erp.sales.v1`, a unique run ID, and `--write-approved`. Acceptance requires the final Dubbo read model to be `SALE_ORDER` with status `20`.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the final document before deciding whether another write is permitted.
