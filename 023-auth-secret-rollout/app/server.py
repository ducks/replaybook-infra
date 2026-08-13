#!/usr/bin/env python3
import hashlib
import hmac
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DATABASE = os.environ["SESSION_DATABASE"]
INSTANCE = os.environ["INSTANCE_NAME"]
RELEASE = os.environ["RELEASE_VERSION"]
SECRET = os.environ["SESSION_SECRET"].encode()


def signature(session_id: str) -> str:
    return hmac.new(SECRET, session_id.encode(), hashlib.sha256).hexdigest()


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, body: str) -> None:
        payload = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def route(self) -> tuple[str, str] | None:
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) < 2 or parts[0] != INSTANCE:
            return None
        return parts[1], "/".join(parts[2:])

    def do_GET(self) -> None:
        route = self.route()
        if route is None:
            self.respond(404, "missing")
            return
        resource, value = route
        if resource == "health" and not value:
            self.respond(200, "ok")
            return
        if resource == "release" and not value:
            self.respond(200, RELEASE)
            return
        if resource != "sessions" or not value:
            self.respond(404, "missing")
            return
        with database() as connection:
            row = connection.execute(
                "SELECT signature, revoked FROM sessions WHERE session_id = ?",
                (value,),
            ).fetchone()
        if row is None or row[1] or not hmac.compare_digest(row[0], signature(value)):
            self.respond(401, "unauthorized")
            return
        self.respond(200, "authenticated")

    def do_POST(self) -> None:
        route = self.route()
        if route is None or route[0] != "sessions" or not route[1]:
            self.respond(404, "missing")
            return
        session_id = route[1]
        try:
            with database() as connection:
                connection.execute(
                    "INSERT INTO sessions (session_id, signature, revoked) VALUES (?, ?, 0)",
                    (session_id, signature(session_id)),
                )
        except sqlite3.IntegrityError:
            self.respond(409, "exists")
            return
        self.respond(201, "created")

    def log_message(self, format: str, *args: object) -> None:
        return


ThreadingHTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
