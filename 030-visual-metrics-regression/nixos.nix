{ pkgs, ... }:

let
  appDir = ./app;
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ curl nginx python3 ];

  users.users.metrics-api = {
    isSystemUser = true;
    group = "metrics-api";
  };
  users.groups.metrics-api = { };

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3200";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision the report rendering service";
    wantedBy = [ "multi-user.target" ];
    before = [ "metrics-api.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils ];
    script = ''
      install -d -m 0755 /etc/metrics-api /var/lib/metrics-api
      if [[ ! -e /var/lib/metrics-api/server.py ]]; then
        cp ${appDir}/server.py /var/lib/metrics-api/server.py
        chmod 0755 /var/lib/metrics-api/server.py
      fi
      if [[ ! -e /etc/metrics-api/service.env ]]; then
        printf '%s\n' \
          'PORT=3200' \
          'CACHE_MAX_ENTRIES=0' \
          'CACHE_ENTRY_KIB=256' \
          'PRESSURE_THRESHOLD=80' \
          > /etc/metrics-api/service.env
      fi
    '';
  };

  systemd.services.metrics-api = {
    description = "Report rendering API";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      User = "metrics-api";
      Group = "metrics-api";
      EnvironmentFile = "/etc/metrics-api/service.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/metrics-api/server.py";
      MemoryMax = "192M";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
