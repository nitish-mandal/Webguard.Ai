# Approved source access and workspaces (Phase 4)

Source acquisition is not isolated execution. These components parse/copy source
on the controller but never import it, install it, run tests or execute repository
instructions. No HTTP handler or polling worker invokes acquisition automatically.
`worker.run_job` still raises its explicit not-implemented error.

## Controller interfaces

`RepositoryAccess.github(jobs)` uses only the exact canonical lowercase
owner/name in ALLOWED_REPOSITORY. It rejects the reserved demo identity; a real
owner/name must be approved explicitly. `RepositoryAccess.fixture(jobs, git_dir)`
is separate and only supports the reserved demo identity. That local path is a
trusted controller/test dependency, never an HTTP request or target setting.
The fixture must be an ordinary, operator-prepared Git directory, not the bundled
non-Git demo directory or a linked worktree. Product tests initialize temporary
Git copies; the bundled demo is never initialized, modified or executed here.

The underlying adapter's constructor identity is controller configuration, not a
request selector; RepositoryAccess also checks it against JobService settings
before use. Neither adapter accepts a per-operation URL, command or local path.
The HTTP API continues to reject path/fixture_path/workspace_root and other extra
request fields. Local directories cannot be selected over the API.

`prepare(lease)` requires a live fenced lease and baselining state. It resolves
the requested ref, or an explicitly supplied/already pinned SHA, and persists the
immutable SHA with `pin_revision`. Once pinned, branch movement cannot change it.
It then acquires source, seals/verifies it and transactionally records one
source_snapshots row and a source_acquired event. Schema migration 3 adds that
table; source metadata contains only identifiers/digests/timestamp, not local
paths or credentials. Acquisition is not pytest baseline evidence and never
authorizes reproduced/verified by itself. State remains baselining.

On restart, existing metadata reopens and verifies the same baseline without
resolving a moved ref. A changed profile, missing workspace or altered baseline
fails closed. Failed acquisition retains the pinned SHA, removes its new owned
workspace and can retry that exact SHA. Cancellation/stale ownership prevents
recording acquisition. Database/event failure rolls back the snapshot record and
cleans its unique workspace. Acquisition rejections use SourceError codes;
storage and ownership exceptions retain the Phase 2 service contracts. A future
orchestrator must classify failures and renew/reap leases. No such loop is added.

`attempt(lease, number)` checks current ownership before and after preparing a
copy. Physical copy creation does not spend a model/repair attempt; the future
orchestrator must use the existing job-state and reservation services for that.
WorkspaceManager is an internal controller capability, not a network API.

## Remote and local acquisition

The public GitHub adapter constructs endpoints on api.github.com and
codeload.github.com only. It validates repository full_name, resolves a commit
and its tree, rejects truncated recursive trees, and inspects modes/sizes/paths
before requesting an archive. Redirects are rejected even within trusted hosts,
so renamed/transferred repository redirects require explicit operator review.
URLs, embedded credentials, SSH/local/file schemes and alternate hosts cannot
be supplied as identities. TLS verification uses Python's default trust store;
there is no insecure-TLS option. Environment proxies, cookies and Authorization
headers are not used. Private/authenticated repository access is not implemented;
GitHub source reads never forward the configured future publication token.

HTTP bodies are streamed with compressed/metadata caps, socket timeouts up to five
seconds and a shared monotonic acquisition budget checked around reads. read1
returns available chunks rather than waiting to fill a large buffer. Network
timeouts are not an OS resource sandbox: DNS/kernel/network stalls can affect
wall-clock timing. No hard network/isolation attestation is claimed. Public
GitHub availability and rate limiting can fail source access; errors fail closed.
No actual GitHub download was performed in Phase 4 validation: remote tests use
mocked API/archive responses and transport objects.

Archives are never extractall'd or checked out. Compressed and decompressed
streams, member counts and declared/actual file sizes are bounded. Only inspected
regular files are materialized; blob content must match the tree's Git object ID.
Symlinks, submodules/gitlinks (including those without .gitmodules), .gitmodules,
hardlinks, sparse/special members, traversal, absolute/drive/ADS/backslash paths,
Windows reserved names, case collisions and duplicate/unexpected archive files
are rejected. Directory components are portable and limited to 16 levels and
relative paths to 240 characters. Overly large/unsupported repositories fail
rather than being partially accepted. Empty source repositories are unsupported.

The fixture adapter runs only structured, shell=False Git rev-parse, ls-tree and
cat-file operations, against committed objects, in a service-owned working
directory. It never copies the fixture working tree or untracked files. Git
stdout/stderr, duration and blob output are bounded, and the process is killed
on timeout/output overflow. The child environment is an essential OS allowlist
plus explicit Git controls: no prompts, global/system configuration, credentials,
lazy fetching, replacement objects, pager, hooks, fsmonitor or allowed protocols.
No checkout/smudge/clean/build/install command is invoked. Source-provided Git
configuration or instructions cannot supply a controller command.

## Profile and workspace integrity

DEMO_PROFILE is a frozen, code-owned Python 3.12 profile for the approved demo (or
its approved GitHub copy). Phase 8 upgrades the trusted profile to v4:
python -I -B -m pytest -q --capture=no -c /opt/webguard/pytest.ini -p no:cacheprovider -p webguard_report tests.
Existing v1/v2/v3 snapshot digests are immutable; create a new job/snapshot and image
for v4. See REPRODUCTION.md and VERIFICATION.md for bounded reporting/check contracts.
Editable source: pagination.py only; tests/configuration are excluded. Other
repository layouts require an explicitly reviewed controller profile; there is
no repository-driven profile inference. AGENTS.md, dependency files, attributes
and instructions in source are inert data and cannot override the profile.

The dependency recipe is data only: offline, binary-only, --no-deps installation
from a prepared /wheels set, with pytest 9.2.0, iniconfig 2.3.1, packaging 26.3,
pluggy 1.7.0, pygments 2.21.0 and colorama 0.4.6 pinned. These versions already
exist in the product lock. Nothing executes that recipe in Phase 4. Phase 5 must
prepare/hash/validate the platform-specific wheel set and build the isolated
runtime; no target dependency preparation or clean target environment is claimed.
Source-edit allowlists are declarations for the future patch validator, not an
implemented repair/patch engine.

WORKSPACE_ROOT must be a dedicated empty directory or a previously owned root.
An ownership marker is created exclusively; nonempty unmarked roots are not
adopted. Root and descendant symlinks, Windows junctions/reparse points and hardlink
file aliases are rejected. Each acquisition has a unique job-id/workspace-id
directory with a checked ownership record. Baseline data has no .git directory.
A canonical manifest stores the commit, code-owned profile and relative
size/SHA256 entries. Its digest/profile digest are also persisted in SQLite.

Baseline files are read-only and their contents are reverified before copies.
Read-only attributes are not kernel-enforced immutability against the controller
owner: the integrity manifest detects tampering. Phase 5 must not expose writable
baseline, controller, DB or ownership metadata paths to target code. This is
workspace integrity, not a sandbox or a hostile multi-user service guarantee.

Every attempt/reset gets a fresh generation directory, even for the same logical
attempt number. It contains independent regular-file copies and separate trusted
SHA/manifest/profile metadata outside the copy. Old artifacts stay in the old
generation until cleanup and cannot carry into a reset. Unique paths prevent an
expired owner from deleting a newer owner's copy. No hardlinks or shared mutable
source trees are used. Baseline integrity is checked again after copying.

Cleanup accepts only validated Workspace identities, revalidates root/job markers,
resolves the exact owned absolute target and scans for unsafe links/types before
recursive deletion. It never accepts an arbitrary path or deletes the root.
Read-only files are made writable only after these checks. Symlink/junction,
hardlink, ownership mismatch or ambiguous paths are left for review, not followed.
An incomplete root/job whose ownership marker could not be written is not blindly
deleted. Clean up only when the controller has quiesced the relevant work; these
operations are not interprocess locking or protection against a privileged actor
concurrently rewriting the service's private filesystem. Removing a successful
snapshot's files retains its DB audit record; reopening it then fails closed.

## Configuration and Phase 5

Defaults in .env.example: WORKSPACE_ROOT=workspaces, SOURCE_TIMEOUT_SECONDS=20,
SOURCE_MAX_FILE_BYTES=1048576, SOURCE_MAX_TOTAL_BYTES=10485760,
SOURCE_MAX_FILES=1000, SOURCE_MAX_ARCHIVE_BYTES=10485760,
SOURCE_MAX_METADATA_BYTES=1048576. These are validated controller limits, not
API parameters. Git stderr is separately bounded to 64 KiB. The effective prepare
budget is capped by remaining job deadline and lease lifetime. No source operation
resets persistent job budgets. Git 2.55.0.windows.5 and Python 3.12.10 were tested;
other platform/tool combinations are not claimed verified.

Phase 5 now provides Docker-only execution, checked wheel artifacts, an offline
image recipe, resource/network/output limits, owned cleanup and 16 real boundary
test cases. Docker Engine 29.9.2/Linux/cgroups v2 now passes all 16 real cases;
the Phase 6 temporary-Git demo reproduces the same assertion twice at a pinned SHA.
Actual image/build/execution receipts are recorded in PHASE_PROGRESS.md and
docs/baseline/docker-resume-*. See ISOLATED_RUNNER.md for contracts/setup. Do not execute target
pytest, install scripts or repository instructions on the host as a fallback.

Official references consulted: [GitHub Git trees](https://docs.github.com/en/rest/git/trees),
[Git cat-file](https://git-scm.com/docs/git-cat-file),
[Git configuration](https://git-scm.com/docs/git-config).
