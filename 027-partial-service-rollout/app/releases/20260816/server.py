#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.environ["PORT"])
INSTANCE = os.environ["INSTANCE_NAME"]
RELEASE = "20260816"


def database():
    return psycopg.connect(DATABASE_URL, autocommit=True)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, body: str) -> None:
        payload = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def path_parts(self) -> list[str]:
        return self.path.split("?", 1)[0].strip("/").split("/")

    def do_GET(self) -> None:
        parts = self.path_parts()
        if parts == ["health"]:
            self.respond(200, "ok")
            return
        if parts == ["release"]:
            self.respond(200, RELEASE)
            return
        if parts == ["instance"]:
            self.respond(200, INSTANCE)
            return
        if parts == ["schema"]:
            self.respond(200, "legacy")
            return
        if len(parts) != 2 or parts[0] != "orders":
            self.respond(404, "missing")
            return
        with database() as connection:
            row = connection.execute(
                "SELECT payload FROM orders WHERE order_id = %s", (parts[1],)
            ).fetchone()
        if row is None:
            self.respond(404, "missing")
            return
        self.respond(200, "stored")

    def do_POST(self) -> None:
        parts = self.path_parts()
        if len(parts) != 2 or parts[0] != "orders":
            self.respond(404, "missing")
            return
        try:
            with database() as connection:
                connection.execute(
                    "INSERT INTO orders (order_id, payload) VALUES (%s, %s)",
                    (parts[1], "accepted-before-convergence"),
                )
        except psycopg.errors.UniqueViolation:
            self.respond(409, "exists")
            return
        self.respond(201, "stored")

    def log_message(self, format: str, *args: object) -> None:
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
