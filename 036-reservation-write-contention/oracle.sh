#!/usr/bin/env bash
set -euo pipefail
sed -i 's/ATOMIC_WRITES=0/ATOMIC_WRITES=1/' /etc/reservation/reservation-api.env
systemctl stop reservation-api.service
sqlite3 /var/lib/reservation/reservations.sqlite3 'BEGIN IMMEDIATE; UPDATE capacity SET available=total-(SELECT COALESCE(SUM(quantity),0) FROM reservations) WHERE id=1; COMMIT;'
systemctl start reservation-api.service
