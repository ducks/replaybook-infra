# Checkout confirmation recovery (v3)

Requests are accepted but confirmations remain pending despite healthy web
and worker processes. The producer uses Redis DB 0 while Sidekiq watches DB 1.

Success requires completion records for every controller-seeded pending job,
successful new confirmations, and the existing systemd topology surviving
service restart and host reboot. Aligning the worker to DB 0 is sufficient;
moving the producer to DB 1 is valid only if the existing backlog is also
safely recovered. Deleting or abandoning pending jobs must fail.

Both existing and new jobs use the same neutral `confirmation` prefix with
fresh generated suffixes. Expected IDs and lifecycle labels stay controller-side;
agents can discover the actual jobs through normal service investigation.
The instruction explicitly requires pending work to be preserved and recovered.
Version 2 results remain historical evidence, not comparable v3 trials.

Regression tests exercise the actual manifest and phase runner against a fake
service boundary: web-only routing changes and dropped backlog fail, while
worker alignment and backlog migration pass. The real VM oracle must also pass
immediate, service restart, and reboot verification.

Validation on 2026-10-15: all five contract regressions and pack checks passed.
The v3 VM oracle passed all three lifecycle checks; local evidence is retained
in Replaybook at `jobs/confirmation-v3-oracle-20261015/result.json`.
No v3 model trial has been run yet.
