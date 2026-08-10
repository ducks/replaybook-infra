# Repository instructions

- Work on a feature branch. Do not commit scenario changes directly to `main`.
- Replaybook is expected at `../replaybook` unless `REPLAYBOOK_DIR` is set.
- Never place provider credentials, proprietary incidents, or customer data in
  this repository.
- Do not expose `oracle.sh`, verifier behavior, or expected repairs through an
  agent-visible file.
- Any change that can affect scoring requires an individual scenario version
  bump and a pack version bump.
- Run `make validate` and an oracle evaluation for every changed scenario.
- Preserve opaque controller-owned state in stateful scenarios. An empty queue
  is not proof that existing work was recovered.
- Keep public benchmark claims tied to tracked result artifacts and compatible
  benchmark versions.
