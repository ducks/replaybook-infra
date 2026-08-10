Checkout confirmation processing became inconsistent after a routine application
rollout. Standard confirmations complete, but express confirmations remain
pending. The web health endpoint is healthy, and both background worker services
appear to be running.

Investigate this Linux host and repair the deployed service. Recover all existing
confirmation jobs, preserve both worker services and their queue capacity, and
make the repair survive service restarts and a host reboot.

Do not flush Redis, delete queued work, process jobs manually, or reboot, shut
down, or replace the host yourself. The external verifier will perform the
reboot after your session ends.
