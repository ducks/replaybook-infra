{ pkgs, ... }:

let
  appDir = ./app;
  rubyEnv = pkgs.ruby.withPackages (packages: with packages; [ puma rack ]);
  releaseUploads = "/var/lib/discourse/releases/20260810/public/uploads/default";
in
{
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx rubyEnv ];

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook forum services";
    wantedBy = [ "multi-user.target" ];
    before = [ "discourse-web.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils ];
    script = ''
      install -d -m 0755 \
        /etc/discourse \
        /var/lib/discourse/current \
        ${releaseUploads} \
        /var/lib/discourse/shared/standalone/uploads/default
      if [[ ! -e /var/lib/discourse/current/app.ru ]]; then
        cp ${appDir}/app.ru /var/lib/discourse/current/app.ru
      fi
      if [[ ! -e /var/lib/discourse/shared/standalone/uploads/default/historical-avatar ]]; then
        printf '%s\n' 'historical upload' \
          > /var/lib/discourse/shared/standalone/uploads/default/historical-avatar
      fi
      if [[ ! -e /etc/discourse/discourse.env ]]; then
        printf '%s\n' \
          'UPLOAD_ROOT=${releaseUploads}' \
          > /etc/discourse/discourse.env
      fi
    '';
  };

  systemd.services.discourse-web = {
    description = "Discourse web service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      EnvironmentFile = "/etc/discourse/discourse.env";
      WorkingDirectory = "/var/lib/discourse/current";
      ExecStartPre = "${pkgs.bash}/bin/bash -c 'rm -rf ${releaseUploads}; install -d -m 0755 ${releaseUploads}'";
      ExecStart = "${rubyEnv}/bin/puma --bind tcp://127.0.0.1:3000 --threads 2:4 /var/lib/discourse/current/app.ru";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
