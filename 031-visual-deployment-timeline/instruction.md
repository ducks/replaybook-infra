A checkout deployment was automatically rolled back after one application
instance failed to start. Checkout writes now fail even though the public
health endpoint is green. The attached deployment-timeline capture is
authoritative operational evidence from the release controller.

Investigate the timeline and this Linux host, then durably finish the intended
deployment using the release artifacts already present. Preserve both
load-balanced application instances, the background worker, every order already
accepted by the service, and the existing receipt archive. New orders must be
accepted and completed normally. The repair must survive service restarts and a
host reboot.

Do not reverse or falsify the recorded schema state, delete or replace existing
orders or receipts, remove an application instance, route around a broken
instance, hard-code verifier responses, or launch unmanaged replacement
services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
