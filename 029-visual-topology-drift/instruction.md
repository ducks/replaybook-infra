Reservation requests are being accepted but remain pending, and the public
health endpoint is returning HTTP 502. The attached production topology diagram
is the authoritative record of the intended service relationships.

Investigate this Linux host and durably restore the depicted topology. Preserve
every reservation accepted before your session began, restore processing of new
reservations through the public endpoint, and keep PostgreSQL, Redis, systemd,
and Nginx as the managed production components. The repair must survive service
restarts and a host reboot.

Do not delete or recreate the reservation database, flush Redis, discard queued
reservations, hard-code verifier responses, replace the depicted components, or
launch unmanaged services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
