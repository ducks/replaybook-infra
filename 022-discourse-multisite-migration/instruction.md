The default hosted forum is healthy after a routine deploy, but users from
another hosted community report that moderation work remains pending. The web
service and background worker are both running, and the global health endpoint
is green.

Investigate this Linux host and durably repair the multisite deployment.
Preserve the existing work for every site and keep each site connected to its
own database. The repair must use the deployed application state, preserve the
current systemd topology, and survive service restarts and a host reboot.

Do not merge the sites, route both site names to one database, delete queued
work, manually mark jobs complete, edit the application to special-case the
checks, or launch unmanaged replacement services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
