---
name: cloudmold-supplier-return-finance-finalization
description: Posts the canonical valuation, accounts-payable, and journal reversal for a completed supplier return.
---

# Supplier return finance finalization

Use this R3 workflow only after the supplier return is physically `COMPLETED`. Freeze the return version, ledger, open accounting period, posting rule, and evidence hash in the approved input. The finance domain allocates the reversal against posted matched supplier invoices, reduces the AP open item and valuation layer, and posts a balanced immutable journal. Never edit warehouse, valuation, AP, invoice, or journal tables directly.
