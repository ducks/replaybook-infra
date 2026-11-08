# SRE incident families: development pack

This self-contained pack starts two new incident families without changing the
existing Core manifest or its frozen cohort. Pack ID: `ducks/replaybook-sre-families`.
Version: `20261107.0.1`. DNS is version 1; storage is version 2 after strengthening its cross-phase receipt checks.

| Scenario | Family | Operational failure | Required recovery |
| --- | --- | --- | --- |
| 041 DNS resolver drift | dns-service-discovery | A boot-applied resolver policy points the gateway at the wrong local nameserver | Real name-based inventory access and unrelated metrics resolution survive policy reapplication/restart/reboot |
| 042 Receipt directory ownership | storage-access-control | A storage policy assigns the write directory to the wrong owner | Non-root writes and retries recover, history and accepted data survive, permissions stay restrictive |

These are new development incidents, not established harder benchmarks and not
training examples yet. `families.json` provides taxonomy. Do not randomly split
attempts between training and testing. Reserve families/variants before collecting
model examples, and record the resulting assignment in the curation split plan.

## Run locally

```sh
REPLAYBOOK_DIR=/path/to/replaybook make validate check test
# Two fresh VMs with reference repairs, including service restart and host reboot:
REPLAYBOOK_DIR=/path/to/replaybook make oracle
```

The standalone worker baseline is copied from the parent pack's public
`worker/base.nix`; the pack has no imports outside its own directory. Scenario
instructions, applications and provisioning remain agent-visible. Reference repair
scripts and controller state are not copied into the guest by the model path.
Do not package whole scenario directories as application artifacts: that could
expose reference repairs. Standard Replaybook guest isolation still applies.

## Acceptance and failure controls

DNS preflight checks the backend independently before reproducing the gateway's
503 response. Verification requires correct inventory and unrelated DNS responses.
Changing only the current resolver file is not durable: service-restart verification
reapplies the boot policy. Hard-coding an IP in the gateway or bypassing unrelated
resolution fails the intended contract; editing application code is forbidden.

Storage preflight records failed request IDs in opaque controller state. Verification
retries those IDs, creates fresh records and rechecks every previously accepted record before generating writes on each
lifecycle phase. The same controller state persists across phases. History, exact
service identity and directory policy are checked separately. Root execution,
world-writable storage, deleting history, or acknowledging writes without storing
them are not accepted. The app checks real OS permissions and fsyncs receipt data.

Contract-control tests exercise DNS collateral damage, root/world-writable shortcuts,
lost history, and false write acknowledgments using deterministic response fixtures.
The receipt application test exercises actual file permissions and writes. These
are not a claim that a root-capable malicious agent cannot forge an application;
observable contracts, instructions and retained trajectories must be reviewed too.

Next variants should introduce causally distinct incidents, for example a stale
host override or exhausted inodes. Do not simply rename services or change ports.
Kubernetes/network-policy incidents remain future work; no Kubernetes dependency
has been added to this initial pack. Reference validation does not require paid model tests.

## Particle pilot

On 2026-11-07, Particle-1 through OpenRouter and the frozen Claux agent passed
one attempt per scenario, including immediate, service restart and host reboot
checks. DNS took 72 seconds ($0.018943894); receipt ownership took 55 seconds
($0.007172334). Total provider-reported cost: $0.026116228, reported for both trials.

Sanitized evidence and runtime hashes are in
`validation/20261107-particle-pilot.json`; raw results and trajectories remain local.
This establishes a successful pilot, not scenario difficulty or comparative model
performance. These results do not change Core or approve trajectories for training.
