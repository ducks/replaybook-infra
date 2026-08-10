{ lib, pkgs, ... }:

let
  appDir = ./app;
  rubyEnv = pkgs.bundlerEnv {
    name = "replaybook-partial-rollout-env";
    gemdir = appDir;
  };
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx postgresql_16 redis rubyEnv.wrappedRuby ];

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "replaybook" ];
    ensureUsers = [{ name = "replaybook"; ensureDBOwnership = true; }];
    authentication = lib.mkOverride 10 ''
      local all all trust
      host all all 127.0.0.1/32 trust
      host all all ::1/128 trust
    '';
  };

  services.redis.servers.replaybook = { enable = true; bind = "127.0.0.1"; port = 6379; };
  services.nginx = {
    enable = true;
    virtualHosts.default = { default = true; locations."/".proxyPass = "http://127.0.0.1:3000"; };
  };

  systemd.services.incident-provision = {
    description = "Provision the Replaybook partial Rails rollout incident";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" "redis-replaybook.service" ];
    requires = [ "postgresql.service" "redis-replaybook.service" ];
    before = [ "checkout-web.service" "checkout-sidekiq-standard.service" "checkout-sidekiq-express.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 /etc/replaybook /var/lib/checkout/releases
      if [[ ! -e /var/lib/checkout/releases/20260809 ]]; then
        cp -R ${appDir}/releases/20260809 /var/lib/checkout/releases/20260809
      fi
      if [[ ! -e /var/lib/checkout/releases/20260810 ]]; then
        cp -R ${appDir}/releases/20260810 /var/lib/checkout/releases/20260810
      fi
      ln -sfn /var/lib/checkout/releases/20260810 /var/lib/checkout/current
      if [[ ! -e /etc/replaybook/checkout.env ]]; then
        printf '%s\n' 'REDIS_URL=redis://127.0.0.1:6379/0' > /etc/replaybook/checkout.env
      fi
      if [[ ! -e /etc/replaybook/standard.env ]]; then
        printf '%s\n' 'RELEASE_DIR=/var/lib/checkout/current' 'WORKER_NAME=standard' > /etc/replaybook/standard.env
      fi
      if [[ ! -e /etc/replaybook/express.env ]]; then
        printf '%s\n' 'RELEASE_DIR=/var/lib/checkout/releases/20260809' 'WORKER_NAME=express' > /etc/replaybook/express.env
      fi
      psql --host 127.0.0.1 --username replaybook --dbname replaybook <<'SQL'
      CREATE TABLE IF NOT EXISTS completed_jobs (
        job_id text PRIMARY KEY,
        worker_name text NOT NULL,
        release_version text NOT NULL,
        completed_at timestamptz NOT NULL DEFAULT now()
      );
      SQL
    '';
  };

  systemd.services.checkout-web = {
    description = "Replaybook checkout web service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/replaybook/checkout.env";
      ExecStart = "${rubyEnv.wrappedRuby}/bin/ruby /var/lib/checkout/current/server.rb";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.checkout-sidekiq-standard = {
    description = "Replaybook standard checkout Sidekiq worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [ "/etc/replaybook/checkout.env" "/etc/replaybook/standard.env" ];
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${rubyEnv}/bin/sidekiq -r \"$RELEASE_DIR/jobs.rb\" -q standard -c 1'";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.checkout-sidekiq-express = {
    description = "Replaybook express checkout Sidekiq worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [ "/etc/replaybook/checkout.env" "/etc/replaybook/express.env" ];
      ExecStart = "${pkgs.bash}/bin/bash -c 'exec ${rubyEnv}/bin/sidekiq -r \"$RELEASE_DIR/jobs.rb\" -q express -c 1'";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
