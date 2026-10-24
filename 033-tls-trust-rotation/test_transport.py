"""Real TLS negative controls and end-to-end controller checks."""
import hashlib
import socket
import importlib.util
import os
from pathlib import Path
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('delivery_service', ROOT / 'app/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
sys.path.insert(0, os.environ.get('REPLAYBOOK_DIR', str(ROOT.parents[1] / 'replaybook')))
from integrations.host import scenario_phase as phases


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates = tempfile.TemporaryDirectory()
        cls.pki = Path(cls.certificates.name)
        def openssl(*args):
            subprocess.run(['openssl', *args], cwd=cls.pki, check=True, capture_output=True)
        for ca in ('platform', 'archive-root'):
            openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
                    '-keyout', ca+'.key', '-out', ca+'.pem', '-subj', '/CN='+ca,
                    '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        for name, ca, dns in (('receiver','platform','localhost'), ('archive','archive-root','localhost'), ('directory','platform','directory.internal')):
            openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', name+'.key', '-out', name+'.csr', '-subj', '/CN='+dns)
            (cls.pki / (name+'.ext')).write_text('subjectAltName=DNS:'+dns+'\nextendedKeyUsage=serverAuth\n')
            openssl('x509', '-req', '-in', name+'.csr', '-CA', ca+'.pem', '-CAkey', ca+'.key', '-CAcreateserial', '-days', '2', '-extfile', name+'.ext', '-out', name+'.pem')

    @classmethod
    def tearDownClass(cls):
        cls.certificates.cleanup()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / 'ca.pem'
        self.bundle.write_bytes((self.pki / 'archive-root.pem').read_bytes())
        environment = patch.dict(os.environ, {'CA_BUNDLE':str(self.bundle), 'RECEIVER_HOST':'localhost'})
        environment.start()
        self.addCleanup(environment.stop)
        self.servers = []
        self.addCleanup(self.shutdown)
        self.ports = {}
        for port, name in ((4443,'receiver'), (4444,'archive'), (4445,'directory')):
            instance = service.server('receiver', 0, str(self.root/'receipts.sqlite3'), str(self.pki/(name+'.pem')), str(self.pki/(name+'.key')))
            self.ports[port] = instance.server_port
            self.start(instance)
        self.dispatch = service.server('dispatch', 0, str(self.root/'dispatch.sqlite3'))
        self.start(self.dispatch)
        self.observer = service.server('observer', 0, str(self.root/'receipts.sqlite3'))
        self.start(self.observer)
        original_send = service.send
        routing = patch.object(service, 'send', side_effect=lambda port,path,body=None:original_send(self.ports[port],path,body))
        routing.start()
        self.addCleanup(routing.stop)
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.worker = threading.Thread(target=service.worker, args=(self.dispatch.database,self.stop), daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 3)
        # LIFO cleanup must stop the worker before joining it.
        self.addCleanup(self.stop.set)
        original_request = phases.request
        controller = patch.object(phases, 'request', side_effect=lambda base,step,path: original_request(
            f'http://127.0.0.1:{self.observer.server_port if path.startswith("/receipts/") else self.dispatch.server_port}',step,path))
        controller.start()
        self.addCleanup(controller.stop)

    def start(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append((server,thread))

    def shutdown(self):
        for server,thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def assert_security_failure(self):
        with self.assertRaises(phases.PhaseFailure) as failed:
            phases.run_wait_http("unused", "immediate", {"path":"/transport/security",
                "expected_status":200,"expected_body":"verified","timeout_seconds":0.2,
                "request_timeout_seconds":3,"failure_category":"tls_peer_validation_disabled"})
        self.assertEqual(failed.exception.category,"tls_peer_validation_disabled")

    def repair(self):
        self.bundle.write_bytes((self.pki/'platform.pem').read_bytes())

    def test_repair_recovers_exact_backlog_and_fresh_work_all_phases(self):
        manifest = ROOT/'phase-plan.toml'
        phases.run_phase(manifest,'preflight','unused',self.root/'controller')
        self.assertFalse(service.security_status())
        self.repair()
        for phase in ('immediate','service-restart','host-reboot'):
            phases.run_phase(manifest,phase,'unused',self.root/'controller')
        with sqlite3.connect(self.observer.database) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM deliveries WHERE delivered=1').fetchone()[0],16)
        response = phases.request('unused',{'method':'POST'},'/receipts/forged-record')
        self.assertEqual(response.status,405)

    def test_certificate_swap_can_pass_http_but_fails_pinned_controller(self):
        spec = importlib.util.spec_from_file_location('tls_swap_lifecycle', ROOT/'lifecycle.py')
        lifecycle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lifecycle)
        def identities():
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            peers = {}
            for original, actual in self.ports.items():
                with socket.create_connection(('127.0.0.1',actual),timeout=2) as sock:
                    with context.wrap_socket(sock,server_hostname='localhost') as secured:
                        peers[str(original)] = hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
            return {'peers':peers,'roots':{name:hashlib.sha256((self.pki/name).read_bytes()).hexdigest()
                    for name in ('platform.pem','archive-root.pem')}}
        state = self.root/'controller'
        with patch.object(lifecycle,'remote_identity',side_effect=identities):
            lifecycle.run('preflight','unused',state,phases)
            self.ports[4443],self.ports[4444] = self.ports[4444],self.ports[4443]
            # The old HTTP-only verifier accepts this forbidden repair.
            phases.run_phase(ROOT/'phase-plan.toml','immediate','unused',state)
            # The production v2 controller rejects it before HTTP scoring.
            with self.assertRaisesRegex(RuntimeError,'identities changed'):
                lifecycle.run('immediate','unused',state,phases)

    def test_old_or_union_ca_store_is_rejected(self):
        self.assertFalse(service.security_status())
        self.assert_security_failure()
        self.bundle.write_bytes((self.pki/'platform.pem').read_bytes()+(self.pki/'archive-root.pem').read_bytes())
        self.assertFalse(service.security_status())
        self.assert_security_failure()
        self.repair()
        self.assertTrue(service.security_status())

    def test_disabled_chain_or_hostname_validation_is_rejected(self):
        self.repair()
        with patch.object(service,'transport_context',side_effect=ssl._create_unverified_context):
            self.assertFalse(service.security_status())
            self.assert_security_failure()
        def no_hostname():
            context = ssl.create_default_context(cafile=str(self.bundle))
            context.check_hostname = False
            return context
        with patch.object(service,'transport_context',side_effect=no_hostname):
            self.assertFalse(service.security_status())
            self.assert_security_failure()

    def test_unreachable_security_endpoint_does_not_count_as_rejection(self):
        self.repair()
        self.ports[4444] = self.dispatch.server_port  # HTTP instead of TLS.
        self.assertFalse(service.security_status())

    def test_deleted_backlog_fails_controller_verifier(self):
        manifest = ROOT/'phase-plan.toml'
        phases.run_phase(manifest,'preflight','unused',self.root/'controller')
        with sqlite3.connect(self.dispatch.database) as db:
            db.execute('DELETE FROM deliveries')
        self.repair()
        config = tomllib.loads(manifest.read_text())
        for step in config['verify']['steps']:
            if 'timeout_seconds' in step:
                step['timeout_seconds'] = 0.2
        with patch.object(phases,'load_manifest',return_value=config):
            with self.assertRaises(phases.PhaseFailure) as failed:
                phases.run_phase(manifest,'immediate','unused',self.root/'controller')
        self.assertEqual(failed.exception.category,'backlog_not_recovered')


class IdentityTests(unittest.TestCase):
    def load_lifecycle(self):
        spec = importlib.util.spec_from_file_location('tls_lifecycle', ROOT/'lifecycle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_controller_rejects_certificate_swap_and_ca_relabel(self):
        from unittest.mock import Mock
        lifecycle = self.load_lifecycle()
        pins = {'peers':{'4443':'a'*64,'4444':'b'*64,'4445':'c'*64},
                'roots':{'platform.pem':'d'*64,'archive-root.pem':'e'*64}}
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            phases_mock = Mock()
            with patch.object(lifecycle,'remote_identity',return_value=pins):
                lifecycle.run('preflight','unused',state,phases_mock)
                lifecycle.run('immediate','unused',state,phases_mock)
            phases_mock.reset_mock()
            import copy
            for group, first, second in (('peers','4443','4444'),('roots','platform.pem','archive-root.pem')):
                changed = copy.deepcopy(pins)
                changed[group][first],changed[group][second] = changed[group][second],changed[group][first]
                with patch.object(lifecycle,'remote_identity',return_value=changed):
                    with self.assertRaisesRegex(RuntimeError,'identities changed'):
                        lifecycle.run('host_reboot','unused',state,phases_mock)
                phases_mock.run_phase.assert_not_called()

    def test_snapshot_selects_its_own_phase_runner(self):
        lifecycle = self.load_lifecycle()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario = root/'scenario-packs/pack/033-tls-trust-rotation'
            scenario.mkdir(parents=True)
            host = root/'host-harness'
            host.mkdir()
            (host/'scenario_phase.py').write_text('MARKER = "frozen"\n')
            with patch.object(lifecycle,'ROOT',scenario):
                self.assertEqual(lifecycle.phase_runner().MARKER,'frozen')


if __name__ == '__main__':
    unittest.main()
