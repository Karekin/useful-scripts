---
name: cloudmold-supplier-invoice-finalization-lifecycle
description: Independently approves and posts an exactly matched supplier invoice into AP and the general ledger.
---

# Supplier invoice finalization lifecycle

Use this R3 workflow only for a supplier invoice whose current lifecycle status is `SUBMITTED` and match status is `MATCHED`. Freeze the invoice identity and version in the approval input. The approver must differ from the invoice creator, and the poster must differ from the approver. The finance domain creates the AP open item, installment schedule, and balanced immutable journal; never mutate invoice, AP, or journal tables directly.
