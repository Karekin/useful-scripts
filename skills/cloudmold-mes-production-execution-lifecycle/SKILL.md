---
name: cloudmold-mes-production-execution-lifecycle
description: Run one occurrence-fresh product through MES readiness, work-order confirmation, task dispatch, production feedback, qualified output receipt, work-order completion, and terminal readback. Use as the managed production-supervisor business role.
---

# CloudMold MES Production Execution Lifecycle

This `BUSINESS_ROLE` models the production supervisor’s main artery. Temporal persists the parent and child ledgers, retries every write with the same step idempotency key, and runs a new occurrence each day.

The readiness child creates a fresh product and production line for the test occurrence. The role then confirms a fresh work order, dispatches a task, records 100% qualified production feedback, approves the resulting product receipt into the virtual WIP warehouse, finishes the work order, and accepts success only when the work order, task, feedback, and product receipt are all terminal with positive output.

It is not a technical health check and must not be scheduled without the `production-supervisor` approval route.

V1 deliberately uses a non-batch finished product and proves the production supervisor's work-order-to-qualified-receipt artery. Raw-material BOM, issue/return, batch genealogy, multi-operation or outsourced production, equipment/OEE, and production cost settlement remain follow-on business workflows; do not claim those outcomes from this definition.
