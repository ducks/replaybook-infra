import sqlite3
import time


DATABASE = "/var/lib/export-service/exports.db"


def initialize() -> None:
    with sqlite3.connect(DATABASE) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS completed_exports "
            "(export_id TEXT PRIMARY KEY, completed_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )


initialize()


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET" and path == "/health":
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    if method == "POST" and path.startswith("/exports/"):
        export_id = path.removeprefix("/exports/")
        time.sleep(3)
        with sqlite3.connect(DATABASE) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO completed_exports (export_id) VALUES (?)",
                (export_id,),
            )
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"completed"]

    if method == "GET" and path.startswith("/exports/"):
        export_id = path.removeprefix("/exports/")
        with sqlite3.connect(DATABASE) as connection:
            row = connection.execute(
                "SELECT 1 FROM completed_exports WHERE export_id = ?", (export_id,)
            ).fetchone()
        if row:
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"completed"]
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"pending"]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"missing"]
