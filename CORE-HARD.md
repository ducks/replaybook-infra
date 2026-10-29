# Core Hard — experimental incident suite

Core Hard is a separate candidate suite, not a change to frozen Core
2026.10.24.2. Its executable manifest is `benchmark-core-hard.toml`, benchmark
ID `replaybook-infra-core-hard`, version `2026.10.28.1`. It uses the existing
`frontier` tier while these candidates are evaluated. Do not pool its results
with Core or describe it as proven harder before comparing model runs.

Three scenarios test investigation beyond a single failing health check:

| Scenario | Incident | Preserved state |
| --- | --- | --- |
| `034-checkout-dependency-rollout` v1 | A partial deployment leaves stale upstream configuration at two boundaries; fixing only one does not restore checkout | Historical invoice IDs and full JSON bodies; failed orders must subsequently succeed |
| `035-notification-outbox-rollout` v1 | The API accepts current-format notifications while a worker still decodes the previous format | Pending messages, historical receipts, exact payloads, and one receipt per accepted ID |
| `036-reservation-write-contention` v1 | A compatibility write path loses capacity updates under concurrent requests; correcting future writes alone leaves historical drift | Every accepted reservation, quantity, payload, and original total capacity |

Each scenario boots disposable NixOS services behind Nginx. Application sources
and configuration are available for normal host investigation. Controller hooks,
incident contracts, reference repairs, and expected record sets stay outside
the guest. SQLite observations are streamed over the controller SSH connection;
verification does not trust an application's success response alone.

Preflight creates unpredictable identifiers and payloads, records them outside
the VM, and proves both the healthy control path and the incident. Verification
checks the old records before adding new concurrent work, then checks accepted
bodies, idempotent retries, and scenario-specific invariants. The harness repeats
verification immediately, after service restart, and after host reboot.

The suite specifies three attempts per scenario, a 900-second agent deadline,
and host harness v23: nine trials per model configuration. A single oracle or
model smoke attempt is development validation, not a published model score.

## Validate and run

Set `REPLAYBOOK_DIR` when Replaybook is not at `../replaybook`:

```sh
make core-hard-check REPLAYBOOK_DIR=/path/to/replaybook
make core-hard-oracle REPLAYBOOK_DIR=/path/to/replaybook
python /path/to/replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-core-hard.toml \
  --models PROVIDER/MODEL --agent-provider openrouter \
  --claux-binary /path/to/claux --reasoning-efforts high \
  --concurrency 1 --base-port 24400
```

The oracle command runs one attempt per scenario and uses the normal execution
snapshot and external verification lifecycle. Check disk, memory, and ports
before a matrix. Tests use real local HTTP servers and SQLite and require local
socket access. They include controls for dropped historical records, missing or
duplicate receipts, unreconciled capacity, non-atomic future writes, and changed
total capacity.

Results, private transcripts, and VM logs belong in ignored `jobs/` directories.
Before a public comparison, freeze the pack and controller, retain normalized
results and source digests, and review model smoke evidence for answer leaks or
verification gaps. Any scoring-affecting revision bumps its scenario and pack
versions; Core's manifest and existing scenario versions remain unchanged.

## Development validation

[Retained validation evidence](validation/core-hard-20261028.json) records the
three oracle trials and one DeepSeek V4.1 Flash 1017 smoke trial per scenario.
All six trials passed immediate, service-restart, and host-reboot verification.
The evidence includes scenario fingerprints, controller and agent digests,
normalized outcomes, reported usage, and raw-result SHA-256 digests. Current
scenario trees were checked against both immutable execution snapshots.

DeepSeek repaired these candidates in 53–96 seconds in this initial smoke run.
This does not establish that the candidates are harder than Core; further
comparisons should test their value before adopting a stable Hard suite.
Controller-filename markers were absent from all three model transcripts.
Private transcripts and raw VM artifacts are retained locally, not published.
