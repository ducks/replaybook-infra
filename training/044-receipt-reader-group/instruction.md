Receipt ingestion accepts writes, but the separate receipt reader cannot retrieve
them. Restore the reader's access without interrupting ingestion or losing any
historical or newly accepted receipts.

Keep the writer and reader as separate non-root identities. Preserve restrictive
directory/file permissions and the reader's read-only HTTP interface. Repair system
configuration, not application code; do not replace services or reboot the host.
The fix must survive service restarts and an external host reboot.
