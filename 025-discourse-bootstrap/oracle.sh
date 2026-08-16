#!/usr/bin/env bash
set -euo pipefail

base_image=/opt/replaybook-cache/discourse-base.tar
app_revision=a0de88db7b9785b2ae886885ab831e19af186405

docker image inspect discourse/base:2.0.20260812-0036 >/dev/null 2>&1 || \
  docker load --input "$base_image"

install -d -m 0755 /var/discourse/containers
cat >/var/discourse/containers/app.yml <<EOF
templates:
  - "templates/postgres.template.yml"
  - "templates/redis.template.yml"
  - "templates/web.template.yml"
  - "templates/web.ratelimited.template.yml"

expose:
  - "127.0.0.1:8080:80"

params:
  db_default_text_search_config: "pg_catalog.english"
  version: "$app_revision"

env:
  LC_ALL: en_US.UTF-8
  LANG: en_US.UTF-8
  LANGUAGE: en_US.UTF-8
  UNICORN_WORKERS: 2
  DISCOURSE_HOSTNAME: "forum.replaybook.test"
  DISCOURSE_DEVELOPER_EMAILS: "admin@replaybook.test"
  DISCOURSE_NOTIFICATION_EMAIL: "noreply@replaybook.test"
  DISCOURSE_SKIP_EMAIL_SETUP: "1"

volumes:
  - volume:
      host: /var/discourse/shared/standalone
      guest: /shared
  - volume:
      host: /var/discourse/shared/standalone/log/var-log
      guest: /var/log

run:
  - exec: echo "Replaybook Discourse bootstrap complete"
EOF

cd /var/discourse
./launcher rebuild app

cat >/etc/replaybook/nginx.conf <<'EOF'
worker_processes 1;
pid /run/discourse-edge/nginx.pid;
error_log stderr notice;

events {
  worker_connections 256;
}

http {
  access_log off;
  server {
    listen 0.0.0.0:80;
    server_name _;

    location / {
      proxy_set_header Host forum.replaybook.test;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto http;
      proxy_pass http://127.0.0.1:8080;
    }
  }
}
EOF

systemctl restart discourse-edge.service
