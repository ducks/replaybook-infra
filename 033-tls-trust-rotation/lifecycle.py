#!/usr/bin/env python3
"""Controller-owned certificate identities and declarative HTTP checks.

The legacy hook is necessary because the typed phase runner cannot retain
preflight certificate fingerprints or perform independent SSH/TLS probes.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def phase_runner():
    # The execution snapshot places the exact phase runner alongside the host
    # shell runner. Locate that closure first, then an explicitly selected
    # development checkout. Never silently substitute a live runner for a
    # snapshot's runner.
    for parent in ROOT.parents:
        candidate = parent / 'host-harness/scenario_phase.py'
        if candidate.is_file():
            break
    else:
        repository = Path(os.environ.get('REPLAYBOOK_DIR', str(ROOT.parents[1] / 'replaybook')))
        candidate = repository / 'integrations/host/scenario_phase.py'
    if not candidate.is_file():
        raise RuntimeError('set REPLAYBOOK_DIR to the Replaybook checkout for a direct scenario run')
    spec = importlib.util.spec_from_file_location('tls_scenario_phases', candidate)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Streamed over SSH; neither this probe nor expected fingerprints are installed
# in the guest. No certificate validation is claimed by this observation: it
# captures exact peer identities, while the HTTP phase tests exercise the
# application's active validating transport.
IDENTITY_PROBE = r'''
import hashlib, json, pathlib, socket, ssl
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
peers = {}
for port in (4443, 4444, 4445):
    with socket.create_connection(('127.0.0.1', port), timeout=3) as sock:
        with context.wrap_socket(sock, server_hostname='receiver.internal') as secured:
            peers[str(port)] = hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
roots = {name: hashlib.sha256((pathlib.Path('/etc/delivery/pki') / name).read_bytes()).hexdigest()
         for name in ('platform.pem', 'archive-root.pem')}
print(json.dumps({'peers': peers, 'roots': roots}))
'''


def remote_identity():
    port = int(os.environ['REPLAYBOOK_HOST_SSH_PORT'])
    if not 0 < port < 65536:
        raise ValueError('invalid SSH port')
    key = os.environ.get('REPLAYBOOK_HOST_SSH_KEY', str(Path.home() / '.ssh/id_ed25519'))
    result = subprocess.run(['ssh', '-i', key, '-p', str(port), '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR', 'root@127.0.0.1', 'python -'],
        input=IDENTITY_PROBE, capture_output=True, text=True, timeout=20, check=True)
    data = json.loads(result.stdout)
    if (set(data) != {'peers','roots'} or set(data['peers']) != {'4443','4444','4445'}
        or set(data['roots']) != {'platform.pem','archive-root.pem'}
        or any(not isinstance(value,str) or len(value)!=64
               or any(c not in '0123456789abcdef' for c in value)
               for group in data.values() for value in group.values())):
        raise ValueError('invalid peer identity observation')
    return data


def run(phase, base, state_dir, phases=None):
    phases = phases or phase_runner()
    state_dir.mkdir(parents=True, exist_ok=True)
    identity_file = state_dir / 'tls-peer-identities.json'
    failure_file = state_dir / 'phase-failure.json'
    if phase == 'preflight':
        phases.run_phase(ROOT/'phase-plan.toml', phase, base, state_dir)
        identity_file.write_text(json.dumps(remote_identity(), sort_keys=True)+'\n')
    else:
        observed = remote_identity()
        expected = json.loads(identity_file.read_text())
        if observed != expected:
            failure_file.write_text(json.dumps({'category':'tls_endpoint_identity_changed','phase':phase})+'\n')
            raise RuntimeError('TLS endpoint or authority identities changed')
        phases.run_phase(ROOT/'phase-plan.toml', phase, base, state_dir)


if __name__ == '__main__':
    phase, base, state = sys.argv[1:]
    try:
        run(phase, base, Path(state))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
