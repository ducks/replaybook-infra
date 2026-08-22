{ lib, pkgs, ... }:

let
  appDir = ./app;
  python = pkgs.python3.withPackages (packages: with packages; [ psycopg redis ]);
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ curl nginx postgresql_16 redis python ];

  users.users.reservation-api = {
    isSystemUser = true;
    group = "reservation-api";
  };
  users.groups.reservation-api = { };

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    ensureDatabases = [ "reservations" ];
    ensureUsers = [{ name = "reservations"; ensureDBOwnership = true; }];
    authentication = lib.mkOverride 10 ''
      local all all trust
      host all all 127.0.0.1/32 trust
      host all all ::1/128 trust
    '';
  };

  services.redis.servers.reservations = {
    enable = true;
    bind = "127.0.0.1";
    port = 6379;
  };

  systemd.services.incident-provision = {
    description = "Provision the reservation topology";
    wantedBy = [ "multi-user.target" ];
    after = [ "postgresql.service" "redis-reservations.service" ];
    requires = [ "postgresql.service" "redis-reservations.service" ];
    before = [ "reservation-api.service" "reservation-worker.service" "incident-nginx.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.postgresql_16 ];
    script = ''
      install -d -m 0755 /etc/reservation-api /var/log/nginx
      if [[ ! -e /etc/reservation-api/api.env ]]; then
        printf '%s\n' \
          'PORT=3100' \
          'DATABASE_URL=postgresql://reservations@127.0.0.1/reservations' \
          'REDIS_URL=redis://127.0.0.1:6379/4' \
          > /etc/reservation-api/api.env
      fi
      if [[ ! -e /etc/reservation-api/worker.env ]]; then
        printf '%s\n' \
          'DATABASE_URL=postgresql://reservations@127.0.0.1/reservations' \
          'REDIS_URL=redis://127.0.0.1:6379/7' \
          > /etc/reservation-api/worker.env
      fi
      if [[ ! -e /etc/reservation-api/nginx.conf ]]; then
        cat > /etc/reservation-api/nginx.conf <<'EOF'
      pid /run/incident-nginx/nginx.pid;
      events {}
      http {
        access_log /var/log/nginx/reservation-access.log;
        error_log stderr notice;
        server {
          listen 80;
          location = /health {
            proxy_pass http://127.0.0.1:3101/health;
          }
          location /reservations/ {
            proxy_pass http://127.0.0.1:3100;
          }
        }
      }
      EOF
      fi

      psql --host 127.0.0.1 --username reservations --dbname reservations \
        --set ON_ERROR_STOP=1 <<'SQL'
      CREATE TABLE IF NOT EXISTS reservations (
        reservation_id text PRIMARY KEY,
        state text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        completed_at timestamptz
      );
      SQL
    '';
  };

  systemd.services.reservation-api = {
    description = "Reservation API";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "reservation-api";
      Group = "reservation-api";
      EnvironmentFile = "/etc/reservation-api/api.env";
      ExecStart = "${python}/bin/python ${appDir}/api.py";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.reservation-worker = {
    description = "Reservation queue worker";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "reservation-api";
      Group = "reservation-api";
      EnvironmentFile = "/etc/reservation-api/worker.env";
      ExecStart = "${python}/bin/python ${appDir}/worker.py";
      Restart = "always";
      RestartSec = 1;
    };
  };

  systemd.services.incident-nginx = {
    description = "Reservation edge proxy";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" "reservation-api.service" ];
    after = [ "incident-provision.service" "reservation-api.service" "network.target" ];
    serviceConfig = {
      RuntimeDirectory = "incident-nginx";
      ExecStartPre = "${pkgs.nginx}/bin/nginx -t -c /etc/reservation-api/nginx.conf";
      ExecStart = "${pkgs.nginx}/bin/nginx -c /etc/reservation-api/nginx.conf -g 'daemon off;'";
      ExecReload = "${pkgs.nginx}/bin/nginx -s reload -c /etc/reservation-api/nginx.conf";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
