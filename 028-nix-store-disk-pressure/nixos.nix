{ lib, pkgs, ... }:

let
  appDir = ./app;
in
{
  imports = [ ../worker/base.nix ];

  virtualisation.diskSize = lib.mkForce 3072;
  virtualisation.writableStoreUseTmpfs = false;

  environment.systemPackages = with pkgs; [ curl nginx python3 sqlite nix ];

  users.users.billing-ledger = {
    isSystemUser = true;
    group = "billing-ledger";
  };
  users.groups.billing-ledger = { };

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision billing ledger state";
    wantedBy = [ "multi-user.target" ];
    before = [ "nix-cache-warmup.service" "billing-ledger.service" ];
    path = [ pkgs.coreutils pkgs.openssl pkgs.python3 ];
    serviceConfig.Type = "oneshot";
    script = ''
      install -d -m 0755 /etc/replaybook
      install -d -o billing-ledger -g billing-ledger -m 0750 \
        /var/lib/billing-ledger \
        /var/lib/billing-ledger/protected

      if [[ ! -e /etc/replaybook/cache-warmup.env ]]; then
        printf '%s\n' 'CACHE_WARMUP=enabled' > /etc/replaybook/cache-warmup.env
      fi
      if [[ ! -e /etc/replaybook/ledger.env ]]; then
        printf '%s\n' \
          'STATE_DIR=/var/lib/billing-ledger' \
          'MIN_FREE_BYTES=805306368' \
          > /etc/replaybook/ledger.env
      fi

      archive=/var/lib/billing-ledger/protected/accounting.archive
      if [[ ! -e "$archive" ]]; then
        dd if=/dev/zero of="$archive" bs=1M count=128 status=none
        sha256sum "$archive" | cut -d ' ' -f 1 > "$archive.sha256"
        chown billing-ledger:billing-ledger "$archive" "$archive.sha256"
        chmod 0400 "$archive" "$archive.sha256"
      fi

      if [[ ! -e /var/lib/billing-ledger/receipts.sqlite3 ]]; then
        ${pkgs.python3}/bin/python - <<'PY'
      import sqlite3

      path = "/var/lib/billing-ledger/receipts.sqlite3"
      with sqlite3.connect(path) as database:
          database.execute("CREATE TABLE receipts (receipt_id text PRIMARY KEY, created_at text NOT NULL)")
          database.executemany(
              "INSERT INTO receipts (receipt_id, created_at) VALUES (?, ?)",
              [
                  ("historical-20260815-a", "2026-08-15T19:12:04Z"),
                  ("historical-20260816-b", "2026-08-16T08:44:31Z"),
                  ("historical-20260817-c", "2026-08-17T06:20:55Z"),
              ],
          )
      PY
        chown billing-ledger:billing-ledger /var/lib/billing-ledger/receipts.sqlite3
        chmod 0600 /var/lib/billing-ledger/receipts.sqlite3
      fi
    '';
  };

  systemd.services.nix-cache-warmup = {
    description = "Refresh local Nix build cache";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" ];
    path = [ pkgs.coreutils pkgs.gawk pkgs.nix ];
    serviceConfig = {
      Type = "oneshot";
      EnvironmentFile = "/etc/replaybook/cache-warmup.env";
    };
    script = ''
      if [[ "''${CACHE_WARMUP:-enabled}" != enabled ]]; then
        exit 0
      fi

      scratch=/dev/shm/nix-cache-warmup
      install -d -m 0700 "$scratch"
      payload="$scratch/cache.bin"
      dd if=/dev/zero of="$payload" bs=1M count=512 status=none
      index=0
      while (( $(df --output=avail -BM / | tail -1 | tr -dc '0-9') > 700 )); do
        printf 'cache-generation=%08d\n' "$index" | \
          dd of="$payload" conv=notrunc status=none
        nix-store --add "$payload" >/dev/null
        index=$((index + 1))
      done
      rm -f "$payload"
      rmdir "$scratch"
      touch /run/nix-cache-warmup-complete
    '';
  };

  systemd.services.billing-ledger = {
    description = "Billing receipt ledger";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "billing-ledger";
      Group = "billing-ledger";
      EnvironmentFile = "/etc/replaybook/ledger.env";
      ExecStart = "${pkgs.python3}/bin/python ${appDir}/server.py";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
