# Repair proposals (Phase 7)

Phase 8 now consumes proposed candidates through VERIFICATION.md. New runtime
profile/image is v4; existing v3 evidence is preserved, not relabelled. The current
real demonstration verifies an exact deterministic fake patch in Docker. This
does not change Phase 7's offline default or live Gemini NOT VERIFIED status.

Phase 7 implements explicit repair proposals after reproducible detection. Offline
mode is the default; live Gemini calls are opt-in and **NOT VERIFIED**. A real
Docker reproduction followed by an offline proposal passes acceptance. Accepted
candidates remain proposed in repairing state and await Phase 8 verification.
No repaired-target test pass, automatic worker loop, Gemini live result or PR is
claimed. The bundled demo is unchanged.

## Controller and evidence prerequisite

Use `RepairService(access).propose(lease)` with the existing approved RepositoryAccess
and fenced JobService. The job must be reproduced (or resuming repairing), with
same-SHA durable detection evidence and its matching SHA256 receipt under the owned
workspace. An exported JSON file or failing exit code alone cannot authorize a
provider call. The service reopens/verifies the immutable baseline/profile and
checks both assertion observations, image/input identity and distinct runs before
constructing a prompt. Missing/tampered evidence blocks before provider usage.

Only the relevant allowlisted function snippets and bounded failing-test diagnostic,
comparison and signature are sent. Full repository files, whole logs, settings and
credentials are excluded. Known and generic secrets, terminal control sequences
and configured secret prefixes at truncation boundaries are redacted. The fixed
instruction labels repository/model text as untrusted data; no tools/commands are
requested or executed. Prompt data cannot select a provider/model/endpoint.

The required JSON response contains a diagnosis and source replacements:

```json
{"diagnosis":"The slice endpoint drops an item.","edits":[{"path":"pagination.py","old_text":"return items[start:start + page_size - 1]","new_text":"return items[start:start + page_size]"}]}
```

Pydantic rejects extra fields, type coercion and invalid lengths. The parser rejects
duplicate JSON keys, Markdown fences, oversize output, blank diagnoses and invalid
Unicode. Raw malformed responses/SDK errors are never persisted or returned.

## Providers, credentials and limits

The deterministic FakeRepairProvider recognizes only the demo's exact off-by-one
anchor. It is a fixture-specific proposal, not a general repair algorithm or proof
that the edit works. Offline mode requires no API credential and imports no SDK
client for generation.

GeminiRepairProvider uses the official `google-genai` SDK, locked at 2.34.0. Live
selection requires ENABLE_LIVE_GEMINI=true, explicit GEMINI_MODEL, GEMINI_API_KEY
and local AUTH_TOKEN. Settings and the provider independently enforce that gate.
There is no default model and no live request was made during implementation.
The SDK contract was tested with an injected client and its real configuration
types, not external credentials. Supported live model behavior/quota is not claimed.

Both providers use a trusted killable controller child process. The API key is
passed only through stdin in memory, never argv, target environments, logs or disk.
The child inherits only essential OS runtime variables; ambient Google credentials,
endpoint overrides and proxies are omitted. SDK HTTP uses trust_env=false and a
timeout in milliseconds, no automatic function calling/tools and JSON-schema output.
SDK retry attempts=1 disables hidden retries; the controller owns every retry.
Parent wall/output limits stop the process even if SDK timeout handling stalls.

Defaults in .env.example:

| Setting | Default |
| --- | --- |
| REPAIR_INPUT_BYTES | 16384 including context, schema and fixed instruction |
| REPAIR_OUTPUT_BYTES | 16384 combined child output cap |
| REPAIR_OUTPUT_TOKENS | 2048 provider generation cap |
| REPAIR_CALL_SECONDS | 20, capped by remaining job deadline |
| REPAIR_MAX_RETRIES | 1 retry; only timeout/unavailable errors retry |
| REPAIR_COST_MICROS_PER_CALL | 100000 conservative operator accounting reservation for live calls |

Before each attempt, reserve one persistent model call, input-byte upper bound plus
output token cap/overhead, and live cost allowance. No refund/reset after failures,
retries or restart. The cost allowance is operator accounting, not a billing quote
or a claim about provider pricing. Job-snapshotted call/token/cost/repair limits are
authoritative. Offline attempts reserve calls/tokens but zero provider cost.
Lease/deadline/cancellation checks run while waiting; stale/cancelled owners cannot
apply or record candidates. Retry failures leave repairing with bounded rejection
events; exhausted budgets prevent further provider work.

## Patch validation and durable handoff

Only exact profile allowlist paths ending .py are eligible. Tests, hidden paths,
secrets, dependencies, configuration, workflows, absolute/traversal/drive/ambiguous
paths are rejected even if a response names them. No file addition/deletion/rename
or multiple edits to one file is supported. Old anchors must occur exactly once
in the pinned original and be present in the supplied relevant snippet. Reject
no-ops, invalid syntax, credential-bearing replacements, oversized files and
persisted patch-file/line limit violations. AST parsing only checks syntax; it
does not import, compile or execute target code. Diff work is bounded to edit text.

All edits validate before creating a new independent attempt. Owned baseline and
attempt checks reject symlinks/junctions/hardlinks. Inventory afterward proves only
approved files changed; tests/dependencies/other bytes remain unchanged. The patch
digest uses the runner's canonical baseline-manifest plus final file-hash inventory,
so Phase 8 can independently check the exact candidate. Baseline/fixture are never
modified. Apply/storage failure cleans only that verified owned attempt and receipt;
unsafe paths fail closed rather than following links during deletion.

SQLite migration 4 adds repair_candidates with unique (job, repair_attempt), pinned
SHA/profile/source/detection identities, attempt ID, patch/receipt digests, provider,
redacted diagnosis, files and status=proposed. Candidate write/event are transactional
and fenced. Receipts live outside target trees and carry untrusted_model_data=true.
Resuming an already proposed attempt returns the durable candidate without another
provider call. No automatic transition to verifying/verified occurs. Future Phase 8
must reopen/revalidate source, candidate bytes/digest and clean isolated verification.

## Actual acceptance and setup

Install current requirements-dev.lock with hashes using the existing Python 3.12.10
runtime; the updated uv lock resolves 46 packages. A fresh local venv install and
editable project install were run and matched all 45 installed Windows distributions.
Both installs use SDK 2.34.0. The Linux runner wheels/profile/image are unchanged.

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/docker-resume-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_repair.py
```

The gate requires a real two-container reproduction at a newly pinned temporary Git
commit, then an offline candidate; it returns 2 for unavailable/skipped Docker,
1 for failures and 0 only for the required case passing. It does not test the patch.
Current result: passed, zero skips. Proof/patch metadata:
baseline/phase7-real-proposal.json and phase7-proposal-receipt.json. No current Docker
blocker exists on this accepted setup. Phase 8 independent candidate verification
is now implemented; see VERIFICATION.md. Live Gemini remains unverified and optional.

Official interfaces consulted: [Google Gen AI SDK](https://googleapis.github.io/python-genai/),
[structured output schema](https://googleapis.github.io/python-genai/#json-response-schema),
[SDK source](https://github.com/googleapis/python-genai).
