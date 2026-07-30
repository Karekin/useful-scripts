---
name: cloudmold-consumer-paid-unshipped-order
description: Create one occurrence-fresh paid but unshipped consumer order for governed order-exception workflows. Use only as an internal test-data subflow under an approved parent.
---

# CloudMold Paid Unshipped Order Scenario

This `INTERNAL_SUBFLOW` is a test-environment business fixture. It resolves a real synthetic consumer and published listing, creates fresh inventory, places and reserves a new order, captures payment, confirms payment on the order, and creates an unshipped fulfillment.

It must not receive an independent daily Temporal Schedule. The order-exception parent owns approval, orchestration, cancellation decisions, compensation, and terminal evidence.
