#!/usr/bin/env python3
import os
import time

import psycopg
import redis


DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
QUEUE = "reservations:pending"
queue = redis.from_url(REDIS_URL, decode_responses=True)

while True:
    try:
        item = queue.blpop(QUEUE, timeout=2)
        if item is None:
            continue
        _, reservation_id = item
        with psycopg.connect(DATABASE_URL) as database:
            database.execute(
                """
                UPDATE reservations
                SET state = 'completed', completed_at = now()
                WHERE reservation_id = %s
                """,
                (reservation_id,),
            )
            database.commit()
        print(f"completed {reservation_id}", flush=True)
    except Exception as error:
        print(f"worker error: {error}", flush=True)
        time.sleep(1)
