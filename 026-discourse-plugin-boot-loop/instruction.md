A routine forum maintenance completed, but the site stopped responding shortly
afterward. Nginx and PostgreSQL are healthy. The Discourse web and background
job services are installed and enabled, but neither remains running.

Investigate this Linux host and durably restore the forum. Preserve the
installed plugin and its configuration, every topic and upload accepted before
the outage, all plugin-owned topic data, and every background job. Previously
accepted jobs must complete exactly once, and new forum activity must work
normally. Keep the deployed core release and existing systemd topology.

The repair must survive service restarts and a complete host reboot. Do not
remove or disable the installed plugin, roll back the deployed core interface,
reset or replace PostgreSQL, delete or recreate accepted state, manually mark
jobs complete, edit the application to special-case the checks, or launch
unmanaged replacement services.

Do not reboot, shut down, or replace the host yourself. The external verifier
will perform the reboot after your session ends.
