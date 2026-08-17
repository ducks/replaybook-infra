{ pkgs, ... }:

let
  appDir = ./app;
  rubyEnv = pkgs.ruby.withPackages (packages: with packages; [ pg puma rack ]);
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx postgresql_16 rubyEnv ];

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "discourse" ];
    ensureUsers = [{ name = "discourse"; ensureDBOwnership = true; }];
    authentication = pkgs.lib.mkOverride 10 ''
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
    description = "Provision the forum and its installed plugin";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" ];
    requires = [ "postgresql.service" ];
    before = [ "discourse-web.service" "discourse-sidekiq.service" ];
    serviceConfig.Type = "oneshot";
    serviceConfig.RemainAfterExit = true;
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 /etc/discourse /var/lib/discourse/plugins/discourse-presence

      if [[ ! -e /var/lib/discourse/plugins/discourse-presence/initializer.rb ]]; then
        install -m 0644 ${appDir}/plugin/initializer.rb \
          /var/lib/discourse/plugins/discourse-presence/initializer.rb
      fi

      if [[ ! -e /etc/discourse/runtime.env ]]; then
        printf '%s\n' \
          'DISCOURSE_RELEASE=20260816' \
          'DISCOURSE_PLUGIN_API_VERSION=1' \
          'DISCOURSE_PLUGIN_INITIALIZER=/var/lib/discourse/plugins/discourse-presence/initializer.rb' \
          'DISCOURSE_RUNTIME_FILE=/etc/discourse/runtime.env' \
          > /etc/discourse/runtime.env
      fi

      psql --host 127.0.0.1 --username discourse --dbname discourse \
        --set ON_ERROR_STOP=1 <<'SQL'
      CREATE TABLE IF NOT EXISTS topics (
        topic_id text PRIMARY KEY,
        state text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE IF NOT EXISTS uploads (
        upload_id text PRIMARY KEY,
        topic_id text NOT NULL REFERENCES topics(topic_id),
        state text NOT NULL
      );
      CREATE TABLE IF NOT EXISTS plugin_topic_data (
        topic_id text PRIMARY KEY REFERENCES topics(topic_id),
        state text NOT NULL
      );
      CREATE TABLE IF NOT EXISTS background_jobs (
        job_id text PRIMARY KEY,
        state text NOT NULL,
        attempt_count integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE IF NOT EXISTS plugin_settings (
        name text PRIMARY KEY,
        value text NOT NULL
      );
      CREATE TABLE IF NOT EXISTS runtime_state (
        singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
        incident_triggered boolean NOT NULL DEFAULT false,
        processing_enabled boolean NOT NULL DEFAULT false
      );
      INSERT INTO plugin_settings (name, value)
      VALUES ('discourse-presence-enabled', 'true')
      ON CONFLICT (name) DO NOTHING;
      INSERT INTO runtime_state (singleton, incident_triggered, processing_enabled)
      VALUES (true, false, false)
      ON CONFLICT (singleton) DO NOTHING;
      SQL
    '';
  };

  systemd.services.discourse-web = {
    description = "Discourse web application";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/runtime.env";
      WorkingDirectory = "${appDir}";
      ExecStart = "${rubyEnv}/bin/puma --bind tcp://127.0.0.1:3000 --threads 2:4 config.ru";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.discourse-sidekiq = {
    description = "Discourse background job worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/runtime.env";
      RuntimeDirectory = "discourse-sidekiq";
      WorkingDirectory = "${appDir}";
      ExecStart = "${rubyEnv}/bin/ruby worker.rb";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
