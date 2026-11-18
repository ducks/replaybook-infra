{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 sqlite nginx iproute2 ];
  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      extraConfig = "include /etc/ledgerlens-edge/routes.conf;";
    };
  };
  systemd.services.nginx = {
    after = [ "ledgerlens-source.service" ];
    requires = [ "ledgerlens-source.service" ];
  };
  systemd.services.ledgerlens-source = {
    description = "Stage the application source checkout";
    wantedBy = [ "multi-user.target" ];
    before = [ "nginx.service" ];
    serviceConfig.Type = "oneshot";
    path = [ pkgs.coreutils pkgs.git ];
    script = ''
      install -d /opt/ledgerlens /etc/ledgerlens-edge
      if [[ ! -d /opt/ledgerlens/repo ]]; then
        cp -R ${./repo} /opt/ledgerlens/repo
        chmod -R u+w /opt/ledgerlens/repo
        git -C /opt/ledgerlens/repo init --initial-branch=main
        git -C /opt/ledgerlens/repo config user.name LedgerLens
        git -C /opt/ledgerlens/repo config user.email example@localhost
        git -C /opt/ledgerlens/repo add .
        GIT_AUTHOR_DATE=2026-11-18T00:00:00Z GIT_COMMITTER_DATE=2026-11-18T00:00:00Z \
          git -C /opt/ledgerlens/repo commit -m 'LedgerLens source release 0.4.0'
      fi
      if [[ ! -e /etc/ledgerlens-edge/routes.conf ]]; then
        printf '%s\n' 'location / { return 503 "deployment-required"; }' > /etc/ledgerlens-edge/routes.conf
      fi
    '';
  };
}
