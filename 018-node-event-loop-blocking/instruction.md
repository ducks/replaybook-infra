Checkout task requests are timing out whenever several customers submit them
at once. The health endpoint remains green, and the Node service appears to be
running normally between bursts.

Investigate this Linux host and repair the deployed service. Recover the
existing timed-out task IDs, preserve the Node and Nginx service topology, and
make concurrent task requests complete reliably after service restart and host
reboot.

Do not delete completion state or replace the service with a constant response.
Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
