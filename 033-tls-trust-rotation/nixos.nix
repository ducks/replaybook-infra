{ pkgs, ... }:

let
  appDir = ./app;
in
{
  imports = [ ../worker/base.nix ];
  environment.systemPackages = with pkgs; [ python3 openssl sqlite nginx ];
  networking.extraHosts = "127.0.0.1 receiver.internal";

  users.groups.dispatch = { };
  users.users.dispatch = { isSystemUser = true; group = "dispatch"; };
  users.groups.receiver = { };
  users.users.receiver = { isSystemUser = true; group = "receiver"; };

  services.nginx = {
    enable = true;
    virtualHosts.default = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:3000";
      locations."/receipts/".proxyPass = "http://127.0.0.1:3001";
    };
  };

  systemd.services.incident-provision = {
    description = "Provision delivery services";
    wantedBy = [ "multi-user.target" ];
    before = [ "delivery-dispatch.service" "delivery-receiver.service" ];
    path = [ pkgs.coreutils pkgs.openssl ];
    serviceConfig.Type = "oneshot";
    script = ''
      install -d -m 0755 /etc/dispatch /etc/delivery/pki /var/lib/delivery/current
      install -d -m 0750 -o dispatch -g dispatch /var/lib/dispatch
      install -d -m 0750 -o receiver -g receiver /var/lib/receiver
      if [[ ! -e /var/lib/delivery/current/service.py ]]; then
        install -m 0755 ${appDir}/service.py /var/lib/delivery/current/service.py
      fi
      if [[ ! -e /etc/delivery/pki/receiver.pem ]]; then
        cd /etc/delivery/pki
        for ca in platform archive-root; do
          openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
            -keyout "$ca.key" -out "$ca.pem" -subj "/CN=$ca" \
            -addext 'basicConstraints=critical,CA:TRUE' \
            -addext 'keyUsage=critical,keyCertSign,cRLSign'
        done
        for name in receiver archive directory; do
          ca=platform
          dns=receiver.internal
          if [[ "$name" == archive ]]; then ca=archive-root; fi
          if [[ "$name" == directory ]]; then dns=directory.internal; fi
          openssl req -new -newkey rsa:2048 -nodes -keyout "$name.key" \
            -out "$name.csr" -subj "/CN=$dns"
          printf '%s\n' "subjectAltName=DNS:$dns" 'extendedKeyUsage=serverAuth' \
            'basicConstraints=CA:FALSE' > "$name.ext"
          openssl x509 -req -in "$name.csr" -CA "$ca.pem" -CAkey "$ca.key" \
            -CAcreateserial -days 3650 -extfile "$name.ext" -out "$name.pem"
        done
        rm -f ./*.csr ./*.ext ./*.srl ./platform.key ./archive-root.key
        chmod 0644 ./*.pem
        chown receiver:receiver ./receiver.key ./archive.key ./directory.key
        chmod 0600 ./*.key
      fi
      if [[ ! -e /etc/dispatch/ca-bundle.pem ]]; then
        install -m 0644 /etc/delivery/pki/archive-root.pem /etc/dispatch/ca-bundle.pem
      fi
      if [[ ! -e /etc/dispatch/dispatch.env ]]; then
        printf '%s\n' 'STATE_DIR=/var/lib/dispatch' \
          'CA_BUNDLE=/etc/dispatch/ca-bundle.pem' \
          'RECEIVER_HOST=receiver.internal' > /etc/dispatch/dispatch.env
      fi
    '';
  };

  systemd.services.delivery-receiver = {
    description = "Internal receipt endpoints";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" ];
    requires = [ "incident-provision.service" ];
    environment = { STATE_DIR = "/var/lib/receiver"; PKI_DIR = "/etc/delivery/pki"; };
    serviceConfig = {
      User = "receiver";
      Group = "receiver";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/delivery/current/service.py receiver";
      Restart = "always";
      RestartSec = 1;
    };
  };
  systemd.services.delivery-dispatch = {
    description = "Webhook dispatcher";
    wantedBy = [ "multi-user.target" ];
    after = [ "incident-provision.service" "delivery-receiver.service" ];
    requires = [ "incident-provision.service" "delivery-receiver.service" ];
    serviceConfig = {
      User = "dispatch";
      Group = "dispatch";
      EnvironmentFile = "/etc/dispatch/dispatch.env";
      ExecStart = "${pkgs.python3}/bin/python /var/lib/delivery/current/service.py dispatch";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
