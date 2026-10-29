"""Notification API and transactional delivery worker."""
import http.server
import json
import logging
import os
import sqlite3
import sys
import time


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, body TEXT NOT NULL, status TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, body TEXT NOT NULL, deliveries INTEGER NOT NULL)')
    return db


def deliver_one(database, decoder):
    with connect(database) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT id, body FROM messages WHERE status='pending' ORDER BY rowid LIMIT 1").fetchone()
        if not row:
            return False
        identity, body = row
        payload = json.loads(body)
        destination = payload['recipient' if decoder == 1 else 'destination']
        if not isinstance(destination, str) or not destination:
            raise ValueError('destination is required')
        db.execute('INSERT OR IGNORE INTO receipts VALUES (?, ?, 1)', (identity, body))
        db.execute("UPDATE messages SET status='sent' WHERE id=?", (identity,))
    return True


def worker(database, decoder, stop=None):
    while stop is None or not stop.is_set():
        try:
            if deliver_one(database, decoder):
                continue
        except (KeyError, ValueError, sqlite3.Error) as error:
            logging.warning('delivery processing: %s', error)
        time.sleep(.2)


def server(port, database):
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
            if self.path.startswith('/messages/'):
                with connect(database) as db:
                    row = db.execute('SELECT status FROM messages WHERE id=?', (self.path.split('/')[-1],)).fetchone()
                return self.respond(200, row[0]) if row else self.respond(404, 'missing')
            return self.respond(404, 'missing')

        def do_POST(self):
            archive = self.path.startswith('/imports/')
            if not archive and not self.path.startswith('/messages/'):
                return self.respond(404, 'missing')
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                if not isinstance(payload, dict) or not isinstance(payload.get('destination'), str):
                    raise ValueError('destination is required')
                body = json.dumps(payload, sort_keys=True)
                identity = self.path.split('/')[-1]
                with connect(database) as db:
                    old = db.execute('SELECT body FROM messages WHERE id=?', (identity,)).fetchone()
                    if old and old[0] != body:
                        return self.respond(409, 'conflict')
                    db.execute('INSERT OR IGNORE INTO messages VALUES (?, ?, ?)', (identity, body, 'sent' if archive else 'pending'))
                    if archive:
                        db.execute('INSERT OR IGNORE INTO receipts VALUES (?, ?, 1)', (identity, body))
                return self.respond(202, 'accepted')
            except (ValueError, sqlite3.Error) as error:
                logging.warning('submission: %s', error)
                return self.respond(400, 'request failed')

    return http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if sys.argv[1] == 'worker':
        worker(os.environ['DATABASE'], int(os.environ['DECODER']))
    else:
        server(int(os.environ['PORT']), os.environ['DATABASE']).serve_forever()
