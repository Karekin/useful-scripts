---
name: cloudmold-erp-stock-transfer
description: Create, approve, and verify a yudao ERP stock transfer over governed Dubbo. Use it when canonical SKU/product projections and both mapped warehouses are ACTIVE and the source has sufficient stock; it never orchestrates through REST or UI.
---

# CloudMold ERP Stock Transfer

Plan with `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario references/scenario.json`. Input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing; `command` matches `YudaoErpCommandApi.StockMoveCommand`, and source and target warehouse IDs must be distinct mapped yudao warehouses.

Execute only in local/test with skill ID `skill.cloudmold.erp.stock-transfer.v1` and `--write-approved`. Acceptance requires final type `STOCK_MOVE`, status `20`, and downstream inventory reconciliation by the calling full-chain Skill.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the final document before deciding whether another write is permitted.
