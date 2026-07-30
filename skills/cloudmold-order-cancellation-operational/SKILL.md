---
name: cloudmold-order-cancellation-operational
description: Run an occurrence-fresh paid-unshipped order through governed exception intake, assignment, compensation, and terminal closure. Use as the daily order-exception operator business role.
---

# CloudMold Order Cancellation Operations

This `BUSINESS_ROLE` models the order-exception operator’s main artery. A child fixture creates a new paid but unshipped consumer order for every Temporal occurrence. The operator then opens, notifies, and claims an exception case, starts the paid-order cancellation Saga, waits for fulfillment cancellation, payment refund, inventory release, and order cancellation, resolves the case, and verifies both case and cancellation terminal state.

The child is test-data support only and never receives its own daily Schedule. Production use still requires real PSP refund and fulfillment-provider authorities; the local flow proves the governed business orchestration and compensating state transitions.
