---
name: cloudmold-consumer-shopping-journey
description: Run a clearly identified synthetic-consumer journey through discovery, purchase, fulfillment, after-sales, service, and community readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: user
    role: synthetic-consumer
---

# Consumer Shopping Journey

Simulates one governed consumer persona from discovery through search, product-detail viewing, favorite, cart, checkout, payment attribution, fulfillment, after-sale resolution, customer-service consultation, and a moderated community post.

The definition is a durable SkillTask workflow. Temporal owns the daily parent run; every write uses a step idempotency key and the canonical domain command APIs.
