---
name: cloudmold-r3-acceptance-policy
description: Restrict the internal DeerFlow R3 acceptance agent to the fixed commerce full-chain submit and durable task query tools.
allowed-tools:
  - cloudmold-hsf_cloudmold_skill_task_submit_commerce_full_chain_r3
  - cloudmold-hsf_cloudmold_skill_task_get
---

# R3 acceptance tool boundary

This policy is only for the hidden `internal_test` acceptance agent.

- Accept only an exact, already-approved `skill.cloudmold.commerce.full-chain-hsf.v1@1.2.0` submission.
- Submit the fixed R3 task once, then query the returned task identifier.
- Never invoke a domain write capability directly.
- Never reinterpret, broaden, repair, or invent approval scope or task input.
- If either permitted tool is unavailable or rejects the exact arguments, stop and report failure.
- This policy does not issue an approval and must never be attached to a business-role agent.
