# Consumer Shopping Journey

Simulates one governed consumer persona from discovery through search, product-detail viewing, favorite, cart, checkout, payment attribution, fulfillment, after-sale resolution, customer-service consultation, and a moderated community post.

The definition is a durable SkillTask workflow. Temporal owns the daily parent run; every write uses a step idempotency key and the canonical domain command APIs.
