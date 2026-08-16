{ lib, pkgs, ... }:

let
  discourseDockerRevision = "9c35fe8f6f4eb66d399f756e3bae773292e34db2";
  discourseDocker = pkgs.fetchFromGitHub {
    owner = "discourse";
    repo = "discourse_docker";
    rev = discourseDockerRevision;
    hash = "sha256-xARXE6vWDbl4ed8sdGNVbm/fN+ENG9/7Sr78WCYElgc=";
  };
  discourseBaseImage = pkgs.dockerTools.pullImage {
    imageName = "discourse/base";
    imageDigest = "sha256:837e8ed4b5916baa36856b842ad84fe262b6b1b5550701f8844b13cc7acad7a5";
    sha256 = "sha256-0MsFpIziudJKI7rzwTrPfTvCSgwxBLpyTO3Xk54TsIQ=";
    finalImageName = "discourse/base";
    finalImageTag = "2.0.20260812-0036";
  };
in
{
  imports = [ ../worker/base.nix ];

  virtualisation = {
    cores = lib.mkForce 4;
    memorySize = lib.mkForce 4096;
    diskSize = lib.mkForce 32768;
    docker.enable = true;
  };

  networking.hosts."127.0.0.1" = [ "forum.replaybook.test" ];
  boot.kernel.sysctl."vm.overcommit_memory" = 1;

  environment.systemPackages = with pkgs; [ docker git nginx ];

  systemd.tmpfiles.rules = [
    "d /opt/replaybook-cache 0755 root root -"
    "L+ /opt/replaybook-cache/discourse-base.tar - - - - ${discourseBaseImage}"
    "L+ /opt/replaybook-cache/discourse-docker-source - - - - ${discourseDocker}"
  ];

  systemd.services.incident-provision = {
    description = "Stage the pinned official Discourse installer";
    wantedBy = [ "multi-user.target" ];
    after = [ "docker.service" ];
    requires = [ "docker.service" ];
    before = [ "discourse-edge.service" ];
    serviceConfig.Type = "oneshot";
    serviceConfig.RemainAfterExit = true;
    path = [ pkgs.coreutils pkgs.git ];
    script = ''
      install -d -m 0755 /etc/replaybook /var/lib/replaybook

      if [[ ! -d /var/lib/replaybook/discourse-docker-origin/.git ]]; then
        install -d -m 0755 /var/lib/replaybook/discourse-docker-origin
        cp -R ${discourseDocker}/. /var/lib/replaybook/discourse-docker-origin/
        chmod -R u+w /var/lib/replaybook/discourse-docker-origin
        git -C /var/lib/replaybook/discourse-docker-origin init --initial-branch=main
        git -C /var/lib/replaybook/discourse-docker-origin config user.name Replaybook
        git -C /var/lib/replaybook/discourse-docker-origin config user.email replaybook@localhost
        git -C /var/lib/replaybook/discourse-docker-origin add .
        GIT_AUTHOR_DATE=2026-08-15T00:00:00Z \
          GIT_COMMITTER_DATE=2026-08-15T00:00:00Z \
          git -C /var/lib/replaybook/discourse-docker-origin commit \
            -m "Pinned discourse_docker ${discourseDockerRevision}"
      fi

      if [[ ! -d /var/discourse/.git ]]; then
        rm -rf /var/discourse
        git clone /var/lib/replaybook/discourse-docker-origin /var/discourse
      fi
      install -d -m 0755 /var/discourse/cids /var/discourse/containers

      if [[ ! -e /etc/replaybook/nginx.conf ]]; then
        cat >/etc/replaybook/nginx.conf <<'EOF'
      worker_processes 1;
      pid /run/discourse-edge/nginx.pid;
      error_log stderr notice;

      events {
        worker_connections 128;
      }

      http {
        access_log off;
        server {
          listen 0.0.0.0:80;
          server_name _;
          location / {
            default_type text/plain;
            return 503 "setup-required";
          }
        }
      }
      EOF
      fi

      cat >/opt/replaybook-cache/PROVENANCE <<'EOF'
      discourse_docker revision: ${discourseDockerRevision}
      discourse/base tag: 2.0.20260812-0036
      Discourse application revision: a0de88db7b9785b2ae886885ab831e19af186405
      EOF
    '';
  };

  systemd.services.discourse-edge = {
    description = "Local edge for the Discourse deployment";
    wantedBy = [ "multi-user.target" ];
    requires = [ "incident-provision.service" ];
    after = [ "incident-provision.service" "network.target" ];
    serviceConfig = {
      RuntimeDirectory = "discourse-edge";
      ExecStartPre = "${pkgs.nginx}/bin/nginx -t -c /etc/replaybook/nginx.conf";
      ExecStart = "${pkgs.nginx}/bin/nginx -c /etc/replaybook/nginx.conf -g 'daemon off;'";
      ExecReload = "${pkgs.nginx}/bin/nginx -s reload -c /etc/replaybook/nginx.conf";
      Restart = "always";
      RestartSec = 1;
    };
  };
}
