{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 sqlite nginx ];
  users.groups.reservation = {};
  users.users.reservation = { isSystemUser = true; group = "reservation"; };
  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      extraConfig = "include /etc/reservation/routes.conf;";
    };
  };
  systemd.services.nginx = {
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
  };
  systemd.services.incident-provision = {
    description = "Provision application deployment";
    wantedBy = [ "multi-user.target" ];
    before = [ "nginx.service" "reservation-api.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig.Type = "oneshot";
    script = ''
      install -d -m 0755 /etc/reservation /var/lib/reservation/current
      chown reservation:reservation /var/lib/reservation
      if [[ ! -e /var/lib/reservation/current/service.py ]]; then
        install -m 0644 ${./app/service.py} /var/lib/reservation/current/service.py
      fi
      if [[ ! -e /etc/reservation/routes.conf ]]; then
        cat > /etc/reservation/routes.conf <<'ROUTES'
location / { proxy_pass http://127.0.0.1:3000; }
ROUTES
      fi
      if [[ ! -e /etc/reservation/reservation-api.env ]]; then
        cat > /etc/reservation/reservation-api.env <<'ENV'
PORT=3000
DATABASE=/var/lib/reservation/reservations.sqlite3
ATOMIC_WRITES=0
ENV
      fi
    '';
  };
  systemd.services.reservation-api = {
    description = "reservation api";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    serviceConfig = {
      User = "reservation";
      Group = "reservation";
      EnvironmentFile = "/etc/reservation/reservation-api.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/reservation/current/service.py ";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
