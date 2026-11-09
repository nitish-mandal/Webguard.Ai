# Solo MVP scope

One operator, one exact owner-approved GitHub repository, Python 3.12 pure-Python
target, pytest, small source-only patches. The product's own UI is React/TypeScript;
that does not imply arbitrary JavaScript repair support. Docker isolates target
tests. SQLite durable jobs and a polling Python worker are sufficient initially.

Bug detection means observing and reproducibly classifying a pytest failure at
a pinned commit, not claiming every bug can be discovered. Candidate discovery
may suggest a new regression test only when its expected behavior is supported
by a documented contract and it fails on baseline. No reproducible failure means
no repair and no PR. Environment failures are a separate blocked/failure reason.

The operator supplies a report or selects the allowlisted target; execution
commands come from trusted service configuration, never from arbitrary UI input.
No autonomous browsing of production sites, arbitrary repository onboarding,
automatic merging, production deployment, billing, multi-tenancy, private data
ingestion or vulnerability exploitation. Add other adapters only after this
single-target workflow passes acceptance.
