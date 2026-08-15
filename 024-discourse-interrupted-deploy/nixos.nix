{ lib, pkgs, ... }:

let
  appDir = ./app;
  rubyEnv = pkgs.ruby.withPackages (packages: with packages; [ pg puma rack ]);
  releaseRoot = "/var/lib/discourse/releases";
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx postgresql_16 rubyEnv ];

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "discourse" ];
    ensureUsers = [{ name = "discourse"; ensureDBOwnership = true; }];
    authentication = lib.mkOverride 10 ''
      local all all trust
      host all all 127.0.0.1/32 trust
      host all all ::1/128 trust
    '';
  };

  services.nginx = {
    enable = true;
    appendHttpConfig = ''
      upstream discourse_web {
        server 127.0.0.1:3001;
        server 127.0.0.1:3002;
      }
    '';
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://discourse_web";
      locations."/instances/blue/".proxyPass = "http://127.0.0.1:3001/";
      locations."/instances/green/".proxyPass = "http://127.0.0.1:3002/";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision hosted forum export services";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" ];
    requires = [ "postgresql.service" ];
    before = [
      "discourse-web-blue.service"
      "discourse-web-green.service"
      "discourse-export-worker.service"
    ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 \
        /etc/discourse \
        ${releaseRoot}/20260813 \
        ${releaseRoot}/20260814/db/migrate

      if [[ ! -e ${releaseRoot}/20260814/config.ru ]]; then
        cp -R ${appDir}/releases/20260813/. ${releaseRoot}/20260813/
        cp -R ${appDir}/releases/20260814/. ${releaseRoot}/20260814/
        cp ${appDir}/releases/20260814/db/migrate/202608140001_add_export_delivery.sql \
          ${releaseRoot}/20260814/db/migrate/202608140001_add_export_delivery.sql
      fi
      ln -sfn ${releaseRoot}/20260814 /var/lib/discourse/current

      if [[ ! -e /etc/discourse/blue.env ]]; then
        printf '%s\n' \
          'RELEASE_DIR=/var/lib/discourse/current' \
          'RELEASE_VERSION=20260814' \
          > /etc/discourse/blue.env
      fi
      if [[ ! -e /etc/discourse/green.env ]]; then
        printf '%s\n' \
          'RELEASE_DIR=${releaseRoot}/20260813' \
          'RELEASE_VERSION=20260813' \
          > /etc/discourse/green.env
      fi
      if [[ ! -e /etc/discourse/worker.env ]]; then
        printf '%s\n' \
          'RELEASE_DIR=/var/lib/discourse/current' \
          'RELEASE_VERSION=20260814' \
          > /etc/discourse/worker.env
      fi

      psql --host 127.0.0.1 --username discourse --dbname discourse \
        --set ON_ERROR_STOP=1 <<'SQL'
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version text PRIMARY KEY
      );
      CREATE TABLE IF NOT EXISTS staff_exports (
        export_id text PRIMARY KEY,
        state text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        attempt_count integer NOT NULL DEFAULT 0,
        artifact_key text
      );
      SQL
    '';
  };

  systemd.services.discourse-web-blue = {
    description = "Hosted forum web instance blue";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/blue.env";
      ExecStart = "${pkgs.bash}/bin/bash -c 'cd \"$RELEASE_DIR\" && exec ${rubyEnv}/bin/puma --bind tcp://127.0.0.1:3001 --threads 2:4 config.ru'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.discourse-web-green = {
    description = "Hosted forum web instance green";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/green.env";
      ExecStart = "${pkgs.bash}/bin/bash -c 'cd \"$RELEASE_DIR\" && exec ${rubyEnv}/bin/puma --bind tcp://127.0.0.1:3002 --threads 2:4 config.ru'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.discourse-export-worker = {
    description = "Hosted forum staff export worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/worker.env";
      ExecStart = "${pkgs.bash}/bin/bash -c 'cd \"$RELEASE_DIR\" && exec ${rubyEnv}/bin/ruby worker.rb'";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
