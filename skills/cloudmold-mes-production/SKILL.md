---
name: cloudmold-mes-production
description: Create MES unit, product category, product projection, work order, confirm, finish, and verify it over governed Dubbo. Use it after canonical Merchant/Shop/operator authority is resolved; it does not need a frontend or HTTP endpoint.
---

# CloudMold MES Production

> Deprecated as a managed business role. Use `cloudmold-mes-production-execution-lifecycle` for daily Temporal orchestration, fresh occurrence data, production feedback, qualified receipt, and terminal business evidence. This skill remains only as a compatibility/demo utility and must not receive an independent daily Schedule.

Plan with `python3 ../../scripts/yudao_dubbo_flow.py plan --scenario references/scenario.json`. Input contains an `authority` Merchant/Shop/OWNER tuple validated through Dubbo before writing. The Skill creates the MES unit, product category and product projection itself, then passes only the returned MES product ID to the work-order capability. It never asks a frontend or caller to manufacture an internal MES ID.

Execute only in local/test with skill ID `skill.cloudmold.mes.production.v1`, `references/hsf-full-chain-input.json`, and `--write-approved`. The current v2 scenario proves autonomous master-data creation plus the work-order lifecycle. A production-grade MES release additionally requires routing/task scheduling, material issue/receipt, quality, capacity, and produced-quantity evidence; those remain explicit follow-on graph nodes rather than being hidden behind this lifecycle result.

For replay or timeout recovery, keep the original business `--idempotency-key` while assigning a new evidence `--run-id`; query the work-order state before deciding whether another write is permitted.
