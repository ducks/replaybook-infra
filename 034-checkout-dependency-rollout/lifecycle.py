"""Controller-only HTTP exercises and independent SQLite observations."""
import concurrent.futures
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request


KIND = 'checkout'
DATABASE = '/var/lib/checkout/ledger.sqlite3'
QUERIES = {'invoices': 'SELECT id, body FROM invoices ORDER BY id'}

class Failure(RuntimeError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def request(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def require_http(base, path, status, payload=None, body=None):
    actual, text = request(base, path, payload)
    if actual != status or (body is not None and text != body):
        raise Failure('http_contract_failed', f'{path}: HTTP {actual}; required {status}')


def wait_ready(base):
    end = time.monotonic() + 60
    while True:
        try:
            require_http(base, '/health', 200, body='ok')
            return
        except (OSError, Failure):
            if time.monotonic() >= end:
                raise
            time.sleep(.2)


def snapshot():
    port = int(os.environ['REPLAYBOOK_HOST_SSH_PORT'])
    if not 0 < port < 65536:
        raise ValueError('invalid SSH port')
    key = os.environ.get('REPLAYBOOK_HOST_SSH_KEY', str(Path.home()/'.ssh/id_ed25519'))
    script = 'import sqlite3,json\ndb=sqlite3.connect(' + repr('file:'+DATABASE+'?mode=ro') + ',uri=True)\n'
    script += 'result={}\n'
    for name, query in QUERIES.items():
        script += 'result['+repr(name)+']=db.execute('+repr(query)+').fetchall()\n'
    script += 'print(json.dumps(result))\n'
    run = subprocess.run(['ssh','-i',key,'-p',str(port),'-o','BatchMode=yes',
        '-o','ConnectTimeout=5','-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null',
        '-o','LogLevel=ERROR','root@127.0.0.1','python -'],input=script,text=True,capture_output=True,timeout=25,check=True)
    return json.loads(run.stdout)


def generated(count):
    result = {}
    for _ in range(count):
        identity = secrets.token_hex(16)
        if KIND == 'reservation':
            payload = {'quantity':secrets.randbelow(3)+1,'customer':secrets.token_hex(16)}
        elif KIND == 'notification':
            payload = {'destination':secrets.token_hex(16)+'@example.invalid','text':secrets.token_hex(32)}
        else:
            payload = {'sku':secrets.token_hex(16),'amount_cents':secrets.randbelow(9000)+100}
        result[identity] = payload
    return result


def submit(base, prefix, records, status, concurrency=1):
    def send(item):
        identity, payload = item
        require_http(base, prefix+identity, status, payload)
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(send, records.items()))


def records_ok(records, observed):
    table = 'invoices' if KIND == 'checkout' else 'messages' if KIND == 'notification' else 'reservations'
    rows = {row[0]:row[1:] for row in observed[table]}
    for identity, payload in records.items():
        row = rows.get(identity)
        body = row[1] if KIND == 'reservation' and row else row[0] if row else None
        if body is None or json.loads(body) != payload:
            raise Failure('accepted_records_not_preserved','accepted record or original payload is missing')
        if KIND == 'reservation' and row[0] != payload['quantity']:
            raise Failure('accepted_records_not_preserved','reservation quantity changed')
        if KIND == 'notification' and row[1] != 'sent':
            raise Failure('backlog_not_recovered','accepted notification is not sent')
    if KIND == 'notification':
        receipts = {row[0]:row[1:] for row in observed['receipts']}
        for identity, payload in records.items():
            row = receipts.get(identity)
            if not row or json.loads(row[0]) != payload or row[1] != 1:
                raise Failure('delivery_receipts_not_preserved','receipt missing, changed, or duplicated')


def capacity_ok(observed, total):
    if len(observed['capacity']) != 1:
        raise Failure('capacity_not_conserved','capacity record missing')
    current_total, available = observed['capacity'][0]
    used = sum(row[1] for row in observed['reservations'])
    if current_total != total or available != total-used or available < 0:
        raise Failure('capacity_not_conserved','available capacity differs from committed reservations')


def run(phase, base, state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir/'work-contract.json'
    wait_ready(base)
    if phase == 'preflight':
        state = {'records':generated(4), 'total':256}
        if KIND == 'checkout':
            submit(base,'/ledger/invoices/',state['records'],201,concurrency=4)
            state['retry_orders'] = generated(2)
            submit(base,'/orders/',state['retry_orders'],502)
            records_ok(state['records'], snapshot())
        elif KIND == 'notification':
            historical = generated(2)
            submit(base,'/imports/',historical,202)
            submit(base,'/messages/',state['records'],202,concurrency=4)
            time.sleep(1)
            before = snapshot()
            messages = {row[0]:row for row in before['messages']}
            if any(identity not in messages or messages[identity][2] != 'pending' for identity in state['records']):
                raise Failure('incident_not_reproduced','pending notification workload did not remain blocked')
            records_ok(historical,before)
            state['records'].update(historical)
        else:
            submit(base,'/reservations/',state['records'],201,concurrency=4)
            observed = snapshot()
            records_ok(state['records'],observed)
            try:
                capacity_ok(observed,state['total'])
            except Failure:
                pass
            else:
                raise Failure('incident_not_reproduced','concurrent reservation accounting did not drift')
        state_file.write_text(json.dumps(state,sort_keys=True)+'\n')
        return
    state = json.loads(state_file.read_text())
    # Check existing evidence before creating new work. Pending notifications
    # can take a bounded interval to drain after an ordinary service restart.
    end = time.monotonic()+20
    while True:
        try:
            observed = snapshot()
            records_ok(state['records'],observed)
            if KIND == 'reservation':
                capacity_ok(observed,state['total'])
            break
        except Failure:
            if time.monotonic() >= end:
                raise
            time.sleep(.2)
    fresh = generated(8)
    if KIND == 'checkout':
        fresh.update(state.get('retry_orders',{}))
    prefix = '/orders/' if KIND == 'checkout' else '/messages/' if KIND == 'notification' else '/reservations/'
    submit(base,prefix,fresh,202 if KIND == 'notification' else 201,concurrency=8)
    # Same IDs submitted again must not duplicate or mutate accepted work.
    submit(base,prefix,fresh,202 if KIND == 'notification' else 201,concurrency=1)
    state['records'].update(fresh)
    end = time.monotonic()+20
    while True:
        try:
            observed = snapshot()
            records_ok(state['records'],observed)
            if KIND == 'reservation':
                capacity_ok(observed,state['total'])
            break
        except Failure:
            if time.monotonic() >= end:
                raise
            time.sleep(.2)
    state_file.write_text(json.dumps(state,sort_keys=True)+'\n')


if __name__ == '__main__':
    phase, base, state = sys.argv[1:]
    try:
        run(phase,base,Path(state))
    except Exception as error:
        Path(state).mkdir(parents=True,exist_ok=True)
        (Path(state)/'phase-failure.json').write_text(json.dumps({
            'phase':phase,'category':getattr(error,'category','verification_failed'),
            'message':str(error)})+'\n')
        print(str(error),file=sys.stderr)
        sys.exit(1)
