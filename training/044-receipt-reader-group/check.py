"""Controller-only receipt checks; retained IDs never enter agent instructions."""
import argparse
import json
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request

class CheckFailure(RuntimeError): pass


def request(base, method, path):
    try:
        with urllib.request.urlopen(urllib.request.Request(base.rstrip('/')+path,method=method),timeout=3) as response:
            return response.status,response.read(4096).decode()
    except urllib.error.HTTPError as error:
        with error:return error.code,error.read(4096).decode()


def run_phase(base, phase, directory):
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'receipt-controller-state.json'
    def expect(method, endpoint, status, body):
        actual=request(base,method,endpoint)
        if actual!=(status,body): raise CheckFailure(f'{phase}: {method} {endpoint} expected {status} {body!r}, received {actual!r}')
    # systemctl restart can finish before the HTTP listener has bound. Wait only
    # on health; persistence/identity/permission assertions remain strict.
    for endpoint in ['/health','/reader/health']:
        deadline=time.monotonic()+20
        while True:
            try:
                if request(base,'GET',endpoint)==(200,'ready'):break
            except (OSError, urllib.error.URLError):pass
            if time.monotonic()>=deadline:raise CheckFailure(f'{phase}: {endpoint} not ready')
            time.sleep(0.2)
    if phase=='preflight':
        expect('GET','/health',200,'ready')
        expect('GET','/reader/health',200,'ready')
        expect('GET','/history',200,'historical-ledger-entry\n')
        accepted=['receipt-'+secrets.token_hex(16) for _ in range(3)]
        for identifier in accepted:
            expect('POST','/receipts/'+identifier,201,'stored')
            expect('GET','/receipts/'+identifier,200,'present')
            expect('GET','/reader/receipts/'+identifier,503,'storage unavailable')
        state={'accepted':accepted}
    else:
        if not path.exists():raise CheckFailure('Missing controller state')
        state=json.loads(path.read_text())
        if not state.get('accepted'):raise CheckFailure('Empty controller state')
        expect('GET','/identity',200,'receipt-writer')
        expect('GET','/reader/identity',200,'receipt-reader')
        expect('GET','/storage-policy',200,'restricted')
        expect('GET','/reader/storage-policy',200,'restricted')
        expect('GET','/history',200,'historical-ledger-entry\n')
        expect('GET','/reader/history',200,'historical-ledger-entry\n')
        for identifier in state['accepted']:
            expect('GET','/receipts/'+identifier,200,'present')
            expect('GET','/reader/receipts/'+identifier,200,'present')
        fresh=['receipt-'+secrets.token_hex(16) for _ in range(3)]
        for identifier in fresh:
            expect('POST','/receipts/'+identifier,201,'stored')
            expect('GET','/reader/receipts/'+identifier,200,'present')
            expect('POST','/reader/receipts/'+identifier,405,'read only')
            state['accepted'].append(identifier)
    temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(state)+'\n');temporary.replace(path)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('base');parser.add_argument('phase');parser.add_argument('state',type=Path)
    args=parser.parse_args()
    try:run_phase(args.base,args.phase,args.state)
    except (CheckFailure,OSError,ValueError) as error:raise SystemExit(str(error))
