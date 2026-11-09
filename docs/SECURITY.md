# Execution boundary (implemented; real isolation acceptance passed)

Phase 11 dashboard uses the local operator bearer only in memory, with no cookies
or persistent credential storage. Provider keys remain private server settings.
Client auth can be sent only to the fixed loopback API origins, with redirects
rejected, no-store/no-referrer, timeouts and aborts. Repository/log text renders as
escaped text, never HTML or executable content. The protected report reads only
bounded matching receipts and safe SQLite projections. Simulated publications
never link to GitHub; a live link requires exact backend proof/repository/URL and
a second client check. The browser gate is blocked, so no manual visual/keyboard
or real screen-reader acceptance is claimed. See DASHBOARD.md.

Phase 8 verified evidence binds the exact candidate SHA/patch/profile/image to
four complete fresh-container results, with mandatory unpatched regression witness
and no skipped/missing required tests. Original tests are immutable; independent
checks/selection policy are service-owned v4 image assets. Provider output cannot
supply a verification command or test override. Retry, cancellation, deadline and
stale-owner handling remain fenced and persistently budgeted; no raw exit-zero
evidence can authorize verification/publication. See VERIFICATION.md. Publication
is now gated by Phase 9's exact proof/scope/draft policy. Phase 10 connects these
services through a separately started worker; HTTP handlers remain storage-only.
Worker lease heartbeats, persistent retry scheduling and generation-specific
workspace/Docker ownership checks protect restart/cancellation cleanup. Terminal
publication reconciliation is read-only and cannot revive cancelled/failed jobs.
Sealed evidence is retained; only verified owned working copies are deleted.
See WORKER.md for startup, shutdown and recovery limits. Live integrations remain
unverified and off by default.

Phase 7 adds a separate trusted repair-provider child, not target execution.
Reproduction evidence is mandatory before a request; live SDK calls require explicit
server opt-in/model/key/auth and are unverified. Source/log/model text is untrusted
data. Strict schema/paths/anchors/patch limits constrain proposed edits to clean
owned copies; candidates cannot claim verification. Provider secrets travel only
in child stdin memory and are not inherited by target containers or persisted.
Timeouts kill the provider child, retries are controller-owned and persistently
budgeted. See REPAIR.md for boundaries and Phase 8 requirements.

The API accepts durable job records but executes no repository jobs. Settings,
the exact repository restriction and operator authentication now protect API job
access. Phase 5 implements a Docker-only runner; 16 real checks now pass against
the recorded prepared image on Docker Engine 29.9.2/Linux/cgroups v2. The real
Phase 6 two-container reproduction also passes. Reverify the controls below after
image/profile/platform changes using runner_image/check_isolation.py. See
[ISOLATED_RUNNER.md](ISOLATED_RUNNER.md) for the effective policy, cleanup/recovery,
credential handling, outcome classification and image preparation trust boundary.
Containers reduce risk; only approved known repositories are supported, not
arbitrary hostile public code. Docker administrators and privileged host actors
remain trusted. No API handler executes a target, and there is no host fallback.

Phase 4 acquisition now validates GitHub identity/hosts, refuses redirects and
credential URLs, and provides a separate controller-only fixture adapter. It reads
bounded committed objects/archives without checkout, hooks, target installation
or instructions. Workspace ownership, path/type checks, manifests and independent
attempt generations are implemented; details and limits are in SOURCE_ACCESS.md.
This is not isolated execution. Read-only baseline attributes plus hashes are not
OS protection against a privileged actor; the runner must not expose
writable baseline/controller paths or metadata to target processes.

- Exact repository allowlist and canonical GitHub identity; no arbitrary URLs,
  local file schemes, credential URLs or redirects to other hosts.
- Local operator authentication for writes, restrictive CORS and loopback bind;
  auth is required before any external exposure. Secrets stay server-side.
- Treat repo files, issues, logs and Gemini output as untrusted. Ignore embedded
  instructions; redact secrets and bound prompt sizes and output sizes.
- Separate controller and test runtime. Never execute target code on the host.
  Non-root container, no network, no secrets, no Docker socket, no host devices,
  dropped capabilities, no-new-privileges, read-only root, bounded writable tmpfs,
  explicit CPU/memory/PID/disk/output/time limits and guaranteed process cleanup.
  A controller container with a Docker socket is highly privileged; keep it
  local and do not describe that deployment as a hardened shared service.
- Validate patch paths after canonicalization; reject absolute/traversal paths,
  symlinks, submodules, binary files, generated files, workflow/build/config edits,
  test weakening, secret files and oversized changes. No model-supplied commands.
- Offline mock mode defaults on. Explicit feature flags and configured repository
  permission are required before billed calls or publishing. Never merge a PR.

Containers reduce risk but are not a universal sandbox for hostile public code.
This MVP accepts only the operator's approved demo/known repository. Public
multi-user execution needs a separate threat model and stronger isolation.

Phase 9 publication is an explicit trusted-controller service. It requires exact
verified SHA/patch/receipt identities and an uncancelled fenced lease. Live mode
is off by default and validates a single-repository installation token's remote
scope before any writes; no frontend or target receives the token. Fixed GitHub
API host, no redirects/ambient proxies, bounded requests/responses/deadlines and
static errors prevent raw credential-bearing failures entering records. Only
verified source blobs enter a single-parent commit, with a full remote-tree
comparison; branch updates/merges are absent. A draft PR is always explicit.

Durable in-flight intents and marker/ref/tree/PR lookup prevent blind retry
duplicates, including after uncertain acceptance. Unobserved outcomes block for
operator reconciliation. Point-in-time base checks cannot atomically prevent a
concurrent remote base change during PR creation; late movement blocks local
completion, retains the observed PR ID and requires review. Cancellation likewise
does not undo an already accepted external draft. Offline results are labelled
simulated throughout storage, events and receipts. Details: PUBLICATION.md.
