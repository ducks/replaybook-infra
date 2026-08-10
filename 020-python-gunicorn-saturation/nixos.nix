{ pkgs, ... }:

let
  appDir = ./app;
  pythonEnv = pkgs.python3.withPackages (packages: with packages; [ gunicorn ]);
in {
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx pythonEnv ];

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook export service";
    wantedBy = [ "multi-user.target" ];
    before = [ "export-web.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils ];
    script = ''
      install -d -m 0755 /etc/replaybook /var/lib/export-service
      if [[ ! -e /var/lib/export-service/app.py ]]; then
        cp ${appDir}/app.py /var/lib/export-service/app.py
        cp ${appDir}/start.sh /var/lib/export-service/start.sh
        chmod 0755 /var/lib/export-service/start.sh
      fi
      if [[ ! -e /etc/replaybook/export-web.env ]]; then
        printf '%s\n' \
          'WEB_WORKERS=1' \
          'WEB_THREADS=1' \
          'REQUEST_TIMEOUT=2' \
          > /etc/replaybook/export-web.env
      fi
    '';
  };

  systemd.services.export-web = {
    description = "Replaybook export web service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    path = [ pkgs.bash pythonEnv ];
    serviceConfig = {
      EnvironmentFile = "/etc/replaybook/export-web.env";
      WorkingDirectory = "/var/lib/export-service";
      ExecStart = "/var/lib/export-service/start.sh";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
