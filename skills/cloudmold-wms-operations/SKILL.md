---
name: cloudmold-wms-operations
description: Create, complete, and verify yudao WMS receipt, shipment, movement, and check orders through governed Dubbo capabilities. Use it only after canonical SKU, Merchant/Shop, physical warehouse, inventory, and legacy WMS mapping ledgers are ACTIVE; no UI or REST chain is required.
---

# CloudMold WMS Operations

Choose the receipt, shipment, movement, check, or `full-chain-scenario.json` scenario under `references/`. Plan with `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario <scenario>`. Input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing. The full-chain scenario builds the legacy WMS Merchant, two warehouses, category, item and SKU through atomic Dubbo prerequisites, then performs receipt → movement → shipment → zero-variance check and verifies inventory after every physical mutation. Existing environments may instead provide canonical mapping ledgers to the smaller scenarios.

Execute only in local/test with skill ID `skill.cloudmold.wms.operations.v1`, a unique run ID, and `--write-approved`. Completion mutates physical inventory; acceptance requires the final WMS document state plus inventory history and canonical/lakehouse reconciliation.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the final document and inventory history before deciding whether another write is permitted.
