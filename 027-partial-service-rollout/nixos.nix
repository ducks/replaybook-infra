{ lib, pkgs, ... }:

let
  appDir = ./app;
  python = pkgs.python3.withPackages (packages: with packages; [ psycopg ]);
  releaseRoot = "/var/lib/order-api/releases";
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ curl nginx postgresql_16 python ];

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "orders" ];
    ensureUsers = [{ name = "orders"; ensureDBOwnership = true; }];
    authentication = lib.mkOverride 10 ''
      local all all trust
      host all all 127.0.0.1/32 trust
      host all all ::1/128 trust
    '';
  };

  services.nginx = {
    enable = true;
    appendHttpConfig = ''
      upstream order_api {
        server 127.0.0.1:3001;
        server 127.0.0.1:3002;
      }
    '';
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://order_api";
      locations."/instances/blue/".proxyPass = "http://127.0.0.1:3001/";
      locations."/instances/green/".proxyPass = "http://127.0.0.1:3002/";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision order API services";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" ];
    requires = [ "postgresql.service" ];
    before = [ "order-api-blue.service" "order-api-green.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 \
        /etc/order-api \
        ${releaseRoot}/20260816 \
        ${releaseRoot}/20260817/db/migrate

      if [[ ! -e ${releaseRoot}/20260817/server.py ]]; then
        install -m 0755 ${appDir}/releases/20260816/server.py \
          ${releaseRoot}/20260816/server.py
        install -m 0755 ${appDir}/releases/20260817/server.py \
          ${releaseRoot}/20260817/server.py
        install -m 0644 \
          ${appDir}/releases/20260817/db/migrate/202608170001_add_deployment_generation.sql \
          ${releaseRoot}/20260817/db/migrate/202608170001_add_deployment_generation.sql
      fi
      ln -sfn ${releaseRoot}/20260817 /var/lib/order-api/current

      if [[ ! -e /etc/order-api/common.env ]]; then
        printf '%s\n' \
          'DATABASE_URL=postgresql://orders@127.0.0.1/orders' \
          > /etc/order-api/common.env
      fi
      if [[ ! -e /etc/order-api/blue.env ]]; then
        printf '%s\n' \
          'PORT=3001' \
          'INSTANCE_NAME=blue' \
          'RELEASE_DIR=/var/lib/order-api/current' \
          > /etc/order-api/blue.env
      fi
      if [[ ! -e /etc/order-api/green.env ]]; then
        printf '%s\n' \
          'PORT=3002' \
          'INSTANCE_NAME=green' \
          'RELEASE_DIR=${releaseRoot}/20260816' \
          > /etc/order-api/green.env
      fi

      psql --host 127.0.0.1 --username orders --dbname orders \
        --set ON_ERROR_STOP=1 <<'SQL'
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version text PRIMARY KEY
      );
      CREATE TABLE IF NOT EXISTS orders (
        order_id text PRIMARY KEY,
        payload text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      SQL
    '';
  };

  systemd.services.order-api-blue = {
    description = "Order API blue instance";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [ "/etc/order-api/common.env" "/etc/order-api/blue.env" ];
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${python}/bin/python \"$RELEASE_DIR/server.py\"'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.order-api-green = {
    description = "Order API green instance";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [ "/etc/order-api/common.env" "/etc/order-api/green.env" ];
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${python}/bin/python \"$RELEASE_DIR/server.py\"'";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
