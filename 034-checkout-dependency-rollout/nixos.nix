{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 sqlite nginx ];
  users.groups.checkout = {};
  users.users.checkout = { isSystemUser = true; group = "checkout"; };
  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      extraConfig = "include /etc/checkout/routes.conf;";
    };
  };
  systemd.services.nginx = {
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
  };
  systemd.services.incident-provision = {
    description = "Provision application deployment";
    wantedBy = [ "multi-user.target" ];
    before = [ "nginx.service" "checkout-api.service" "invoice-ledger.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig.Type = "oneshot";
    script = ''
      install -d -m 0755 /etc/checkout /var/lib/checkout/current
      chown checkout:checkout /var/lib/checkout
      if [[ ! -e /var/lib/checkout/current/service.py ]]; then
        install -m 0644 ${./app/service.py} /var/lib/checkout/current/service.py
      fi
      if [[ ! -e /etc/checkout/routes.conf ]]; then
        cat > /etc/checkout/routes.conf <<'ROUTES'
location = /health { proxy_pass http://127.0.0.1:3000; }
location /orders/ { proxy_pass http://127.0.0.1:3009; }
location /ledger/ { proxy_pass http://127.0.0.1:3002/; }
ROUTES
      fi
      if [[ ! -e /etc/checkout/checkout-api.env ]]; then
        cat > /etc/checkout/checkout-api.env <<'ENV'
PORT=3000
DATABASE=/var/lib/checkout/api.sqlite3
LEDGER_URL=http://127.0.0.1:3001
ENV
      fi
      if [[ ! -e /etc/checkout/invoice-ledger.env ]]; then
        cat > /etc/checkout/invoice-ledger.env <<'ENV'
PORT=3002
DATABASE=/var/lib/checkout/ledger.sqlite3
ENV
      fi
    '';
  };
  systemd.services.checkout-api = {
    description = "checkout api";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    serviceConfig = {
      User = "checkout";
      Group = "checkout";
      EnvironmentFile = "/etc/checkout/checkout-api.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/checkout/current/service.py api";
      Restart = "always";
      RestartSec = 1;
    };
  };
  systemd.services.invoice-ledger = {
    description = "invoice ledger";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    serviceConfig = {
      User = "checkout";
      Group = "checkout";
      EnvironmentFile = "/etc/checkout/invoice-ledger.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/checkout/current/service.py ledger";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
