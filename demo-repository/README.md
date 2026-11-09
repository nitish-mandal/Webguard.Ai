# Approved demo target

This directory is a small Python repository fixture, not a separate Git repository
in the archive. Its pagination function deliberately returns one item too few.
Exactly one regression test should fail and one should pass before repair.

Run from the WebGuard-AI root: `python -m pytest demo-repository/tests`.
The main scaffold pytest command excludes this intentionally failing suite.

For real GitHub integration, copy this directory to a separate repository you own,
initialize Git, commit and push it yourself, and configure its exact owner/name.
The agent may automate these steps only with explicit repository/publication scope.
For the offline acceptance test, initialize a temporary local copy; do not change
this fixture. This target has no dependency installation or external network need.
