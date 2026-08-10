The document processing API starts healthy after a restart but degrades during
sustained traffic. Requests eventually return resource-pressure errors even
though the Rust service remains active.

Investigate this Linux host and repair the deployed service. Preserve the Rust
service, Nginx topology, and existing systemd resource limits, and make
sustained processing remain healthy after service restart and host reboot.

Do not replace the application with a constant response.
Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
