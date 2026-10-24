#!/usr/bin/env python3
"""Small persistent webhook dispatcher and HTTPS receipt service."""
from contextlib import contextmanager
import hashlib
import http.server
import json
import logging
import os
from pathlib import Path
import sqlite3
import ssl
import sys
import threading
import urllib.error
import urllib.request


def payload(identifier):
    return hashlib.sha256(('delivery:' + identifier).encode()).hexdigest()


@contextmanager
def database(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, digest TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0)')
    connection.commit()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def transport_context():
    return ssl.create_default_context(cafile=os.environ['CA_BUNDLE'])


def send(port, path, body=None):
    url = f'https://{os.environ.get("RECEIVER_HOST", "receiver.internal")}:{port}{path}'
    request = urllib.request.Request(url, data=body, method='POST' if body is not None else 'GET')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=transport_context()))
    with opener.open(request, timeout=2) as response:
        return response.status, response.read().decode()


def security_status():
    for port in (4444, 4445):
        try:
            send(port, '/health')
        except urllib.error.URLError as error:
            # A closed port or generic network failure is not evidence that
            # certificate validation rejected the peer.
            if isinstance(error.reason, ssl.SSLCertVerificationError):
                continue
            return False
        except (OSError, ssl.SSLError):
            return False
        return False
    return True


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logging.info(fmt, *args)

    def reply(self, status, body):
        encoded = body.encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == '/health':
            return self.reply(200, 'ok')
        if self.server.role == 'dispatch' and self.path == '/transport/security':
            good = security_status()
            return self.reply(200 if good else 503, 'verified' if good else 'unverified')
        prefix = '/deliveries/' if self.server.role == 'dispatch' else '/receipts/'
        if self.path.startswith(prefix):
            identifier = self.path[len(prefix):]
            with database(self.server.database) as db:
                row = db.execute('SELECT digest, delivered FROM deliveries WHERE id=?', (identifier,)).fetchone()
            if row is None:
                return self.reply(404, 'missing')
            if row[0] != payload(identifier):
                return self.reply(409, 'conflict')
            return self.reply(200, 'delivered' if row[1] else 'pending')
        return self.reply(404, 'missing')

    def do_POST(self):
        if self.server.role == 'observer':
            return self.reply(405, 'read_only')
        prefix = '/deliveries/' if self.server.role == 'dispatch' else '/receipts/'
        if not self.path.startswith(prefix):
            return self.reply(404, 'missing')
        identifier = self.path[len(prefix):]
        if not identifier or len(identifier) > 200 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in identifier):
            return self.reply(400, 'invalid')
        digest = payload(identifier)
        if self.server.role != 'dispatch':
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            try:
                if json.loads(raw)['digest'] != digest:
                    return self.reply(409, 'conflict')
            except (ValueError, KeyError, TypeError):
                return self.reply(400, 'invalid')
        with database(self.server.database) as db:
            db.execute('INSERT OR IGNORE INTO deliveries (id,digest,delivered) VALUES (?,?,?)',
                       (identifier, digest, int(self.server.role != 'dispatch')))
        return self.reply(202 if self.server.role == 'dispatch' else 201, 'accepted' if self.server.role == 'dispatch' else 'stored')


def worker(path, stop):
    while not stop.wait(0.5):
        try:
            with database(path) as db:
                rows = db.execute('SELECT id,digest FROM deliveries WHERE delivered=0 ORDER BY rowid LIMIT 32').fetchall()
            for identifier, digest in rows:
                try:
                    status, body = send(4443, '/receipts/' + identifier, json.dumps({'digest': digest}).encode())
                    if status == 201 and body == 'stored':
                        with database(path) as db:
                            db.execute('UPDATE deliveries SET delivered=1 WHERE id=? AND digest=?', (identifier, digest))
                except (OSError, urllib.error.URLError, ssl.SSLError) as error:
                    logging.warning('delivery %s: %s', identifier, error)
        except sqlite3.Error:
            logging.exception('dispatch storage')


def server(role, port, path, certificate=None, key=None):
    with database(path):
        pass
    instance = http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler)
    instance.role = role
    instance.database = path
    if certificate:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        instance.socket = context.wrap_socket(instance.socket, server_side=True)
    return instance


def main():
    logging.basicConfig(level=logging.INFO)
    state = Path(os.environ['STATE_DIR'])
    state.mkdir(parents=True, exist_ok=True)
    role = sys.argv[1]
    if role == 'dispatch':
        instance = server(role, 3000, str(state / 'dispatch.sqlite3'))
        threading.Thread(target=worker, args=(instance.database, threading.Event()), daemon=True).start()
        instance.serve_forever()
    else:
        pki = Path(os.environ['PKI_DIR'])
        for port, name in ((4443, 'receiver'), (4444, 'archive'), (4445, 'directory')):
            instance = server('receiver', port, str(state / 'receipts.sqlite3'), str(pki / (name + '.pem')), str(pki / (name + '.key')))
            threading.Thread(target=instance.serve_forever, daemon=True).start()
        # HTTP is a read boundary for independent receipt inspection, not an
        # alternate delivery endpoint.
        instance = server('observer', 3001, str(state / 'receipts.sqlite3'))
        instance.serve_forever()


if __name__ == '__main__':
    main()
