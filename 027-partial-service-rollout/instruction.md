Order creation became intermittent during a routine application deployment.
Some requests succeed while others return HTTP 503, even though both application
instances are running and their health checks remain green.

Investigate this Linux host and durably complete the deployment. Preserve every
order accepted before your session began, converge both application instances
on the deployed release, and restore reliable order creation through the public
load-balanced endpoint. The repair must preserve the existing PostgreSQL,
systemd, and Nginx topology and survive service restarts and a host reboot.

Do not remove a backend from load balancing, reduce the deployment to one
instance, delete or recreate the order database, discard existing orders,
return hard-coded responses, bypass PostgreSQL, or launch unmanaged replacement
services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
