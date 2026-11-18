#!/usr/bin/env bash
set -euo pipefail
repo=/opt/ledgerlens/repo
mkdir -p "$repo/deploy"
cat >"$repo/deploy/install.sh" <<'INSTALL'
#!/usr/bin/env bash
set -euo pipefail
repo=/opt/ledgerlens/repo
release=/opt/ledgerlens/releases/0.4.0
id ledgerlens >/dev/null 2>&1 || useradd --system --home /var/lib/ledgerlens --user-group ledgerlens
install -d -m 0755 "$release" /etc/ledgerlens /var/lib/ledgerlens /var/lib/ledgerlens/uploads /etc/systemd/system.control/multi-user.target.wants
install -m 0644 "$repo/ledgerlens.py" "$repo/README.md" "$release/"
if [[ ! -f /var/lib/ledgerlens/ledger.sqlite3 ]]; then
 cp /srv/ledgerlens-handoff/ledger.sqlite3 /var/lib/ledgerlens/ledger.sqlite3
 cp /srv/ledgerlens-handoff/uploads/* /var/lib/ledgerlens/uploads/
fi
if [[ ! -f /etc/ledgerlens/token ]]; then install -m 0640 /srv/ledgerlens-handoff/token /etc/ledgerlens/token; fi
chown -R ledgerlens:ledgerlens /var/lib/ledgerlens
chown root:ledgerlens /etc/ledgerlens/token
cat >/etc/ledgerlens/runtime.env <<'ENV'
LEDGER_DATABASE=/var/lib/ledgerlens/ledger.sqlite3
LEDGER_UPLOADS=/var/lib/ledgerlens/uploads
LEDGER_TOKEN_FILE=/etc/ledgerlens/token
LEDGER_PUBLIC_URL=http://ledgerlens.replaybook.test/api
ENV
for kind in api worker; do
 command=worker
 [[ "$kind" == api ]] && command='serve --host 127.0.0.1 --port 8080'
 cat >"/etc/systemd/system.control/ledgerlens-$kind.service" <<UNIT
[Unit]
Description=LedgerLens $kind
After=network.target
[Service]
User=ledgerlens
Group=ledgerlens
WorkingDirectory=$release
EnvironmentFile=/etc/ledgerlens/runtime.env
ExecStartPre=/run/current-system/sw/bin/python $release/ledgerlens.py migrate
ExecStart=/run/current-system/sw/bin/python $release/ledgerlens.py $command
Restart=always
RestartSec=1
[Install]
WantedBy=multi-user.target
UNIT
done
cat >/etc/ledgerlens-edge/routes.conf <<'ROUTES'
location /api/ { proxy_pass http://127.0.0.1:8080/; }
location / { return 404; }
ROUTES
# A source-only artifact: no live state or secrets.
tar -czf "$repo/deploy/ledgerlens-0.4.0.tar.gz" -C "$release" ledgerlens.py README.md
systemctl daemon-reload
ln -sfn ../ledgerlens-api.service /etc/systemd/system.control/multi-user.target.wants/ledgerlens-api.service
ln -sfn ../ledgerlens-worker.service /etc/systemd/system.control/multi-user.target.wants/ledgerlens-worker.service
systemctl restart ledgerlens-api.service ledgerlens-worker.service
systemctl restart nginx
cat >/etc/ledgerlens/deployment.json <<'JSON'
{"api_unit":"ledgerlens-api.service","worker_unit":"ledgerlens-worker.service","database":"/var/lib/ledgerlens/ledger.sqlite3","uploads":"/var/lib/ledgerlens/uploads","token_file":"/etc/ledgerlens/token","release":"/opt/ledgerlens/releases/0.4.0","install_script":"/opt/ledgerlens/repo/deploy/install.sh","artifact":"/opt/ledgerlens/repo/deploy/ledgerlens-0.4.0.tar.gz","operator_doc":"/opt/ledgerlens/repo/deploy/OPERATIONS.md"}
JSON
INSTALL
chmod 755 "$repo/deploy/install.sh"
cat >"$repo/deploy/OPERATIONS.md" <<'DOC'
# LedgerLens operations
Install with `sudo ./deploy/install.sh`; rerunning preserves the live database,
uploads and token. Check `systemctl status ledgerlens-api ledgerlens-worker` and
`journalctl -u ledgerlens-api -u ledgerlens-worker`. Readiness is `/api/ready`.
For backup, stop both units, copy `/var/lib/ledgerlens` and `/etc/ledgerlens`, then
start them. For restore, stop both, restore all database/upload/token files as a
set, restore ownership and restart. Keep the token private and outside archives.
The release artifact is source-only. This prototype's additive migration is
forward compatible; a future incompatible migration requires its own recovery
plan. Do not blindly roll old application code onto a newer schema. Restore a
coherent tested backup when rollback cannot preserve acknowledged writes, and
explicitly account for any writes made after that backup.
DOC
"$repo/deploy/install.sh"
