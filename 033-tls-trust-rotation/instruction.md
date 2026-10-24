Webhook delivery has stopped following internal certificate maintenance. The
public API still accepts deliveries and its health endpoint stays green, but
existing requests remain pending and downstream consumers see no receipts.

Investigate this Linux host and durably restore delivery. Preserve and complete
all already accepted work and retain existing receiver receipts. New deliveries
must also succeed. Keep certificate-chain and hostname verification enabled,
reject the retired trust chain, and preserve the deployed systemd topology.
Do not clear queues, recreate databases, replace HTTPS with HTTP, or launch
unmanaged replacement services. The repair must survive service restarts and
a host reboot.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
