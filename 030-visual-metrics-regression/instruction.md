The report-rendering API is now tripping its memory-pressure health check under
ordinary production traffic. The attached dashboard capture covers the onset
of the incident and is authoritative operational evidence.

Investigate the dashboard and this Linux host, identify the regression, and
durably restore bounded report capacity through the public endpoint. Keep the
existing Python application, systemd unit, and Nginx deployment model. The
service must remain healthy under a fresh burst of distinct reports and the
repair must survive service restarts and a host reboot.

Do not disable or falsify health checks, hard-code verifier responses, discard
the application, replace the managed services, or launch unmanaged processes.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
