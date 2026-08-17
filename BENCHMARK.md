# Replaybook Infra benchmark contract

## Capability under evaluation

Replaybook Infra measures whether an agent can investigate and durably repair
a running, stateful Linux system.

Traditional coding benchmarks ask an agent to produce a correct artifact.
Replaybook Infra asks whether the deployed system is healthy after the agent
leaves.

## What a passing repair means

The controller, not the agent harness, defines success. Depending on the
scenario, the verifier checks that:

1. The user-facing behavior has recovered.
2. Pre-existing jobs, records, or requests were preserved and completed.
3. Forbidden shortcuts were not used.
4. The expected service topology remains intact.
5. The repair survives affected service restarts.
6. The repair survives a complete host reboot.

A passing health check by itself is not evidence of a durable repair.
Temporary processes, in-memory state, and ad hoc shell workarounds disappear
during verification.

## Evaluation boundary

Replaybook builds and controls the disposable NixOS host. It owns the incident
instruction, timeout, lifecycle, oracle, restart and reboot sequence, and
verifier. The oracle and verifier do not enter the model VM.

The selected agent adapter owns only agent invocation and normalized result
reporting. An adapter may change how an agent runs. It cannot redefine what
counts as success.

## Trial outcomes

- **Passed:** the agent reached the verifier and produced a durable repair.
- **Failed:** the agent reached evaluation but violated one or more verifier
  requirements.
- **Unavailable:** the provider or harness failed before a repair could be
  evaluated. Unavailable trials remain visible but do not count against model
  repair rate.

## Primary metrics

- Durable repair rate
- Median repair duration
- Price per durable repair
- Failure category distribution
- Input and output token usage
- Model-round and tool-call timing when the harness reports it

Failed evaluated attempts remain in total spend. Therefore:

```text
price per durable repair = evaluated trial spend / verified repairs
```

## Comparable results

Results belong in one controlled comparison only when they share:

- Scenario pack and scenario versions
- Replaybook host harness version
- Execution snapshot hashes
- Agent harness, tools, prompt, and permissions
- Timeout and attempt count
- Cost and failure provenance rules

Reasoning effort is recorded as a distinct model configuration. Results from
different benchmark or verifier versions remain in versioned history rather
than being silently mixed.

## Scenario requirements

Every scenario must contain:

- `scenario.toml`, including explicit failure categories
- `nixos.nix`, defining the incident host
- `instruction.md`, containing only information available to the participant
- `oracle.sh`, implementing the controller-only reference repair
- A preflight that proves the intended failure exists
- A verifier that checks durable recovery through the public behavior

Stateful scenarios must identify controller-owned state before the agent
starts and verify those exact opaque identifiers afterward. Counting an empty
queue is not equivalent to recovering existing work.

## Leakage and safety

Replaybook checks that the oracle and verifier are absent from the agent VM.
Provider credentials remain outside the VM when the built-in Claux adapter is
used. The controller records execution provenance and sanitized transcripts so
unexpected behavior can be audited.

## Versioning

The pack uses date versions:

```text
YYYYMMDD.MAJOR.PATCH
```

- Increment `PATCH` for metadata or verifier fixes that preserve the intended
  task.
- Increment `MAJOR` when scenario behavior, scoring, or the comparable result
  population changes.
- Use a new date for a new published benchmark revision.

Individual scenarios also have integer versions. Any change that can alter an
agent's score requires a scenario version bump.

## Current limitations

Release `20260817.0.0` is a public development suite with fifteen incident
scenarios and three attempts per scenario in published matrices. It does not
yet provide a private held-out set, human baseline, or enough operational
coverage for a universal infrastructure-agent ranking.
