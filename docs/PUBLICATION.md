# Verified draft publication (Phase 9)

`worker.publication.PublicationService(access).publish(lease)` is an explicit,
fenced controller operation. Offline is the default and needs no external token.
Phase 10 invokes it from the background worker; HTTP handlers never call it.
Call `close()` when done
with a live service to release its HTTP client. Never put provider credentials in
the frontend, VITE settings, a URL, command arguments or an evidence bundle.

## Preconditions and exact commit

The uncancelled job must be `verified` (or an interrupted `publishing` job) with a
current passing Phase 8 aggregate. A legacy exit-zero record is insufficient.
The publisher reopens the sealed baseline, checks current candidate/verification
IDs, SHA, profile/image, patch and hashed receipts, and revalidates source-only
edits. It reconstructs a clean owned attempt and confirms its full inventory/diff
matches the verified patch before holding only those edited UTF-8 source bytes.
It then removes the temporary attempt. Publication does not rerun target tests.

Only branch refs are supported for publication. The configured repository must
match exactly. Before creating a branch, before a PR and before local completion,
the base ref must still resolve to the verified baseline SHA. Any observed move
latches `base_moved`, preserves verified evidence and blocks the old intent even
if the ref later moves back. Create a new job at the new base and reproduce,
repair and verify there; there is no automatic rebase or evidence relabelling.

The dedicated branch is `webguard/jobs/<job-id>`. Live publication uses GitHub's
Git database REST API rather than a local checkout/push: create a tree based on
the exact baseline with only verified source blob replacements, create one
single-parent commit, then create its ref. The full resulting tree is checked
against the base, including original file modes and unchanged tests/config.
Symlinks/submodules/unknown files or a different parent/tree cannot pass. No
hooks, target installation, shell strings, model commands or test weakening run.
Commit author/time and job/verification/patch marker are service-owned. Existing
refs are never force updated. PR creation always sends `draft: true`; there is no
merge, ready-for-review, close or delete action.

The PR body gives the reproduced test/assertion, verified diagnosis, baseline SHA,
patch/evidence digests and commands, exit codes and test counts actually recorded
by Phase 8, including the deliberately failing unpatched regression control.
Untrusted snippets are bounded, redacted and Markdown escaped; mentions are
removed. Complete source/logs and credentials are not placed in the PR body.

## Durable retry protocol

SQLite migration 6 adds `publication_intents`, bound to existing job, verification
and publication records. It stores the immutable marker, repository/ref/SHA,
patch/evidence identities, mode, branch, created time, remote commit/PR IDs,
phase, static failure code and stale latch. Credentials are never persisted.
Observed PR metadata is recorded before the final base check. Only a matching
completed intent and the still-current proof can produce `draft_pr_created`.

Before every effect, a fenced transaction persists `branch_inflight` or
`pr_inflight`. Retries first look up the branch by its job-specific name and
validate its commit marker, parent and complete tree. PR lookup uses the same
head/base and all states, then validates marker, repository, draft/open state and
head commit. A timeout after GitHub acceptance, a restart, or a failed local
completion transaction therefore reconciles the existing result. A closed,
non-draft or foreign PR/ref blocks instead of creating another one. If an
in-flight effect remains invisible, `outcome_unknown` blocks blind reposts;
operator reconciliation is required. This is conservative at-most-one creation,
not a promise of availability during an indefinite remote visibility failure.

Mutation attempts debit the job's existing persistent publication budget. A
read-only reconciliation can complete an already accepted PR even after the
mutation budget is exhausted. Failures return to `verified` with its evidence
intact; they do not repeat Gemini, repair or Docker verification. Job deadlines,
leases, fencing and cancellation still apply at each effect and local write.
Cancellation prevents new effects/completion once observed; it cannot undo a PR
GitHub already accepted. Such a PR may need operator review. Terminal states are
protected and a completed retry reads the stored publication without new calls.

GitHub PR creation has no atomic expected-base-SHA precondition. The base can
move during the network request after the last check. The final check detects
that observed race, stores the returned PR number, latches the intent and refuses
local completion. An external draft can already exist in this case; the operator
must review it. Nothing is automatically merged. Later remote changes after a
successful publication are likewise outside that point-in-time guarantee.

## Live setup and bounded transport

Keep `ENABLE_GITHUB_DRAFT_PR=false` for offline work. Live requires all of:

- `ALLOWED_REPOSITORY=owner/repository` in canonical lowercase, exactly the approved repository.
- Private server `AUTH_TOKEN` and `GITHUB_TOKEN`; explicit `ENABLE_GITHUB_DRAFT_PR=true`.
- A short-lived GitHub App installation token (`ghs_`) restricted to **one**
  repository with Contents write and Pull requests write permissions.

This adapter deliberately supports only installation tokens whose repository
scope it can inspect with `GET /installation/repositories`. It checks total count,
exact repository identity and immutable repository ID against `GET /repos/...`
before writes. Classic PATs and multi-repository installation tokens are rejected.
Token issuance/refresh is operator-owned. Expired or insufficient-permission
tokens fail closed; never log or persist the raw response/exception. No live
credential was supplied or live publication tested in Phase 9.

Requests go only to `https://api.github.com` with REST version `2026-03-10`, no
redirects, ambient proxies or compressed bodies. Defaults: 30-second call
deadline, 5-second individual I/O timeout, 40 requests, 1 MiB response cap and
2 MiB request cap. Limits are validated settings in `.env.example`; response
pagination/truncated trees that exceed this MVP are blockers, not partial proof.
Errors stored/returned by the publisher are static codes without raw GitHub
responses or credentials. The controller owns the token outside Docker.

Official contracts used: [installation repositories](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-app-installation),
[Git trees](https://docs.github.com/en/rest/git/trees#create-a-tree),
[Git commits](https://docs.github.com/en/rest/git/commits#create-a-commit),
[Git refs](https://docs.github.com/en/rest/git/refs#create-a-reference),
[draft PR creation](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request).

## Offline acceptance

The deterministic fake uses a separate persistent SQLite remote at the owned
workspace root (`fake-github.sqlite`), so a job transaction rollback cannot undo
an accepted simulated request. Unique branch/marker keys enforce one fake draft
per job. Records contain `mode: offline`, `simulated: true`, a `simulated://` URL,
and a SIMULATED title/body. They are never presented as real GitHub PRs.

Run the product tests separately from the real Docker demo:

```powershell
.venv\Scripts\python.exe -m pytest -m 'not isolation' -q
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:WEBGUARD_ISOLATION_IMAGE = (Get-Content docs/baseline/phase8-image.json | ConvertFrom-Json).image_id
$env:WEBGUARD_RECORD_ACCEPTANCE = '1'
.venv\Scripts\python.exe runner_image/check_publication.py
```

The strict gate requires one passing, non-skipped case. It creates a temporary
Git copy of the unchanged demo, performs two real baseline runs plus all four
real Phase 8 checks using the same immutable v4 image, publishes with the fake,
reopens storage and retries, and requires exactly one simulated draft. Target
code runs only in Docker. Missing Docker returns a blocked gate, never a host
fallback. `docs/baseline/phase9-offline-demo.json` contains actual commands,
containers, results, verification and simulated publication metadata. Product
tests also cover stale bases, wrong repository, forbidden/tampered evidence,
timeouts after acceptance, invisible outcomes, cancellation, rollback and budgets.
MockTransport verifies the live REST protocol; it does not establish live access.

Phase 10 now invokes this service from the background pipeline; see WORKER.md.
The job UI remains follow-up work. Live publication acceptance requires
the scoped server token, approved repository and explicit opt-in above.
