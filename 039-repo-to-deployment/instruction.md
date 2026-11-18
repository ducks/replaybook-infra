# Deploy an unfamiliar application from its repository

A small team handed over the LedgerLens source repository at
`/opt/ledgerlens/repo`. Read its README, inspect its code and tests, and turn it
into a durable production-style deployment on this NixOS host. No deployment
configuration is provided. Keep application behavior and source unchanged.

Serve its API at `http://ledgerlens.replaybook.test/api` through the existing
Nginx edge on port 80. The edge includes `/etc/ledgerlens-edge/routes.conf`;
initially it returns 503. Python, SQLite, Nginx, Git and systemd are installed.
NixOS owns the read-only `/etc/systemd/system` tree. Additional persistent
units and target wants can be placed in `/etc/systemd/system.control/`, or use
another valid persistent NixOS/systemd deployment approach.
No public DNS, TLS certificate, package registry or hosted infrastructure is
needed. Use native systemd services; do not introduce Docker/Kubernetes or
replace the host. You may use Nix configuration if helpful, but a NixOS rebuild
is not required.

`/srv/ledgerlens-handoff` contains the previous instance's schema-1 database,
uploads and production token. Preserve every record and original upload,
including completed history, unfinished work and invalid imports. Read the
repository to determine the migration, processes and environment required.
Production state and credentials must live outside the checkout, release,
`/tmp`, `/run` and `/root`. The API and worker must run as unprivileged users
under independent, enabled systemd units and recover from worker crashes.
The runtime source must be a release outside the development checkout.

Produce a release `.tar.gz` containing the original application source and
supporting files, without live credentials or databases. Write an executable,
idempotent installer and an operator runbook covering installation, service
management, logs, backup/restore and release recovery limitations. The installer
will be rerun after the system has accepted new work; it must preserve that work.
The verifier checks runtime behavior, not just the existence of these files.

Write `/etc/ledgerlens/deployment.json` with these string fields so another
operator can locate the deployment (paths must be absolute):

- `api_unit`, `worker_unit`: the actual `.service` unit names
- `database`, `uploads`, `token_file`: production state/credential paths
- `release`: directory containing the deployed `ledgerlens.py`
- `install_script`: executable installer path
- `artifact`: the release `.tar.gz` path
- `operator_doc`: runbook path

Use any sensible names and directory layout satisfying those requirements.
The development `.dev` defaults are not production paths. Returned application
links must use the public `/api` URL, authentication must reject incorrect
tokens, and processing must preserve idempotency and original upload bytes.

Success includes actual CSV submission, asynchronous processing, failed-input
classification, download, recovery of historical work, installer rerun,
service restarts, worker loss and a host reboot. Brief deployment interruption
is allowed; acknowledged data loss is not. Do not modify the benchmark, forge
API responses, discard inconvenient records, change the application source or
run unmanaged background processes. Do not reboot the host yourself.
