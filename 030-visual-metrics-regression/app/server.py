#!/usr/bin/env python3
import os
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


PORT = int(os.environ.get("PORT", "3200"))
CACHE_MAX_ENTRIES = int(os.environ.get("CACHE_MAX_ENTRIES", "0"))
CACHE_ENTRY_KIB = int(os.environ.get("CACHE_ENTRY_KIB", "256"))
PRESSURE_THRESHOLD = int(os.environ.get("PRESSURE_THRESHOLD", "80"))

cache = OrderedDict()
cache_lock = threading.Lock()


def render(report_id):
    payload = (report_id.encode() + b":") * 32
    repeats = max(1, (CACHE_ENTRY_KIB * 1024) // len(payload))
    return (payload * repeats)[: CACHE_ENTRY_KIB * 1024]


def cache_report(report_id):
    with cache_lock:
        if report_id in cache:
            cache.move_to_end(report_id)
        else:
            cache[report_id] = render(report_id)
        if CACHE_MAX_ENTRIES > 0:
            while len(cache) > CACHE_MAX_ENTRIES:
                cache.popitem(last=False)


def cache_entries():
    with cache_lock:
        return len(cache)


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
            if cache_entries() > PRESSURE_THRESHOLD:
                self.respond(503, "memory_pressure")
            else:
                self.respond(200, "ok")
            return
        if path == "/status":
            self.respond(200, f"cache_entries={cache_entries()}")
            return
        self.respond(404, "not_found")

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/reports/"):
            self.respond(404, "not_found")
            return
        report_id = unquote(path.removeprefix("/reports/"))
        cache_report(report_id)
        self.respond(200, "rendered")

    def log_message(self, format_string, *args):
        print(f"metrics-api: {self.address_string()} {format_string % args}", flush=True)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
