#!/usr/bin/env python3
import hashlib
import os
import shutil
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


STATE_DIR = Path(os.environ.get("STATE_DIR", "/var/lib/billing-ledger"))
DATABASE = STATE_DIR / "receipts.sqlite3"
ARCHIVE = STATE_DIR / "protected" / "accounting.archive"
ARCHIVE_HASH = STATE_DIR / "protected" / "accounting.archive.sha256"
MIN_FREE_BYTES = int(os.environ.get("MIN_FREE_BYTES", str(768 * 1024 * 1024)))
CACHE_CONFIG = Path("/etc/replaybook/cache-warmup.env")
WARMUP_COMPLETE = Path("/run/nix-cache-warmup-complete")


def free_bytes():
    return shutil.disk_usage(STATE_DIR).free


def archive_intact():
    try:
        expected = ARCHIVE_HASH.read_text().strip()
        digest = hashlib.sha256()
        with ARCHIVE.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected
    except OSError:
        return False


def warmup_in_progress():
    try:
        enabled = "CACHE_WARMUP=enabled" in CACHE_CONFIG.read_text().splitlines()
    except OSError:
        enabled = True
    return enabled and not WARMUP_COMPLETE.exists()


def receipt_exists(receipt_id):
    with sqlite3.connect(DATABASE) as database:
        row = database.execute(
            "SELECT 1 FROM receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()
    return row is not None


def store_receipt(receipt_id):
    with sqlite3.connect(DATABASE) as database:
        database.execute(
            "INSERT OR IGNORE INTO receipts (receipt_id, created_at) VALUES (?, datetime('now'))",
            (receipt_id,),
        )
        database.commit()


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
            if warmup_in_progress():
                self.respond(503, "warming_cache")
            elif not archive_intact():
                self.respond(503, "archive_corrupt")
            elif free_bytes() < MIN_FREE_BYTES:
                self.respond(507, "low_disk")
            else:
                self.respond(200, "ok")
            return
        if path == "/archive":
            self.respond(200 if archive_intact() else 503, "intact" if archive_intact() else "corrupt")
            return
        if path.startswith("/receipts/"):
            receipt_id = unquote(path.removeprefix("/receipts/"))
            self.respond(200 if receipt_exists(receipt_id) else 404, "stored" if receipt_exists(receipt_id) else "missing")
            return
        self.respond(404, "not_found")

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/receipts/"):
            self.respond(404, "not_found")
            return
        if not archive_intact():
            self.respond(503, "archive_corrupt")
            return
        if free_bytes() < MIN_FREE_BYTES:
            self.respond(507, "low_disk")
            return
        receipt_id = unquote(path.removeprefix("/receipts/"))
        try:
            store_receipt(receipt_id)
        except (OSError, sqlite3.Error):
            self.respond(507, "write_failed")
            return
        self.respond(201, "stored")

    def log_message(self, format_string, *args):
        print(f"ledger: {self.address_string()} {format_string % args}", flush=True)


ThreadingHTTPServer(("127.0.0.1", 3000), Handler).serve_forever()
