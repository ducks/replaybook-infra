"""Controller-only receipt checks; retained IDs never enter agent instructions."""
import argparse
import json
from pathlib import Path
import secrets
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
    if phase=='preflight':
        expect('GET','/health',200,'ready')
        expect('GET','/history',200,'historical-ledger-entry\n')
        failed=['retry-'+secrets.token_hex(16) for _ in range(3)]
        for identifier in failed:expect('POST','/receipts/'+identifier,503,'storage unavailable')
        state={'failed':failed,'accepted':[]}
    else:
        if not path.exists():raise CheckFailure('Missing controller state')
        state=json.loads(path.read_text())
        if not state.get('failed') and not state.get('accepted'):raise CheckFailure('Empty controller state')
        expect('GET','/identity',200,'receipt-writer')
        expect('GET','/storage-policy',200,'restricted')
        expect('GET','/history',200,'historical-ledger-entry\n')
        # Check *all prior accepted IDs* before repairing/retrying or generating
        # new traffic. A restart that clears recent receipts cannot pass.
        for identifier in state['accepted']:expect('GET','/receipts/'+identifier,200,'present')
        fresh=['receipt-'+secrets.token_hex(16) for _ in range(3)]
        for identifier in state['failed']+fresh:
            expect('POST','/receipts/'+identifier,201,'stored')
            expect('GET','/receipts/'+identifier,200,'present')
            state['accepted'].append(identifier)
        state['failed']=[]
    temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(state)+'\n');temporary.replace(path)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('base');parser.add_argument('phase');parser.add_argument('state',type=Path)
    args=parser.parse_args()
    try:run_phase(args.base,args.phase,args.state)
    except (CheckFailure,OSError,ValueError) as error:raise SystemExit(str(error))
