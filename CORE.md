# Replaybook Infra Core 2026.10.24

Replaybook Infra Core `2026.10.24` proposes the next public comparison for infrastructure
agents. It answers a narrow question: can an agent investigate and durably
repair representative stateful Linux incidents under one repeatable contract?

The executable contract is [`benchmark-core.toml`](benchmark-core.toml):

- Benchmark ID: `replaybook-infra-core`
- Version: `2026.10.24`
- Tier: `core`
- Nine scenarios
- Three attempts per scenario
- 900-second agent deadline
- Replaybook host harness v23
- Immediate, service-restart, and host-reboot verification
- Preservation of controller-owned state

Each model configuration therefore produces 27 evaluated trials when every
provider invocation is available.

## Frozen scenario set

| Scenario | Version | Coverage |
|---|---:|---|
| `001-nginx-502-host` | 1 | Reverse proxy diagnosis and systemd deployment |
| `013-sidekiq-wrong-redis` | 3 | Cross-service configuration and existing queue state |
| `015-sidekiq-poison-pill` | 1 | Queue recovery without discarding valid work |
| `017-partial-rails-rollout` | 1 | Mixed-release diagnosis and coordinated rollout |
| `019-rust-fd-leak` | 1 | Native-service resource exhaustion |
| `021-discourse-shared-uploads` | 1 | Stateful release layout and historical uploads |
| `024-discourse-interrupted-deploy` | 1 | Interrupted schema and application convergence |
| `028-nix-store-disk-pressure` | 1 | Host storage pressure and durable Nix remediation |
| `023-auth-secret-rollout` | 1 | Signing-secret rotation with active-session preservation and revoked-session rejection |

These scenarios span proxying, queues, deployment convergence, native resource
management, application state, and host operations. New scenarios mature in
the smoke, full, visual, or frontier suites without changing this Core revision.

## Comparison policy

A public Core comparison must name the model, reasoning configuration,
agent harness and version, provider boundary, and Replaybook execution
identity. Results from different agent harnesses or reasoning configurations
remain separate lanes even when they use the same Core v1 scenarios.

Provider or harness failures before meaningful inference are reported as
unavailable. Evaluated failures remain in the repair-rate denominator and in
total spend. A serious model result uses all three attempts; one-off smoke runs
do not enter the canonical comparison.

The primary ranking metric is durable repair rate. Median duration, total
tokens, total cost, cost per durable repair, and failure categories provide the
operational context needed to interpret that rate.

## Stability policy

The current Core revision omits the surrounding scenario-pack version from its manifest. The
pack ID, exact scenario versions, and content hashes for every selected
scenario remain pinned by Replaybook. This lets the public scenario library
grow without resetting Core coverage.

Core revisions use `YYYY.MM.DD`. A second contract release on the same day adds
a numeric suffix such as `2026.10.24.1`, followed by `.2` if needed. Any change
to the selected scenarios, their scoring content, attempt count, deadline,
required host harness, or verification policy creates a new dated revision.
Earlier Core artifacts and results remain available as versioned history.

## Run Core

From a sibling Replaybook checkout:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-core.toml \
  --models provider/model-id \
  --reasoning-efforts high \
  --concurrency 2
```

Validate the contract without launching virtual machines:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-core.toml \
  --check
```

## Proposed Core revision

This branch adds `023-auth-secret-rollout` without changing its scenario v1 scoring.
The previous eight-scenario Core revision and frozen operator cohorts remain
historical and unchanged. The extra scenario adds three trials per model.
This proposal is independent of the other Core candidate branches; combine
selections and assign the final revision before publishing a joint suite.

Validation: `make validate`, `make core-check`, and the unchanged scenario v1
oracle passed on 2026-10-24, including immediate, service-restart, and
host-reboot checks. Local evidence: `replaybook/jobs/core-auth-oracle-20261024/`.

This integration also adds `016-rails-pool-exhaustion`; its unchanged v1
oracle passed all three lifecycle phases in `core-pool-oracle-20261024`.
