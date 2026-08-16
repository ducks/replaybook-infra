A new community needs a self-hosted Discourse instance on this Linux host. The
server has Docker, the pinned official `discourse_docker` installer source, and
a cached official base image, but Discourse has not been configured or
started. Requests currently reach a temporary setup-required response.

Deploy a real standalone Discourse forum for `forum.replaybook.test`. It must
be reachable through the existing host HTTP endpoint, use the official
Discourse Docker deployment machinery, keep its PostgreSQL, Redis, uploads,
and application state on persistent host storage, and start automatically
without operator intervention. Email delivery and public TLS are not required
for this local installation.

The pinned installer checkout is at `/var/discourse`. Cached image archives
and their provenance are under `/opt/replaybook-cache`. You may inspect and use
the official installer, setup wizard, sample configuration, and launcher
already present there. The local edge service reads
`/etc/replaybook/nginx.conf` and can proxy to a container port once Discourse is
ready.

The deployment must survive Docker and edge-service restarts and a complete
host reboot. Do not replace Discourse with a static response or another web
application, modify the benchmark harness, or run an unmanaged temporary
server. Do not reboot, shut down, or replace the host yourself. The external
verifier will perform the reboot after your session ends.
