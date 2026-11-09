# Release gates for the implementation agent
+
1. Offline: on a temporary Git copy of the demo, baseline fails the first-page
   regression and passes invalid-input test. Deterministic fake Gemini returns
   a minimal source-only repair; the isolated runner verifies both tests and
   additional boundary cases. A fake GitHub adapter records exactly one draft PR.
   Clearly label this as mocked integration, not live Gemini/GitHub verification.
2. A healthy target produces no_reproducible_bug and never calls Gemini or GitHub.
3. An invalid target, hostile path, prompt injection, network-dependent test,
   timeout, oversized output, forbidden patch or attempted test deletion fails
   closed with a useful reason and no publication.
4. Model outage, malformed output, budget exhaustion and repair regression never
   produce a PR. Patch proposals cannot change baseline tests or trusted commands.
5. Worker crash/restart, expired lease, duplicate API request, cancellation and
   GitHub timeout after PR creation do not create duplicate jobs/branches/PRs.
6. API authorization, input validation and redaction tests pass. UI covers queued,
   progress, failure, cancellation, no bug, verified and draft-PR states accessibly.
7. Optional live gate: with explicit credentials and configured opt-in, run one
   demo job using actual Gemini and GitHub, verify PR draft=true, inspect the diff
   and link checks/evidence. If unavailable mark live integration NOT VERIFIED.
8. Root tests, frontend tests/build, lint/type checks, actual isolation integration
   tests and documented clean-install setup pass. Mock tests do not substitute
   for executing the test runner boundary. Record tool versions and commands.
