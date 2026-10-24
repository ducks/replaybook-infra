# Certificate maintenance and durable webhook delivery

Proposed scenario v2; Core candidate, not part of the existing frozen baseline.

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

## Initial v1 validation evidence

- Static scenario validation and `make check` passed on 2026-10-24.
- Five real-TLS integration tests cover backlog recovery, fresh work through
  every controller verification phase, deleted backlog, union trust stores,
  disabled certificate or hostname validation, unreachable diagnostic peers,
  and a read-only receipt observation boundary.
- The final fresh-VM oracle passed immediate, service-restart, and host-reboot
  checks. Local evidence: `replaybook/jobs/core-tls-oracle-20261024-02/result.json`.
- Replaybook `make lint` passed. Evidence files stay outside the scenario pack.

## Version 2: preserve transport identities

The v1 model smoke passed the HTTP verifier by swapping the current and retired
endpoint certificates and continuing to trust the retired CA. This violates the
retired-chain contract. Its result is retained as evidence of a verifier gap,
not accepted as validation of v2.

V2 records the exact live peer certificate fingerprints and both CA-file hashes
in controller-only preflight state. Every verification phase independently
observes those identities over SSH/TLS before running the HTTP assertions.
Swapping endpoints, replacing the diagnostic certificates, or relabeling the
CA files now fails. The reference repair continues to update only client trust.
The legacy lifecycle hook wraps the typed HTTP plan because the typed runner
cannot retain or compare independent certificate observations. The HTTP plan
and probe stay controller-side. No harness-library change is required.

## V2 validation evidence

- `make check` passed with eight tests, including a real TLS reproduction of
  certificate swapping that passes the v1 HTTP assertions but fails the v2
  controller. A separate test rejects relabeled CA files and verifies that
  execution snapshots load their own frozen phase runner.
- Fresh-VM oracle: `replaybook/jobs/core-tls-v2-oracle-20261024/result.json`
  reports reward 1 and immediate, service-restart, and host-reboot success.
- Only `app/service.py` and the provisioning closure enter the guest. The
  controller hook, phase plan, certificate observation probe, and expected
  fingerprints remain outside the agent-visible filesystem. The guest-facing
  application/provisioning source is unchanged from the v1 leak-audited build.

- V2 DeepSeek V4.1 Flash smoke (OpenRouter, Claux, high reasoning): reward 1,
  84-second agent duration, $0.013918048 provider-reported cost. Evidence:
  `replaybook/jobs/core-tls-v2-smoke-20261024/summary.json`. Immediate,
  service-restart, and host-reboot checks all passed. Observable tool review
  confirmed a client CA-bundle update, preserved endpoint certificates, and
  recovered queued deliveries. No controller file markers appeared in tool
  outputs. This single smoke establishes usability, not model reliability.
