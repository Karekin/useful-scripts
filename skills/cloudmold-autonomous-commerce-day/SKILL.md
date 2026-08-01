---
name: cloudmold-autonomous-commerce-day
description: Run the governed daily operations-control loop across CloudMold commerce roles and verify every child workflow reaches an auditable terminal state.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: operations
    role: operations-control
---

# Autonomous Commerce Day

Runs a real operations-control role loop rather than a composition-only shell.

Each Temporal occurrence creates and claims a fresh commerce-operations action case, creates a new governed product and published listing, then hands that exact listing to a simulated consumer. The consumer completes browsing, product-detail viewing, favorites, cart, checkout, order/payment/fulfillment, after-sale, customer service, and community publishing. Only after both child business chains succeed does the operations role resolve its own action case and verify the `RESOLVED` terminal state.

The rotating input factory derives unique product, listing, consumer, order, service, community, and operations-case identities from the Temporal occurrence key, so daily automation does not replay yesterday's SPU.
