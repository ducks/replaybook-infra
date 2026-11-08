{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 nginx dnsmasq bind ];
  system.nssDatabases.hosts = [ "files" "dns" ];
  networking.resolvconf.enable = false;
  services.nginx = {
    enable = true;
    virtualHosts.default = { default = true; locations."/".proxyPass = "http://127.0.0.1:3000"; locations."/backend/".proxyPass = "http://127.0.0.1:3001/"; };
  };
  systemd.services.discovery-provision = {
    wantedBy = [ "multi-user.target" ];
    before = [ "resolver-policy.service" "inventory.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
    script = ''
      install -d -m 0755 /etc/discovery /srv/inventory
      if [[ ! -e /etc/discovery/resolv.conf ]]; then
        printf 'nameserver 127.0.0.1\noptions timeout:1 attempts:1\n' > /etc/discovery/resolv.conf
      fi
      if [[ ! -e /etc/discovery/hosts ]]; then
        printf '127.0.0.1 localhost\n127.0.0.2 inventory.internal\n' > /etc/discovery/hosts
      fi
      printf 'inventory-ready\n' > /srv/inventory/health
    '';
  };
  systemd.services.resolver-policy = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "discovery-provision.service" ];
    after = [ "discovery-provision.service" ];
    before = [ "discovery-web.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
    script = ''
      rm -f /etc/resolv.conf
      install -m 0644 /etc/discovery/resolv.conf /etc/resolv.conf
      rm -f /etc/hosts
      install -m 0644 /etc/discovery/hosts /etc/hosts
    '';
  };
  systemd.services.inventory-dns = {
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      ExecStart = "${pkgs.dnsmasq}/bin/dnsmasq --keep-in-foreground --user=root --pid-file=/run/inventory-dns.pid --no-resolv --no-hosts --listen-address=127.0.0.1 --bind-interfaces --address=/inventory.internal/127.0.0.1 --address=/metrics.internal/127.0.0.9";
      Restart = "on-failure";
    };
  };
  systemd.services.inventory = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "discovery-provision.service" ];
    after = [ "discovery-provision.service" ];
    serviceConfig.ExecStart = "${pkgs.python3}/bin/python -m http.server 3001 --bind 127.0.0.1 --directory /srv/inventory";
  };
  systemd.services.discovery-web = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "resolver-policy.service" "inventory-dns.service" "inventory.service" ];
    after = [ "resolver-policy.service" "inventory-dns.service" "inventory.service" ];
    serviceConfig.ExecStart = "${pkgs.python3}/bin/python ${../apps/discovery.py}";
  };
}
