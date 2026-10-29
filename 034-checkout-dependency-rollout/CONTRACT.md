# Checkout dependency rollout — incident contract

Symptom: order creation returns 502 after a deployment while health endpoints are green.
Cause: a partially applied release left both edge and application upstream configuration on their previous ports.
Durable repair: converge the deployed edge and application configuration to the running service topology.
State: preserve exact pre-existing invoice IDs and JSON bodies recorded by the controller.
Success: fresh, unpredictable order bodies arrive unchanged in the ledger, historical invoices survive, and required services stay active through restart and reboot.
Negative controls: fixing only the edge or only the application fails; constant success pages, deleting invoices, and replacing the ledger database fail.

Controller hooks and this document are never installed in the guest.
