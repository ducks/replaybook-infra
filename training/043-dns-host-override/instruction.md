The inventory gateway returns HTTP 503. The backend is healthy and direct queries
to the local DNS server appear correct. Restore normal name-based access while
preserving unrelated service discovery.

Repair system configuration, not application code. Do not replace services,
hard-code upstream addresses, disable DNS, or reboot the host. The repair must
survive policy reapplication, service restarts and an external host reboot.
