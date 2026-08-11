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

Replaybook Infra is a preview benchmark. Release `20260811.1.0` contains eleven
public development scenarios:

| Scenario | Version | Incident |
|---|---:|---|
| `001-nginx-502-host` | 1 | Nginx proxies to the wrong backend port |
| `013-sidekiq-wrong-redis` | 2 | Web and Sidekiq use different Redis databases |
| `014-missing-rails-migration` | 2 | A deployed Rails migration was not applied |
| `015-sidekiq-poison-pill` | 1 | A poison payload blocks valid queued work |
| `016-rails-pool-exhaustion` | 1 | Puma concurrency exceeds the Active Record pool |
| `017-partial-rails-rollout` | 1 | One Sidekiq worker remains pinned to the previous release |
| `018-node-event-loop-blocking` | 1 | Synchronous subprocess work serializes concurrent Node requests |
| `019-rust-fd-leak` | 1 | A Rust service retains one file descriptor per request |
| `020-python-gunicorn-saturation` | 1 | Gunicorn kills undersized workers during concurrent exports |
| `021-discourse-shared-uploads` | 1 | A Discourse deploy stores uploads inside the active release instead of shared storage |
| `022-discourse-multisite-migration` | 1 | One Discourse tenant missed a deployed database migration |

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

Validate the complete executable benchmark contract without starting a VM:

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
