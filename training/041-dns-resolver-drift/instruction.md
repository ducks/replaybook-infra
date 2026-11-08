The inventory gateway returns HTTP 503 even though the inventory backend and local
service-discovery process are running. Investigate and restore name-based access
to the inventory service. Preserve unrelated service discovery as well.

Repair the system configuration, not the application code. Do not replace the
services, hard-code upstream IP addresses in the application, disable DNS, or
reboot the host. The repair must survive policy reapplication, service restarts
and the external verifier's host reboot.
