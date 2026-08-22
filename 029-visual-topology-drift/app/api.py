#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import psycopg
import redis


DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
PORT = int(os.environ.get("PORT", "3100"))
QUEUE = "reservations:pending"


def reservation_state(reservation_id):
    with psycopg.connect(DATABASE_URL) as database:
        row = database.execute(
            "SELECT state FROM reservations WHERE reservation_id = %s",
            (reservation_id,),
        ).fetchone()
    return None if row is None else row[0]


def enqueue(reservation_id):
    with psycopg.connect(DATABASE_URL) as database:
        row = database.execute(
            """
            INSERT INTO reservations (reservation_id, state)
            VALUES (%s, 'pending')
            ON CONFLICT (reservation_id) DO NOTHING
            RETURNING reservation_id
            """,
            (reservation_id,),
        ).fetchone()
        database.commit()
    if row is not None:
        redis.from_url(REDIS_URL, decode_responses=True).rpush(QUEUE, reservation_id)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        payload = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.respond(200, "ok")
            return
        if path.startswith("/reservations/"):
            reservation_id = unquote(path.removeprefix("/reservations/"))
            state = reservation_state(reservation_id)
            self.respond(200 if state is not None else 404, state or "missing")
            return
        self.respond(404, "not_found")

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/reservations/"):
            self.respond(404, "not_found")
            return
        reservation_id = unquote(path.removeprefix("/reservations/"))
        enqueue(reservation_id)
        self.respond(202, "accepted")

    def log_message(self, format_string, *args):
        print(f"reservation-api: {self.address_string()} {format_string % args}", flush=True)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
