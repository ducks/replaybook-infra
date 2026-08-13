{ pkgs, ... }:

let
  appDir = ./app;
  python = pkgs.python3;
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx python sqlite ];

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/old/".proxyPass = "http://127.0.0.1:3001";
      locations."/new/".proxyPass = "http://127.0.0.1:3002";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook session services";
    wantedBy = [ "multi-user.target" ];
    before = [ "session-old.service" "session-new.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.sqlite ];
    script = ''
      install -d -m 0755 /etc/replaybook /var/lib/session-app/current
      install -d -m 0750 /var/lib/session-app/state
      if [[ ! -e /var/lib/session-app/current/server.py ]]; then
        install -m 0755 ${appDir}/server.py /var/lib/session-app/current/server.py
        install -m 0755 ${appDir}/rotate_sessions.py /var/lib/session-app/current/rotate_sessions.py
      fi
      if [[ ! -e /etc/replaybook/session-common.env ]]; then
        printf '%s\n' \
          'SESSION_DATABASE=/var/lib/session-app/state/sessions.sqlite3' \
          > /etc/replaybook/session-common.env
      fi
      if [[ ! -e /etc/replaybook/session-old.env ]]; then
        printf '%s\n' \
          'INSTANCE_NAME=old' \
          'PORT=3001' \
          'RELEASE_VERSION=20260811' \
          'SESSION_SECRET=retired-signing-secret-20260811' \
          > /etc/replaybook/session-old.env
      fi
      if [[ ! -e /etc/replaybook/session-new.env ]]; then
        printf '%s\n' \
          'INSTANCE_NAME=new' \
          'PORT=3002' \
          'RELEASE_VERSION=20260812' \
          'SESSION_SECRET=current-signing-secret-20260812' \
          > /etc/replaybook/session-new.env
      fi
      if [[ ! -e /etc/replaybook/session-rotation.env ]]; then
        printf '%s\n' \
          'OLD_SESSION_SECRET=retired-signing-secret-20260811' \
          'NEW_SESSION_SECRET=current-signing-secret-20260812' \
          > /etc/replaybook/session-rotation.env
      fi
      sqlite3 /var/lib/session-app/state/sessions.sqlite3 <<'SQL'
      CREATE TABLE IF NOT EXISTS sessions (
        session_id text PRIMARY KEY,
        signature text NOT NULL,
        revoked integer NOT NULL CHECK (revoked IN (0, 1))
      );
      INSERT OR IGNORE INTO sessions (session_id, signature, revoked)
      VALUES (
        'revoked-session',
        'c367ab5e86cbd96e24c48546f1827003a80bc29d4233ea6129e7cd87f88f18b8',
        1
      );
      SQL
      chown -R root:root /var/lib/session-app
      chmod 0750 /var/lib/session-app/state
      chmod 0640 /var/lib/session-app/state/sessions.sqlite3
    '';
  };

  systemd.services.session-old = {
    description = "Old-generation session service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [
        "/etc/replaybook/session-common.env"
        "/etc/replaybook/session-old.env"
      ];
      ExecStart = "${python}/bin/python /var/lib/session-app/current/server.py";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.session-new = {
    description = "New-generation session service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = [
        "/etc/replaybook/session-common.env"
        "/etc/replaybook/session-new.env"
      ];
      ExecStart = "${python}/bin/python /var/lib/session-app/current/server.py";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
