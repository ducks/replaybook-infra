{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 sqlite nginx ];
  users.groups.notification = {};
  users.users.notification = { isSystemUser = true; group = "notification"; };
  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      extraConfig = "include /etc/notification/routes.conf;";
    };
  };
  systemd.services.nginx = {
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
  };
  systemd.services.incident-provision = {
    description = "Provision application deployment";
    wantedBy = [ "multi-user.target" ];
    before = [ "nginx.service" "notification-api.service" "notification-worker.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig.Type = "oneshot";
    script = ''
      install -d -m 0755 /etc/notification /var/lib/notification/current
      chown notification:notification /var/lib/notification
      if [[ ! -e /var/lib/notification/current/service.py ]]; then
        install -m 0644 ${./app/service.py} /var/lib/notification/current/service.py
      fi
      if [[ ! -e /etc/notification/routes.conf ]]; then
        cat > /etc/notification/routes.conf <<'ROUTES'
location / { proxy_pass http://127.0.0.1:3000; }
ROUTES
      fi
      if [[ ! -e /etc/notification/notification-api.env ]]; then
        cat > /etc/notification/notification-api.env <<'ENV'
PORT=3000
DATABASE=/var/lib/notification/messages.sqlite3
ENV
      fi
      if [[ ! -e /etc/notification/notification-worker.env ]]; then
        cat > /etc/notification/notification-worker.env <<'ENV'
DATABASE=/var/lib/notification/messages.sqlite3
DECODER=1
ENV
      fi
    '';
  };
  systemd.services.notification-api = {
    description = "notification api";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    serviceConfig = {
      User = "notification";
      Group = "notification";
      EnvironmentFile = "/etc/notification/notification-api.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/notification/current/service.py api";
      Restart = "always";
      RestartSec = 1;
    };
  };
  systemd.services.notification-worker = {
    description = "notification worker";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    serviceConfig = {
      User = "notification";
      Group = "notification";
      EnvironmentFile = "/etc/notification/notification-worker.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/notification/current/service.py worker";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
