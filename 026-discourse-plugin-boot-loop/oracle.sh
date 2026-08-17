#!/usr/bin/env bash
set -euo pipefail

sed -i \
  's/supported_plugin_api_versions = \[1\]/supported_plugin_api_versions = [1, 2]/' \
  /var/lib/discourse/plugins/discourse-presence/initializer.rb

systemctl restart discourse-web.service discourse-sidekiq.service
