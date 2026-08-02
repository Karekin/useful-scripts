---
name: cloudmold-procurement-receipt-accounting-lifecycle
description: Executes the governed CloudMold procurement receipt acceptance, valuation, supplier invoice, three-way match, AP, and journal lifecycle.
---

# Procurement receipt accounting lifecycle

Use this business-role workflow only after a canonical warehouse receipt and its procurement quality inspection have been recorded. Supply frozen identifiers, versions, monetary values, accounting policy versions, evidence hashes, and distinct active actor principals in `skill-task.json` input.

The workflow completes the inspection through an independent quality actor, posts the qualified receipt valuation, then creates, submits, three-way matches, independently approves, and independently posts the supplier invoice. Every write is R3-governed, idempotent, and persisted by the owning domain; do not replace any step with direct table writes or inferred identifiers.
