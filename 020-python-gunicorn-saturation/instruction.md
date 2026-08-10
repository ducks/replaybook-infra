The export API remains healthy at idle, but export requests fail under normal
concurrent use. Gunicorn repeatedly replaces workers while customers receive
errors and their exports remain incomplete.

Investigate this Linux host and repair the deployed service. Recover the exact
existing export requests, preserve the Gunicorn and Nginx service topology, and
make concurrent exports complete after service restart and host reboot.

Do not delete the export database, bypass the export work, or launch unmanaged
workers. Do not reboot, shut down, or replace the host yourself. The external
verifier will perform the reboot after your session ends.
