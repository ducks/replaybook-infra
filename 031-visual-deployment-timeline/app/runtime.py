#!/usr/bin/env python3
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


DB_PATH = os.environ.get("DB_PATH", "/var/lib/checkout/state/checkout.db")


def connect():
    database = sqlite3.connect(DB_PATH, timeout=10)
    database.execute("PRAGMA busy_timeout=10000")
    return database


def schema_version():
    with connect() as database:
        row = database.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
    return row[0] if row else "unknown"


def serve(release):
    port = int(os.environ["PORT"])

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
            if path == "/release":
                self.respond(200, release)
                return
            if path == "/schema":
                self.respond(200, schema_version())
                return
            if path.startswith("/orders/"):
                order_id = unquote(path.removeprefix("/orders/"))
                with connect() as database:
                    row = database.execute(
                        "SELECT state, completed_release FROM orders WHERE order_id = ?",
                        (order_id,),
                    ).fetchone()
                if row is None:
                    self.respond(404, "not_found")
                elif row[0] == "pending":
                    self.respond(409, "pending")
                else:
                    self.respond(200, f"completed:{row[1]}")
                return
            if path.startswith("/receipts/"):
                receipt_id = unquote(path.removeprefix("/receipts/"))
                with connect() as database:
                    row = database.execute(
                        "SELECT payload FROM receipts WHERE receipt_id = ?",
                        (receipt_id,),
                    ).fetchone()
                if row is None:
                    self.respond(404, "not_found")
                else:
                    self.respond(200, row[0])
                return
            self.respond(404, "not_found")

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.startswith("/orders/"):
                self.respond(404, "not_found")
                return
            if release != "42" or schema_version() != "42":
                self.respond(503, "schema_mismatch")
                return
            order_id = unquote(path.removeprefix("/orders/"))
            with connect() as database:
                database.execute(
                    "INSERT OR IGNORE INTO orders VALUES (?, 'pending', NULL)",
                    (order_id,),
                )
                database.commit()
            self.respond(202, "accepted")

        def log_message(self, format_string, *args):
            print(
                f"checkout-{release}: {self.address_string()} "
                f"{format_string % args}",
                flush=True,
            )

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def work(release):
    while True:
        if release == "42" and schema_version() == "42":
            try:
                with connect() as database:
                    database.execute("BEGIN IMMEDIATE")
                    row = database.execute(
                        "SELECT order_id FROM orders WHERE state = 'pending' "
                        "ORDER BY rowid LIMIT 1"
                    ).fetchone()
                    if row is not None:
                        database.execute(
                            "UPDATE orders SET state = 'completed', "
                            "completed_release = ? WHERE order_id = ?",
                            (release, row[0]),
                        )
                    database.commit()
            except sqlite3.OperationalError:
                pass
        time.sleep(0.2)
