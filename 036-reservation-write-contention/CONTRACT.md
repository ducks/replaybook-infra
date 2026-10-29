# Reservation write contention — incident contract

Symptom: concurrent reservations are accepted but available capacity no longer matches committed reservations.
Cause: a deployment enabled the compatibility write path, which reads capacity before its transaction and loses updates under concurrency.
Durable repair: restore atomic reservation transactions and reconcile capacity from preserved committed records.
State: exact accepted IDs, quantities, payloads, and original total capacity must remain intact.
Success: concurrent fresh requests preserve conservation of capacity, duplicate-ID retries are idempotent, and the invariant survives restart and reboot.
Negative controls: increasing total capacity, deleting reservations, merely fixing the counter, or merely enabling atomic writes without reconciliation fail.

Controller hooks and this document are never installed in the guest.
