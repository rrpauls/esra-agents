---
name: esra-crisis
description: Triage active incidents and build resilience after failures using containment, recovery, and controlled tests. Skip ordinary debugging without urgent impact.
license: Apache-2.0
metadata:
  author: rrpauls
  version: "0.1.0"
---

# ESRA Crisis

Stabilize first; defer process optimization until immediate harm is controlled.

1. Establish known facts, affected people or systems, urgency, and what could worsen next. Distinguish evidence from speculation.
2. Prioritize immediate safety, data integrity, and essential operations. For physical emergencies, direct the user to appropriate emergency services; do not delay with a framework.
3. Recommend the smallest reversible containment step with an owner, verification, and rollback. Do not execute production changes or communications beyond authorization.
4. Communicate what is known, what remains unknown, and the next checkpoint. Do not fabricate monitoring or promise background updates without an actual supported setup.
5. After stabilization, identify failure mechanisms and concrete prevention or recovery improvements.

For resilience, examine single points of failure, redundancy, blast radius, observability, and recovery time. Introduce fault tests only in a bounded authorized environment with stop conditions and rollback; never create a real incident to learn from it.

Distinguish robustness, resilience, and evidence-backed improvement from failure. Do not claim a system benefits from volatility merely because it survived one failure. Keep incident responses short and actionable. Post-incident review must produce testable changes, not blame or speculative introspection.

Derived from `rrpauls/hermes-esra` and its host adaptations. Licensed Apache-2.0.
