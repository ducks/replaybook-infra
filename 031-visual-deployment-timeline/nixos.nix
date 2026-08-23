{ pkgs, ... }:

let
  appDir = ./app;
  releaseRoot = "/var/lib/checkout/releases";
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ curl nginx python3 sqlite ];

  users.users.checkout = {
    isSystemUser = true;
    group = "checkout";
  };
  users.groups.checkout = { };

  services.nginx = {
    enable = true;
    appendHttpConfig = ''
      upstream checkout_web {
        server 127.0.0.1:3301;
        server 127.0.0.1:3302;
      }
    '';
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://checkout_web";
      locations."/instances/blue/".proxyPass = "http://127.0.0.1:3301/";
      locations."/instances/green/".proxyPass = "http://127.0.0.1:3302/";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision the checkout deployment timeline incident";
    wantedBy = [ "multi-user.target" ];
    before = [
      "checkout-web-blue.service"
      "checkout-web-green.service"
      "checkout-worker.service"
    ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.python3 ];
    script = ''
      install -d -m 0755 /etc/checkout ${releaseRoot}/41 ${releaseRoot}/42
      install -d -o checkout -g checkout -m 0750 /var/lib/checkout/state

      if [[ ! -e /var/lib/checkout/runtime.py ]]; then
        cp ${appDir}/runtime.py /var/lib/checkout/runtime.py
        cp -R ${appDir}/releases/41/. ${releaseRoot}/41/
        cp -R ${appDir}/releases/42/. ${releaseRoot}/42/
        chmod 0755 /var/lib/checkout/runtime.py ${releaseRoot}/{41,42}/*.py
      fi
      ln -sfn ${releaseRoot}/42 /var/lib/checkout/current

      if [[ ! -e /etc/checkout/blue.env ]]; then
        printf '%s\n' \
          'PORT=3301' \
          'DB_PATH=/var/lib/checkout/state/checkout.db' \
          'RELEASE_DIR=${releaseRoot}/41' \
          > /etc/checkout/blue.env
      fi
      if [[ ! -e /etc/checkout/green.env ]]; then
        printf '%s\n' \
          'PORT=3302' \
          'DB_PATH=/var/lib/checkout/state/checkout.db' \
          'RELEASE_DIR=${releaseRoot}/41' \
          > /etc/checkout/green.env
      fi
      if [[ ! -e /etc/checkout/worker.env ]]; then
        printf '%s\n' \
          'DB_PATH=/var/lib/checkout/state/checkout.db' \
          'RELEASE_DIR=${releaseRoot}/41' \
          > /etc/checkout/worker.env
      fi

      if [[ ! -e /var/lib/checkout/state/checkout.db ]]; then
        ${pkgs.python3}/bin/python - <<'PY'
      import sqlite3

      path = "/var/lib/checkout/state/checkout.db"
      database = sqlite3.connect(path)
      database.executescript("""
      PRAGMA journal_mode=WAL;
      CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        completed_release TEXT
      );
      CREATE TABLE receipts (
        receipt_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
      );
      """)
      database.execute("INSERT INTO metadata VALUES ('schema_version', '42')")
      database.execute(
          "INSERT INTO orders VALUES (?, 'pending', NULL)",
          ("order-accepted-before-rollback",),
      )
      database.execute(
          "INSERT INTO receipts VALUES (?, ?)",
          ("receipt-before-rollback", "paid:8421"),
      )
      database.commit()
      database.close()
      PY
        chown checkout:checkout /var/lib/checkout/state/checkout.db*
      fi
    '';
  };

  systemd.services.checkout-web-blue = {
    description = "Checkout web instance blue";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "checkout";
      Group = "checkout";
      EnvironmentFile = "/etc/checkout/blue.env";
      Environment = "PYTHONPATH=/var/lib/checkout";
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${pkgs.python3}/bin/python \"$RELEASE_DIR/server.py\"'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.checkout-web-green = {
    description = "Checkout web instance green";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "checkout";
      Group = "checkout";
      EnvironmentFile = "/etc/checkout/green.env";
      Environment = "PYTHONPATH=/var/lib/checkout";
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${pkgs.python3}/bin/python \"$RELEASE_DIR/server.py\"'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.checkout-worker = {
    description = "Checkout order worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "checkout";
      Group = "checkout";
      EnvironmentFile = "/etc/checkout/worker.env";
      Environment = "PYTHONPATH=/var/lib/checkout";
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${pkgs.python3}/bin/python \"$RELEASE_DIR/worker.py\"'";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
