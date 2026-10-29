# Notification outbox rollout — incident contract

Symptom: notification submissions are accepted but never produce delivery receipts after a release.
Cause: the worker still uses the previous payload decoder while the API writes the current format.
Durable repair: converge worker configuration to the deployed API format without clearing the outbox.
State: exact pending notification bodies plus historical receipts must survive. Each accepted ID must have exactly one matching receipt.
Success: all pre-existing pending work and future notifications are delivered unchanged through restart and reboot; historical records remain intact.
Negative controls: emptying the queue, marking rows sent without receipts, duplicate deliveries, replacing payloads, and returning synthetic HTTP success fail the independent database probe.

Controller hooks and this document are never installed in the guest.
