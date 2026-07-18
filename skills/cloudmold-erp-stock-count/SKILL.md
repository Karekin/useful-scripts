---
name: cloudmold-erp-stock-count
description: Create, approve, and verify a yudao ERP stock-count adjustment over governed Dubbo. Use it with a frozen stock snapshot, mapped product and warehouse IDs, and explicit approval for the variance; it does not require a UI.
---

# CloudMold ERP Stock Count

Plan with `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario references/scenario.json`. Input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing; `command` matches `YudaoErpCommandApi.StockCheckCommand`, and every line must carry book, actual, and variance quantities derived from the same snapshot.

Execute only in local/test with skill ID `skill.cloudmold.erp.stock-count.v1` and `--write-approved`. Acceptance requires final type `STOCK_CHECK`, status `20`, plus a separate inventory balance assertion.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the final document before deciding whether another write is permitted.
