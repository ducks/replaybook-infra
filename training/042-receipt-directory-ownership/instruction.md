The receipt service is healthy and existing receipts are readable, but new receipt
writes return HTTP 503 after a storage maintenance change. Diagnose and restore
durable writes without losing existing records.

Preserve the receipt-writer service identity and restrictive directory permissions.
Do not run the application as root, make storage world-writable, replace the
application code, or clear the ledger. The repair must survive storage-policy
reapplication, service restarts and the external verifier's reboot. Do not reboot
the host yourself.
