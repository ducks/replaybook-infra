"""LedgerLens: small asynchronous CSV accounting service (standard library only)."""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from decimal import Decimal
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sqlite3
import time

VERSION='0.4.0'


def settings():
    return (Path(os.environ.get('LEDGER_DATABASE','.dev/ledger.sqlite3')),
            Path(os.environ.get('LEDGER_UPLOADS','.dev/uploads')),
            Path(os.environ.get('LEDGER_TOKEN_FILE','.dev/token')))


@contextmanager
def database(path):
    db=sqlite3.connect(path,timeout=10,isolation_level=None)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    try:
        yield db
    finally:
        db.close()


def migrate(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with database(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        version=db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if version is None:
            db.execute('CREATE TABLE imports (id TEXT PRIMARY KEY, object_name TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, result TEXT, created_ns INTEGER NOT NULL)')
            db.execute("INSERT INTO metadata VALUES ('schema','1')")
            version=['1']
        if version[0]=='1':
            db.execute('ALTER TABLE imports ADD COLUMN lease_until REAL NOT NULL DEFAULT 0')
            db.execute('ALTER TABLE imports ADD COLUMN executions INTEGER NOT NULL DEFAULT 0')
            db.execute('CREATE TABLE heartbeat (id INTEGER PRIMARY KEY CHECK(id=1),seen REAL NOT NULL)')
            db.execute("UPDATE metadata SET value='2' WHERE key='schema'")
        elif version[0]!='2':
            raise RuntimeError('unsupported database schema')
        db.commit()


def summarize(raw):
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    if not rows or len(rows)>1000 or any(set(row)!={'category','amount'} for row in rows):
        raise ValueError('invalid_csv')
    totals={}
    for row in rows:
        category=row['category']
        amount=Decimal(row['amount'])
        if not category or len(category)>40 or not amount.is_finite() or amount.as_tuple().exponent < -2:
            raise ValueError('invalid_csv')
        totals[category]=totals.get(category,0)+int(amount*100)
    return {'rows':len(rows),'totals_cents':dict(sorted(totals.items()))}


def worker_once(path,uploads):
    with database(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO heartbeat VALUES (1,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen',(time.time(),))
        row=db.execute("SELECT * FROM imports WHERE state='queued' OR (state='running' AND lease_until<?) ORDER BY created_ns LIMIT 1",(time.time(),)).fetchone()
        if row is None:
            db.commit();return False
        db.execute("UPDATE imports SET state='running',lease_until=? WHERE id=?",(time.time()+2,row['id']))
        db.commit()
        try:
            raw=(uploads/row['object_name']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row['digest']:
                raise RuntimeError('upload_digest_mismatch')
            result=summarize(raw);status='done'
        except (ValueError,ArithmeticError,UnicodeError):
            result={'error':'invalid_csv'};status='failed'
        # I/O errors are operational failures: crash and let the supervisor
        # recover the lease instead of claiming the import was processed.
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE imports SET state=?,result=?,executions=executions+1,lease_until=0 WHERE id=?',
                   (status,json.dumps(result,sort_keys=True),row['id']))
        db.commit()
        return True


def serve(path,uploads,token_file,host,port):
    token=token_file.read_text().strip()
    if len(token)<24:
        raise RuntimeError('production token must contain at least 24 characters')
    uploads.mkdir(parents=True,exist_ok=True)
    public=os.environ.get('LEDGER_PUBLIC_URL','http://localhost:8080').rstrip('/')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,body):
            encoded=json.dumps(body,sort_keys=True).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
        def authorized(self):
            value=self.headers.get('Authorization','')
            if not secrets.compare_digest(value,'Bearer '+token):
                self.respond(401,{'error':'unauthorized'});return False
            return True
        def do_GET(self):
            if self.path=='/health':return self.respond(200,{'status':'alive'})
            if self.path=='/ready':
                try:
                    with database(path) as db:
                        row=db.execute('SELECT seen FROM heartbeat WHERE id=1').fetchone()
                        ready=row is not None and time.time()-row[0]<5
                    return self.respond(200 if ready else 503,{'ready':ready})
                except sqlite3.Error:return self.respond(503,{'ready':False})
            if not self.authorized():return
            if self.path=='/meta':return self.respond(200,{'version':VERSION,'pid':os.getpid()})
            match=re.fullmatch(r'/imports/([A-Za-z0-9-]{1,64})(/source)?',self.path)
            if not match:return self.respond(404,{'error':'not_found'})
            with database(path) as db:row=db.execute('SELECT * FROM imports WHERE id=?',(match[1],)).fetchone()
            if row is None:return self.respond(404,{'error':'not_found'})
            if match[2]:
                raw=(uploads/row['object_name']).read_bytes()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw);return
            self.respond(200,{'id':row['id'],'state':row['state'],'result':json.loads(row['result']) if row['result'] else None,
                              'source_url':public+'/imports/'+row['id']+'/source'})
        def do_POST(self):
            if not self.authorized():return
            match=re.fullmatch(r'/imports/([A-Za-z0-9-]{1,64})',self.path)
            if not match:return self.respond(404,{'error':'not_found'})
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536:return self.respond(413,{'error':'body_size'})
            raw=self.rfile.read(length);digest=hashlib.sha256(raw).hexdigest()
            name=match[1]+'.csv'
            with database(path) as db:
                db.execute('BEGIN IMMEDIATE')
                existing=db.execute('SELECT digest FROM imports WHERE id=?',(match[1],)).fetchone()
                if existing:
                    db.commit();return self.respond(202 if existing[0]==digest else 409,{'id':match[1]})
                temporary=uploads/(name+'.'+secrets.token_hex(8)+'.tmp')
                temporary.write_bytes(raw);temporary.replace(uploads/name)
                db.execute("INSERT INTO imports(id,object_name,digest,state,result,created_ns) VALUES(?,?,?,'queued',NULL,?)",(match[1],name,digest,time.time_ns()))
                db.commit()
            self.respond(202,{'id':match[1],'status_url':public+'/imports/'+match[1]})

    server=ThreadingHTTPServer((host,port),Handler)
    print(json.dumps({'event':'api_started','port':server.server_port}),flush=True)
    server.serve_forever()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['migrate','serve','worker'])
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args();path,uploads,token_file=settings()
    if args.command=='migrate':migrate(path)
    elif args.command=='serve':serve(path,uploads,token_file,args.host,args.port)
    else:
        stopped=False
        def stop(*_):
            nonlocal stopped
            stopped=True
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        while not stopped:
            worker_once(path,uploads);time.sleep(.1)


if __name__=='__main__':main()
