"""Checkout HTTP service and persistent invoice ledger."""
import http.server
import json
import logging
import os
import sqlite3
import sys
import urllib.error
import urllib.request


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS invoices (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    return db


def server(role, port, database, upstream=None):
    with connect(database):
        pass

    class Handler(http.server.BaseHTTPRequestHandler):
        def respond(self, status, body):
            data = body.encode()
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/health':
                return self.respond(200, 'ok')
            if role == 'ledger' and self.path.startswith('/invoices/'):
                with connect(database) as db:
                    row = db.execute('SELECT body FROM invoices WHERE id=?', (self.path.split('/')[-1],)).fetchone()
                return self.respond(200, row[0]) if row else self.respond(404, 'missing')
            return self.respond(404, 'missing')

        def do_POST(self):
            prefix = '/invoices/' if role == 'ledger' else '/orders/'
            if not self.path.startswith(prefix):
                return self.respond(404, 'missing')
            identity = self.path.split('/')[-1]
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            try:
                document = json.loads(body)
                if not isinstance(document, dict) or not document:
                    raise ValueError('an object is required')
                if role == 'api':
                    request = urllib.request.Request(upstream + '/invoices/' + identity, data=body, method='POST')
                    with urllib.request.urlopen(request, timeout=3) as response:
                        response.read()
                    return self.respond(201, 'created')
                canonical = json.dumps(document, sort_keys=True)
                with connect(database) as db:
                    existing = db.execute('SELECT body FROM invoices WHERE id=?', (identity,)).fetchone()
                    if existing and existing[0] != canonical:
                        return self.respond(409, 'conflict')
                    db.execute('INSERT OR IGNORE INTO invoices VALUES (?, ?)', (identity, canonical))
                return self.respond(201, 'created')
            except (ValueError, urllib.error.URLError, TimeoutError) as error:
                logging.warning('invoice request %s: %s', identity, error)
                return self.respond(502 if role == 'api' else 400, 'request failed')

    return http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    role = sys.argv[1]
    server(role, int(os.environ['PORT']), os.environ['DATABASE'], os.environ.get('LEDGER_URL')).serve_forever()
