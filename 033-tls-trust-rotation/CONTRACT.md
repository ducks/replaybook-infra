# Certificate maintenance and durable webhook delivery

Proposed scenario v1; Core candidate, not part of the existing frozen baseline.

- Symptom: the dispatcher accepts work and stays healthy, but delivery stalls
  after an internal receiver certificate rotation.
- Root cause: the dispatcher's private trust bundle still contains the retired
  CA. The receiver now presents a valid certificate from the current platform CA.
- Durable repair: deploy the current CA bundle to the dispatcher's configured
  trust path and restart it, preserving certificate and hostname verification.
- State: controller-generated delivery IDs and receipt records in independent
  dispatcher and receiver SQLite databases. Payloads derive from opaque IDs.
- Success: recover every initial delivery, preserve receiver receipts, and
  deliver fresh work during immediate, service-restart, and host-reboot phases.
- Topology: systemd dispatcher, receiver endpoints, and Nginx remain active.
- Security: the same transport code must reject both a retired-CA endpoint and
  a current-CA endpoint with a mismatched hostname. Trusting both CAs, disabling
  chain verification, or disabling hostname checks must fail verification.
- Negative controls: unchanged deployment, deleted backlog, disabled TLS checks,
  hostname-only bypass, and union trust store. Local integration tests exercise
  real TLS handshakes and controller phase assertions; VM evidence is recorded
  separately after the oracle lifecycle and inexpensive agent smoke test.

The endpoint group includes two internal diagnostic listeners with distinct
certificate identities. They do not receive user work. The receiver stores a
payload digest and rejects conflicting reuse of an ID. Controller checks read
independent receipts as well as dispatch completion, so clearing the queue or
returning success from the dispatch status alone is insufficient.

As with other root-agent scenarios, an agent can edit application code and
forge observations. This is an operational repair benchmark, not a tamper-proof
boundary against malicious root. The security checks test the active transport
behavior rather than accepting configuration text as evidence.

## Validation evidence

- Static scenario validation and `make check` passed on 2026-10-24.
- Five real-TLS integration tests cover backlog recovery, fresh work through
  every controller verification phase, deleted backlog, union trust stores,
  disabled certificate or hostname validation, unreachable diagnostic peers,
  and a read-only receipt observation boundary.
- The final fresh-VM oracle passed immediate, service-restart, and host-reboot
  checks. Local evidence: `replaybook/jobs/core-tls-oracle-20261024-02/result.json`.
- Replaybook `make lint` passed. Evidence files stay outside the scenario pack.
