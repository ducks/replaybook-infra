# Repository → deployment

A source checkout and development README must become an operational deployment.
LedgerLens is a small Python CSV-import application with independent API and
worker processes, persistent uploads, a SQLite migration and token-based auth.
There are no supplied deployment manifests. The agent inspects the application,
packages a release, chooses its service layout and state paths, imports an old
instance's data, configures the edge and produces a repeatable installer.

This is an experimental 30-minute, one-attempt benchmark, separate from Core.
It does not yet have a measured model difficulty rating. No hosted service,
registry account, Docker or Kubernetes is required. The target host is NixOS;
its immutable standard unit tree is documented in the task, along with the
writable persistent systemd control path. A full NixOS rebuild is optional.

## Checks

From the pack root:

```sh
make deployment-check REPLAYBOOK_DIR=../replaybook-publish-crouton
make deployment-oracle REPLAYBOOK_DIR=../replaybook-publish-crouton
make deployment-controls REPLAYBOOK_DIR=../replaybook-publish-crouton
```

For a paid model trial, choose the provider/harness explicitly and pass
`benchmark-repo-deployment.toml` to Replaybook. It pins pack/scenario versions,
1800 seconds and one attempt. The oracle and local controls do not call a model.
Raw jobs belong in Replaybook's ignored `jobs/`, not this public pack.

The controller generates private record IDs, contents and credentials during
preflight. The guest sees the authorized prior-instance handoff, not the
controller's grading state. Runtime Nix inputs contain only the public source
repository, not the oracle, controls or verifier. The source must remain
unchanged; deployment files can be added alongside it.

Verification exercises real HTTP workflows and independently reads SQLite and
upload bytes over SSH. Historical completed, queued, interrupted and malformed
imports must survive; fresh unseen imports must produce correct totals or
explicit error states. Retries must not duplicate work, conflicting uploads
must be rejected, download URLs must use the public edge, and bad credentials
must be denied. The worker is stopped, receives queued work and is killed after
restart; its supervisor must recover it. The installer is rerun after new work
is accepted, followed by service restarts and a host reboot.

The handoff declares paths and service names; those declarations are checked
against live non-root process IDs, running release source, packaged source,
actual records and file hashes. Path aliases resolving into temporary/source/
release storage are rejected. The grader accepts different names, ports and
layouts. It never extracts or executes the agent's archive on the host.

The runbook is required, but its backup/restore and rollback prose receives only
basic presence checks. Those procedures are not yet exercised on a second host.
The deployment may briefly interrupt requests during installation. This is not
a zero-downtime rollout or a complete defense against a malicious root agent.
A useful next variant would test moving/restoring the generated deployment on
a fresh machine. No factory or deployment generator is implemented here.

See `validation.json` for actual VM results and development failures. Incorrect
controls must fail at a deployment contract, not during VM/adapter startup.
