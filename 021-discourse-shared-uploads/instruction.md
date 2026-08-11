The forum is healthy, but uploaded files became unreliable after a routine
application deploy. Older profile images return 404, while newly accepted
uploads disappear when the Discourse web service restarts.

Investigate this Linux host and repair the deployed service. Recover the exact
existing uploads, preserve the Discourse, Nginx, and shared-storage topology,
and make old and new uploads survive service restarts and a host reboot.

Do not delete or replace existing uploads, embed special cases in the web
application, or launch an unmanaged web service.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
