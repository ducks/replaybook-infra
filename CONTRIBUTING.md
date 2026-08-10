# Contributing

Replaybook Infra treats benchmark correctness as part of the product. A task
that leaks its answer, loses state, or accepts a temporary workaround is worse
than no task at all.

## Proposing a scenario

Open an issue describing:

- The user-visible symptom
- The hidden root cause
- Why the incident requires operational reasoning
- State that must survive the repair
- Shortcuts the verifier must reject
- The expected durable repair

Do not use private employer code, credentials, customer data, or proprietary
incident details. Reduce real incidents to original, synthetic reproductions.

## Implementing a scenario

1. Create a feature branch.
2. Use Replaybook's `replaybook-build-scenario` skill or an existing scenario
   as the starting structure.
3. Add the NixOS topology, participant instruction, declarative lifecycle, and
   reference repair.
4. Run the oracle through immediate, restart, and reboot verification.
5. Review the VM filesystem and participant instruction for answer leaks.
6. Run at least one inexpensive agent smoke test.
7. Document any verifier or scenario-version change.

## Required review questions

- Does preflight prove the intended failure exists?
- Does the verifier test user-facing behavior rather than implementation text?
- Can an agent pass by deleting queued work or recreating state?
- Does the repair survive restart and reboot?
- Can an agent discover the oracle, verifier, or expected answer?
- Are failure categories specific enough to explain the result?
- Is the scenario deterministic enough for repeated trials?

## Version changes

Bump the individual scenario version whenever a change can affect outcomes.
Bump the pack date version for every published revision. Historical benchmark
results must retain the exact pack and scenario versions that produced them.
