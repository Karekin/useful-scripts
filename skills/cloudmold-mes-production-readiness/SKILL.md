---
name: cloudmold-mes-production-readiness
description: Prepare one occurrence-fresh MES product, workshop, workstation, process, and enabled key-process route for a managed production run. This is an internal SkillTask child, not an independently scheduled operator.
---

# CloudMold MES Production Readiness

This `INTERNAL_SUBFLOW` creates the MES prerequisites for one test-environment production occurrence. It returns real IDs for the product, workshop, process, workstation, route, and route process; callers never synthesize database identifiers.

All nine writes are idempotent through persisted SkillTask step keys. The daily production supervisor workflow owns scheduling and business closure.
