{ pkgs, ... }:
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 nginx util-linux ];
  users.users.receipt-writer = { isSystemUser = true; group = "receipts"; };
  users.groups.receipts = {};
  users.groups.receipt-readers = {};
  users.users.receipt-reader = { isSystemUser = true; group = "receipt-readers"; };
  services.nginx = { enable = true; virtualHosts.default = { default = true; locations."/reader/".proxyPass = "http://127.0.0.1:3001/"; locations."/".proxyPass = "http://127.0.0.1:3000"; }; };
  systemd.services.receipt-provision = {
    wantedBy = [ "multi-user.target" ];
    before = [ "receipt-storage-policy.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
    script = ''
      install -d -m 0755 /etc/receipts /var/lib/receipts
      install -d -m 0750 -g receipts /var/lib/receipts/incoming
      if [[ ! -e /etc/receipts/storage.env ]]; then
        printf 'STORAGE_OWNER=receipt-writer\n' > /etc/receipts/storage.env
      fi
      if [[ ! -e /etc/receipts/reader.env ]]; then
        printf 'READER_GROUP=receipt-readers\n' > /etc/receipts/reader.env
      fi
      if [[ ! -e /var/lib/receipts/incoming/historical ]]; then
        printf 'historical-ledger-entry\n' > /var/lib/receipts/incoming/historical
        chown receipt-writer:receipts /var/lib/receipts/incoming/historical
        chmod 0640 /var/lib/receipts/incoming/historical
      fi
    '';
  };
  systemd.services.receipt-storage-policy = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "receipt-provision.service" ];
    after = [ "receipt-provision.service" ];
    before = [ "receipt-web.service" ];
    path = [ pkgs.coreutils ];
    serviceConfig = { Type = "oneshot"; RemainAfterExit = true; EnvironmentFile = "/etc/receipts/storage.env"; };
    script = ''
      chown "$STORAGE_OWNER":receipts /var/lib/receipts/incoming
      chmod 0750 /var/lib/receipts/incoming
    '';
  };
  systemd.services.receipt-web = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "receipt-storage-policy.service" ];
    after = [ "receipt-storage-policy.service" ];
    serviceConfig = { User = "receipt-writer"; Group = "receipts"; UMask = "0027"; ExecStart = "${pkgs.python3}/bin/python ${../apps/shared_receipts.py}"; };
  };
  systemd.services.receipt-reader = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "receipt-storage-policy.service" ];
    after = [ "receipt-storage-policy.service" ];
    environment = { PORT = "3001"; READ_ONLY = "1"; };
    serviceConfig = { EnvironmentFile = "/etc/receipts/reader.env"; };
    script = ''
      exec ${pkgs.util-linux}/bin/setpriv --reuid=receipt-reader --regid="$READER_GROUP" --clear-groups ${pkgs.python3}/bin/python ${../apps/shared_receipts.py}
    '';
  };
}
