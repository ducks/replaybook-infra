{ pkgs, ... }:

let appDir = ./app;
in {
  imports = [ ../worker/base.nix ];

  environment.systemPackages = with pkgs; [ nginx nodejs_22 ];

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision Replaybook checkout task service";
    wantedBy = [ "multi-user.target" ];
    before = [ "checkout-node.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils ];
    script = ''
      install -d -m 0755 /var/lib/checkout-node
      if [[ ! -e /var/lib/checkout-node/server.js ]]; then
        cp ${appDir}/server.js /var/lib/checkout-node/server.js
      fi
      touch /var/lib/checkout-node/completed.log
    '';
  };

  systemd.services.checkout-node = {
    description = "Replaybook checkout task service";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      WorkingDirectory = "/var/lib/checkout-node";
      ExecStart = "${pkgs.nodejs_22}/bin/node /var/lib/checkout-node/server.js";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
