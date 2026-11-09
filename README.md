# WebGuard-AI

A solo-developer starter for a deliberately narrow repository repair service.
Open this folder in Google Antigravity, then give its coding agent
`docs/IMPLEMENTATION_PLAN.md` as the build instruction.

**The local background pipeline now works for the approved demo.**
The authenticated job API, separate lease-aware worker, Docker runner and offline
repair/verification/simulated-draft flow are implemented. The React operator
dashboard now submits jobs and shows real evidence/cancellation/publication data.
Phase 11 manual browser acceptance passed for job 802d2957d6ef48d182a8b04919e34165.
Phase 12 final product/frontend/build and all 24 real offline Docker checks pass.
Live Gemini/GitHub remain unverified: the operator deferred that run. Clean source
release and exact future private live settings: `docs/RELEASE.md`.
Phase 5 adds a Docker-only runner and trusted offline image preparation; all 16
real isolation checks now pass. No target code ran on the host. See
`docs/ISOLATED_RUNNER.md` for setup and the strict
acceptance gate. Phase 2 adds validated settings and durable internal job services;
Phase 3 adds an authenticated job storage API. Phase 4 adds approved-source
adapters and managed baseline/attempt workspaces; job execution remains disabled.
Phase 6 adds explicit two-run reproducible-assertion detection and durable evidence;
its real demo acceptance now passes with the same pagination assertion failure at
one pinned commit in two fresh containers. See `docs/REPRODUCTION.md`. Mock execution
does not establish reproduction. Phase 7 adds bounded repair providers and strict
source-only proposed candidates in clean copies. Offline is the default; the
official Google Gen AI SDK adapter is present but live calls are NOT VERIFIED.
Phase 8 now verifies exact candidates in fresh Docker containers: original test,
full suite and independent checks, with an unpatched regression witness. Its real
gate passes the valid fake repair and rejects two bad patches. The bundled demo
remains unchanged. See `docs/REPAIR.md` and `docs/VERIFICATION.md`. Phase 9 adds
verified draft publication with durable retry reconciliation: the Docker-backed
offline demo records exactly one explicitly simulated draft PR. The opt-in live
adapter is contract tested, with no real GitHub publication claimed. See
`docs/PUBLICATION.md`. Phase 10 connects the services in a separately started
worker. See `docs/WORKER.md` for startup/shutdown and real API-to-worker acceptance.
Phase 11 dashboard setup and remaining browser checklist: `docs/DASHBOARD.md`.
Offline startup needs no external credential. Job routes require a local operator
AUTH_TOKEN; see `docs/API.md` for the private header flow.

## First five minutes

1. Extract the ZIP. Open the extracted **WebGuard-AI** folder in Antigravity.
2. Read `docs/STATUS.md` and `docs/SETUP.md`.
3. Paste: â€œRead docs/IMPLEMENTATION_PLAN.md and execute its milestones in order.
   Begin by inspecting this scaffold and running its existing checks.â€
4. Let the agent build locally. Supply real credentials only when the live
   integration milestone is ready. Never paste secrets into agent messages.

## Layout

```text
backend/         FastAPI API and backend tests
frontend/        React + TypeScript + Vite status screen and component test
worker/          Lease-aware background pipeline, approved source services and Docker runner
runner_image/    Trusted offline image preparation, bootstrap and acceptance gate
tests/           Cross-component scaffold contract checks
demo-repository/ Small Python target with one deliberate off-by-one defect
docs/            Scope, architecture, setup, security, acceptance and status
.env.example     Configuration template; no secrets
docs/IMPLEMENTATION_PLAN.md  Complete build and verification instruction
```

## Local scaffold commands

Python 3.12+ and Node 22.12+ (or a compatible newer version) are required.
See setup for PowerShell and POSIX commands and environment loading.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --no-proxy-headers --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

API: http://127.0.0.1:8000/docs Â· UI: http://127.0.0.1:5173

`npm test` and `npm run build` run in `frontend/`. The demo's separate suite is
**expected to fail**, as recorded in earlier baseline evidence. Do not run target
tests on the host; use the Docker runner after its real isolation gate passes.
Both real Docker gates now pass on the recorded prepared image. Do not count the
known deliberate defect as a product failure or fix it during acquisition.

Phase 1 lockfiles and current tool blockers are documented in docs/PHASE_PROGRESS.md.
Python 3.12.10 clean installs and product tests passed; the separate demo fails as intended. Frontend checks passed. See Phase 1 progress for lint findings and later Docker blockers.
See `docs/DELIVERY_VALIDATION.md` for checks actually run before packaging.


