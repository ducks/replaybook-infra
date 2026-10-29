# Replaybook Infra

Replaybook Infra evaluates whether an AI agent can durably repair a stateful
production system without losing existing work.

Agents run as root inside fresh NixOS virtual machines containing real systemd
services. The controller owns the incident lifecycle and verifier. A repair
only passes when the user-facing behavior recovers, required state is
preserved, affected services restart successfully, and the host remains
healthy after reboot.

This repository contains the public benchmark scenario pack. The
[Replaybook](https://github.com/ducks/replaybook) repository contains the
runner, agent adapter contract, result schema, and benchmark publisher.

## Current status

Replaybook Infra Core `2026.10.24.2` is the current comparison suite. The wider
scenario library remains a preview benchmark. Pack `20261024.1.1` contains twenty
public incident scenarios and one real-application deployment scenario:

| Scenario | Version | Incident |
|---|---:|---|
| `001-nginx-502-host` | 1 | Nginx proxies to the wrong backend port |
| `013-sidekiq-wrong-redis` | 3 | Web and Sidekiq use different Redis databases; preserve pending confirmations |
| `014-missing-rails-migration` | 2 | A deployed Rails migration was not applied |
| `015-sidekiq-poison-pill` | 1 | A poison payload blocks valid queued work |
| `016-rails-pool-exhaustion` | 1 | Puma concurrency exceeds the Active Record pool |
| `017-partial-rails-rollout` | 1 | One Sidekiq worker remains pinned to the previous release |
| `018-node-event-loop-blocking` | 1 | Synchronous subprocess work serializes concurrent Node requests |
| `019-rust-fd-leak` | 1 | A Rust service retains one file descriptor per request |
| `020-python-gunicorn-saturation` | 1 | Gunicorn kills undersized workers during concurrent exports |
| `021-discourse-shared-uploads` | 1 | A Discourse deploy stores uploads inside the active release instead of shared storage |
| `022-discourse-multisite-migration` | 1 | One Discourse tenant missed a deployed database migration |
| `023-auth-secret-rollout` | 1 | A rolling deployment split active sessions across signing secrets |
| `024-discourse-interrupted-deploy` | 1 | An interrupted Discourse deploy leaves the schema incomplete and one web instance on the previous release |
| `025-discourse-bootstrap` | 1 | A fresh host must become a durable, production-style Discourse Docker deployment |
| `026-discourse-plugin-boot-loop` | 1 | An installed Discourse plugin is incompatible with the deployed core API and crashes web and Sidekiq |
| `027-partial-service-rollout` | 1 | A load-balanced order API mixes incompatible application generations before its database migration completes |
| `028-nix-store-disk-pressure` | 1 | An unbounded Nix cache refresh exhausts disk and forces a stateful ledger into read-only protection |
| `029-visual-topology-drift` | 1 | A reservation service has edge routing and queue-consumer drift from its authoritative topology diagram |
| `030-visual-metrics-regression` | 1 | A report renderer's cache and memory growth must be diagnosed from an operational dashboard |
| `031-visual-deployment-timeline` | 1 | A checkout fleet must be rolled forward after a deployment timeline shows an irreversible schema migration preceded an automatic rollback |
| `033-tls-trust-rotation` | 2 | Recover queued HTTPS deliveries after CA rotation while rejecting invalid peers |

Four executable tiers support different evaluation budgets:

| Tier | Manifest | Trials per model | Intended use |
|---|---|---:|---|
| Smoke | `benchmark-smoke.toml` | 3 | Qualify a new model or harness before spending on a wider run |
| **Core 2026.10.24.2** | `benchmark-core.toml` | 33 | Canonical model and harness comparison across representative stateful repairs |
| Full | `benchmark.toml` | 60 | Produce publication-grade evidence across all stable incident scenarios |
| Frontier | `benchmark-real.toml` | 1 | Exercise the resource-heavy real Discourse bootstrap with a 30-minute deadline |

The separately versioned `benchmark-visual.toml` manifest runs the three visual
incident scenarios three times each. It provides one consistent comparison
set for image-capable models without mixing text-only incidents into the
denominator.

Smoke deliberately combines the basic Nginx incident with interrupted
deployment and Nix disk-pressure scenarios. Core spans proxying, Redis and
queue state, rolling deployment, Rust resource leakage, shared uploads, an
interrupted Discourse deployment, and host disk recovery. Full contains all
twenty 15-minute incident scenarios, including topology, operational metrics,
and deployment-timeline incidents supplied as image artifacts. Frontier runs a real pinned Discourse
Docker build rather than the synthetic Discourse-shaped services used by the
incident suite.

[`CORE.md`](CORE.md) defines the frozen Core `2026.10.24.2` scenario set, execution
dimensions, official comparison lane, and versioning policy. Adding scenarios
to the wider pack does not change this Core revision or invalidate its results.

Every manifest declares its tier explicitly. Replaybook host harness v23
records that value in matrix summaries, submission bundles, public APIs, and
release pages, and refuses to aggregate results across tiers. The tier-aware
scenario-pack revision is `20261024.1.1`. The smoke
and frontier selections remain unchanged; Core adds the three scenarios described below.

These scenarios are enough to develop and compare agent harnesses. They are
not yet a broad infrastructure leaderboard. See [BENCHMARK.md](BENCHMARK.md)
for the scoring contract, compatibility requirements, and current limitations.

## Requirements

- Linux with Nix and QEMU/KVM
- A checkout of [Replaybook](https://github.com/ducks/replaybook)
- Model credentials required by the selected agent harness

By default, the commands below expect sibling checkouts:

```text
~/dev/replaybook
~/dev/replaybook-infra
```

## Validate the pack

```sh
make validate
```

Validate every executable benchmark tier without starting a VM:

```sh
make check
```

Validate one tier directly:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark.toml \
  --check
```

## Run the reference repair

Every scenario must pass with its controller-only oracle before model results
are meaningful:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark.toml \
  --oracle
```

Run the real Discourse deployment oracle separately:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-real.toml \
  --oracle
```

## Run an agent

```sh
../replaybook/integrations/host/run-host-native.sh \
  --scenario-pack . \
  --scenario 014-missing-rails-migration \
  --model deepseek/deepseek-v4-flash-0731
```

## Run the complete public matrix

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark.toml \
  --models deepseek/deepseek-v4-flash-0731 \
  --concurrency 2
```

The manifest fixes the pack, scenarios, scenario versions, attempt count,
timeout, verification policy, and required host harness. A submission still
chooses its model, reasoning effort, agent adapter, credentials, concurrency,
and output directory.

Replaybook records the manifest identity and SHA-256 hash in every matrix. Its
benchmark publisher refuses to combine matrices produced from incompatible
manifest, pack, scenario, harness, timeout, or agent configurations.

## Choose a benchmark tier

Start a new model or harness with smoke:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-smoke.toml \
  --models openrouter/model-id \
  --reasoning-efforts high \
  --concurrency 2
```

Move promising configurations to core, then full:

```sh
python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark-core.toml \
  --models openrouter/model-id \
  --reasoning-efforts high \
  --concurrency 2

python ../replaybook/integrations/host/run_host_matrix.py \
  --benchmark ./benchmark.toml \
  --models openrouter/model-id \
  --reasoning-efforts high \
  --concurrency 2
```

Tier results remain separate compatibility cohorts because scenario selection,
attempt count, timeout, and manifest hash are part of the benchmark identity.
Passing smoke does not count as a partial full-suite score. It is a controlled
qualification step that limits spend before running broader evidence.

## Repository boundary

- Replaybook owns execution, isolation, adapters, normalized results, and
  publishing.
- Replaybook Infra owns the canonical incident definitions and benchmark
  contract.
- Private or organization-specific scenario packs can use Replaybook without
  depending on this benchmark.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing a scenario. Scenario
correctness matters more than scenario count. Every contribution needs an
oracle, broken-state preflight, durable verifier, leak review, and explicit
failure categories.

## License

MIT

Core `2026.10.24.2` adds authentication secret rotation (023), database pool
exhaustion under concurrent load (016), and TLS trust rotation with durable
queued delivery (033 v2). Core now selects eleven scenarios for 33 trials per
model. The two existing incidents remain in Full; the new TLS incident is
included in both Core and Full. Existing frozen operator cohorts stay unchanged.

## Experimental Core Hard

[Core Hard](CORE-HARD.md) adds three separate candidate incidents covering a
partial dependency rollout, pending notification recovery, and concurrent
reservation accounting. Its [manifest](benchmark-core-hard.toml) is independent
of frozen Core. Run `make core-hard-check` and `make core-hard-oracle` to validate
it before model comparisons; the existing Core suite is unchanged.
