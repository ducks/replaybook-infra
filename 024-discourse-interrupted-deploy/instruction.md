A routine deploy of a hosted forum completed according to the deploy command,
but staff exports accepted afterward remain pending. The public health endpoint
is green, and both application instances and the export worker appear to be
running.

Investigate this Linux host and durably finish the deployment. Preserve every
export already accepted by the service, keep both application instances in the
load-balanced topology, and ensure new exports complete normally. Use the
deployed release and migration artifacts already present on the host. The
repair must survive service restarts and a host reboot.

Do not remove an application instance, route all traffic around one instance,
delete or replace accepted exports, manually mark exports complete, edit the
application to special-case the checks, or launch unmanaged replacement
services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
