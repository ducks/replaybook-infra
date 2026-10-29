"""Capacity reservation HTTP service."""
import http.server
import json
import logging
import os
import sqlite3
import time


def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS capacity (id INTEGER PRIMARY KEY CHECK(id=1), total INTEGER NOT NULL, available INTEGER NOT NULL)')
    db.execute('INSERT OR IGNORE INTO capacity VALUES (1, 256, 256)')
    db.execute('CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, quantity INTEGER NOT NULL, body TEXT NOT NULL)')
    db.commit()
    return db


def reserve(database, identity, payload, atomic):
    quantity = payload['quantity']
    if type(quantity) is not int or not 1 <= quantity <= 3:
        raise ValueError('quantity must be between 1 and 3')
    body = json.dumps(payload, sort_keys=True)
    with connect(database) as db:
        if atomic:
            db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT body FROM reservations WHERE id=?', (identity,)).fetchone()
        if row:
            return (201, 'reserved') if row[0] == body else (409, 'conflict')
        available = db.execute('SELECT available FROM capacity WHERE id=1').fetchone()[0]
        if available < quantity:
            return 409, 'capacity unavailable'
        if not atomic:
            time.sleep(.25)
        db.execute('INSERT INTO reservations VALUES (?, ?, ?)', (identity, quantity, body))
        db.execute('UPDATE capacity SET available=? WHERE id=1', (available - quantity,))
    return 201, 'reserved'


def server(port, database, atomic):
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
            if self.path == '/capacity':
                with connect(database) as db:
                    row = db.execute('SELECT total, available FROM capacity WHERE id=1').fetchone()
                return self.respond(200, json.dumps({'total':row[0], 'available':row[1]}))
            return self.respond(404, 'missing')

        def do_POST(self):
            if not self.path.startswith('/reservations/'):
                return self.respond(404, 'missing')
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                status, body = reserve(database, self.path.split('/')[-1], payload, atomic)
                return self.respond(status, body)
            except (ValueError, KeyError, TypeError, sqlite3.Error) as error:
                logging.warning('reservation: %s', error)
                return self.respond(503, 'request failed')

    return http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server(int(os.environ['PORT']), os.environ['DATABASE'], os.environ['ATOMIC_WRITES'] == '1').serve_forever()
