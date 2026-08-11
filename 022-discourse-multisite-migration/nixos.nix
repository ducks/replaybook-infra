{ lib, pkgs, ... }:

let
  appDir = ./app;
  rubyEnv = pkgs.ruby.withPackages (packages: with packages; [ pg puma rack ]);
  migration = "/var/lib/discourse/current/db/migrate/202608110001_add_delivery_state.sql";
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx postgresql_16 rubyEnv ];

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "discourse_default" "discourse_secondary" ];
    ensureUsers = [ { name = "replaybook"; } ];
    authentication = lib.mkOverride 10 ''
      local all all trust
      host all all 127.0.0.1/32 trust
      host all all ::1/128 trust
    '';
  };

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook multisite forum services";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" ];
    requires = [ "postgresql.service" ];
    before = [ "discourse-web.service" "discourse-worker.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 /etc/discourse /var/lib/discourse/current/db/migrate
      if [[ ! -e /var/lib/discourse/current/server.rb ]]; then
        cp ${appDir}/config.ru /var/lib/discourse/current/config.ru
        cp ${appDir}/server.rb /var/lib/discourse/current/server.rb
        cp ${appDir}/worker.rb /var/lib/discourse/current/worker.rb
        cp ${appDir}/site_config.rb /var/lib/discourse/current/site_config.rb
        cp ${appDir}/db/migrate/202608110001_add_delivery_state.sql ${migration}
      fi
      if [[ ! -e /etc/discourse/multisite.env ]]; then
        printf '%s\n' \
          'DEFAULT_DATABASE=discourse_default' \
          'SECONDARY_DATABASE=discourse_secondary' \
          > /etc/discourse/multisite.env
      fi

      for database in discourse_default discourse_secondary; do
        psql --host 127.0.0.1 --username postgres --dbname postgres \
          --set ON_ERROR_STOP=1 \
          --command "ALTER DATABASE $database OWNER TO replaybook"
        psql --host 127.0.0.1 --username replaybook --dbname "$database" \
          --set ON_ERROR_STOP=1 \
          --command "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY); CREATE TABLE IF NOT EXISTS site_identity (identity text PRIMARY KEY); CREATE TABLE IF NOT EXISTS moderation_jobs (job_id text PRIMARY KEY, completed_at timestamptz); CREATE TABLE IF NOT EXISTS job_attempts (job_id text PRIMARY KEY, attempt_count integer NOT NULL DEFAULT 0)"
      done

      psql --host 127.0.0.1 --username replaybook --dbname discourse_default \
        --set ON_ERROR_STOP=1 \
        --command "INSERT INTO site_identity (identity) VALUES ('default-site') ON CONFLICT DO NOTHING"
      psql --host 127.0.0.1 --username replaybook --dbname discourse_secondary \
        --set ON_ERROR_STOP=1 \
        --command "INSERT INTO site_identity (identity) VALUES ('secondary-site') ON CONFLICT DO NOTHING"
      psql --host 127.0.0.1 --username replaybook --dbname discourse_default \
        --set ON_ERROR_STOP=1 \
        --file ${migration}
    '';
  };

  systemd.services.discourse-web = {
    description = "Discourse multisite web service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/multisite.env";
      WorkingDirectory = "/var/lib/discourse/current";
      ExecStart = "${rubyEnv}/bin/puma --bind tcp://127.0.0.1:3000 --threads 2:4 /var/lib/discourse/current/config.ru";
      StandardOutput = "journal+console";
      StandardError = "journal+console";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.discourse-worker = {
    description = "Discourse multisite background worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/multisite.env";
      WorkingDirectory = "/var/lib/discourse/current";
      ExecStart = "${rubyEnv}/bin/ruby /var/lib/discourse/current/worker.rb";
      StandardOutput = "journal+console";
      StandardError = "journal+console";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
