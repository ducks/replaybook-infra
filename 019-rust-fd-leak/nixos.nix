{ pkgs, ... }:

let appDir = ./app;
in {
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ cargo gcc nginx rustc ];

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook document service";
    wantedBy = [ "multi-user.target" ];
    before = [ "document-service.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.cargo pkgs.coreutils pkgs.gcc pkgs.rustc ];
    script = ''
      install -d -m 0755 /var/lib/fd-service
      if [[ ! -e /var/lib/fd-service/Cargo.toml ]]; then
        cp -R ${appDir}/. /var/lib/fd-service/
      fi
      printf '%s\n' 'document payload' > /var/lib/fd-service/payload.txt
      cd /var/lib/fd-service
      cargo build --release --offline
    '';
  };

  systemd.services.document-service = {
    description = "Replaybook document processing service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      WorkingDirectory = "/var/lib/fd-service";
      ExecStart = "/var/lib/fd-service/target/release/fd-service";
      LimitNOFILE = 80;
      Restart = "always";
      RestartSec = 1;
    };
  };
}
