# LedgerLens

LedgerLens 0.4.0 accepts accounting CSV files, stores their original bytes and
processes them asynchronously into category totals. There are two processes:
the HTTP API and a worker sharing a SQLite database and upload directory.
Python 3.12+ is the only runtime dependency; no pip packages are needed.

## Development

```sh
mkdir -p .dev/uploads
python -c 'import secrets; print(secrets.token_hex(24))' > .dev/token
export LEDGER_DATABASE="$PWD/.dev/ledger.sqlite3"
export LEDGER_UPLOADS="$PWD/.dev/uploads"
export LEDGER_TOKEN_FILE="$PWD/.dev/token"
export LEDGER_PUBLIC_URL=http://localhost:8080
python ledgerlens.py migrate
python ledgerlens.py worker  # keep running in another terminal
python ledgerlens.py serve --host 127.0.0.1 --port 8080
make test
```

`POST /imports/<id>` takes raw UTF-8 CSV (`category,amount` columns) and returns
202 with a status URL. Use `Authorization: Bearer <token>` for application
routes. `GET /imports/<id>` returns queued/running/done/failed and its result;
`GET /imports/<id>/source` returns the exact original upload. Retrying the same
ID/body is idempotent; a different body on an existing ID is a conflict (409).
The worker marks malformed CSV failed instead of discarding it.

`GET /health` is process liveness only. `/ready` additionally requires a recent
worker heartbeat. `/meta` returns the version and API process ID. The public URL
controls links returned to clients; set it correctly behind a reverse proxy.

## State and migration

A handoff from an earlier instance can contain a schema-1 database and uploads.
Run `migrate` with the production environment before starting either process;
it upgrades in place to schema 2 without deleting history or queued work.
Migration is idempotent. Never run the development initialization or replace a
production database during installation. The API and worker must use the same
persistent state, even across releases. A worker killed while processing work
leaves a short lease; a restarted worker can recover it.

The `.dev` paths are convenient for a workstation, not a production deployment.
Use a dedicated unprivileged runtime user, durable paths outside the checkout
and release, and a private token file. Don't put live secrets or data into
release archives. The runtime code does not load `.env` files automatically.

No deployment manifests are supplied. Infrastructure depends on the operator's
host. Keep the source unchanged; add packaging, service definitions and
operational tooling alongside it. Source code, development tests and README
are the application contract, not proof that a deployment is operational.
