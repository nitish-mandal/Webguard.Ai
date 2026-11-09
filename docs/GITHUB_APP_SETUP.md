# Private setup for the single approved live run

No job should be submitted during setup. Both ENABLE_LIVE_GEMINI and
ENABLE_GITHUB_DRAFT_PR stay false. The approved scope is
nitish-mandal/webguard-live-demo, base main. Source upload commit:
https://github.com/nitish-mandal/webguard-live-demo/commit/b5621b9be3e6b1eabdcb1798ba877016d33a6ce6

## Model

Privately enter this non-secret model setting in the root .env:

```dotenv
GEMINI_MODEL=gemini-3.8-flash
```

As checked 2026-11-06, Google's current model documentation lists this ID with
structured output support. The existing Google Gen AI adapter sends a JSON
schema and bounded generate_content request. This is documentation compatibility,
not a tested response, account entitlement, quota or patch-quality guarantee.
No model generation was performed to choose it. Do not use older 2.5 IDs merely
because historical examples mention them.

Official references:
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/generate-content/structured-output

## Register and install your GitHub App

1. Sign in at https://github.com/login in your own browser. No password or token
   belongs in this chat.
2. Open https://github.com/settings/apps/new (Settings -> Developer settings ->
   GitHub Apps -> New GitHub App).
3. Choose a unique app name, for example WebGuard-live-nitish-mandal. Use
   https://github.com/nitish-mandal/webguard-live-demo as Homepage URL. Leave
   callback/user-authorization features unused and disable Webhook Active;
   this local installation-token flow needs neither callback nor webhook server.
4. Under Repository permissions set Contents to Read and write, Pull requests to
   Read and write, and Metadata to Read-only (normally automatically required).
   Leave other repository/account permissions and event subscriptions unset.
5. Under where the app can be installed, select Only on this account. Create it.
6. On its General page note the Client ID (not Client secret). Under Private keys
   click Generate a private key. Keep the downloaded PEM locally outside the
   project/source archive; never paste its contents into chat or .env.
7. Open Install App -> Install for nitish-mandal. Select Only select repositories
   and choose exactly webguard-live-demo. Confirm the permissions and Install.

Official registration/install steps:
- https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app
- https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app

## Generate the short-lived installation token locally

GitHub requires exchanging a signed app JWT for an installation token; a client
secret, PEM file or app JWT itself is not the GITHUB_TOKEN this product accepts.
Installation tokens expire after one hour. Generate one near the planned run.

From a private PowerShell terminal in the project root, run:

```powershell
.venv\Scripts\python.exe scripts/create_github_installation_token.py
```

Enter the App Client ID and the downloaded PEM path when prompted. The PEM path
prompt is hidden. The helper uses the already locked cryptography/httpx/dotenv
libraries, sends an RS256 app JWT only to api.github.com, resolves this repository's
installation, and requests exactly:

```json
{"repositories":["webguard-live-demo"],"permissions":{"contents":"write","pull_requests":"write","metadata":"read"}}
```

It verifies that the minted token can access exactly the approved repository and
has the requested permissions, then writes GITHUB_TOKEN directly to the private
root .env. Existing operator/Gemini credentials, other settings and both false
live flags are preserved. It prints only success booleans and repository identity,
never the token, JWT, key or API response. You do not need to copy any secret into
a shell command, clipboard or chat. The helper does not push files or create PRs.
No actual token issuance was tested before your App/key exists; its tests use a
mock HTTP transport only. On failure it returns a generic message; inspect App
registration/installation/permissions locally rather than sharing credentials.

The helper requests one token and has no automatic retries. If it reports failure,
the token is not confirmed saved. Do not treat the existing .env token as newly
validated. Keep live flags false while diagnosing. Token scope verification does
not authorize or submit a repair job.

Official exchange and JWT instructions:
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app

## Report readiness before any job

After privately setting the model and generating the installation token, reply
"setup complete" without including credentials. Rerun the read-only preflight:
repository/ref/files, setting presence, token format/expiry/scope, live flags off,
prepared Docker image and bounded settings. Report readiness before any submission.
The existing check_live_configuration.py requires live flags true to call a live
configuration runnable, so with both intentionally false it will continue to
report those flags as blockers even after all other settings are ready. Do not
turn them on just to make that checker green. Do not restart the existing offline
API/worker into these settings or submit a job as part of this setup.
