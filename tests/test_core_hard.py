"""Exercise incident contracts against real local HTTP services and SQLite."""
import contextlib
import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.servers = []
        self.addCleanup(self.shutdown)

    def load(self, prefix):
        path = next(ROOT.glob(prefix+'-*'))
        return module(prefix+'_app', path/'app/service.py'), module(prefix+'_controller',path/'lifecycle.py')

    def start(self, server):
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.servers.append((server,thread))
        return 'http://127.0.0.1:'+str(server.server_port)

    def shutdown(self):
        for server,thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def observe(self, controller, database):
        def snapshot():
            with sqlite3.connect(database) as db:
                # JSON roundtrip matches the independent SSH probe's wire form.
                return json.loads(json.dumps({name:db.execute(query).fetchall() for name,query in controller.QUERIES.items()}))
        self.stack.enter_context(patch.object(controller,'snapshot',side_effect=snapshot))
        return snapshot

    def test_checkout_recovers_failed_orders_and_preserves_historical_payloads(self):
        app, controller = self.load('034')
        database = self.root/'ledger.sqlite3'
        ledger = self.start(app.server('ledger',0,str(database)))
        # Reserve and close a socket through a server object to obtain an
        # unused upstream port, without assuming a fixed port is available.
        unused = app.server('ledger',0,str(self.root/'unused.sqlite3'))
        unavailable = 'http://127.0.0.1:'+str(unused.server_port)
        unused.server_close()
        api = [self.start(app.server('api',0,str(self.root/'api.sqlite3'),unavailable))]
        original = controller.request
        def request(_base,path,payload=None):
            if path.startswith('/ledger/'):
                return original(ledger,path[len('/ledger'):],payload)
            return original(api[0],path,payload)
        self.stack.enter_context(patch.object(controller,'request',side_effect=request))
        snapshot = self.observe(controller,database)
        state = self.root/'controller'
        controller.run('preflight','unused',state)
        # A green health path does not fix the order path.
        with self.assertRaises(controller.Failure):
            controller.require_http('unused','/orders/new',201,{'sku':'test','amount_cents':100})
        api[0] = self.start(app.server('api',0,str(self.root/'api2.sqlite3'),ledger))
        for phase in ('immediate','service-restart','host-reboot'):
            controller.run(phase,'unused',state)
        records = json.loads((state/'work-contract.json').read_text())['records']
        identity = next(iter(records))
        with sqlite3.connect(database) as db:
            db.execute('DELETE FROM invoices WHERE id=?',(identity,))
        with self.assertRaisesRegex(controller.Failure,'payload is missing'):
            controller.records_ok(records,snapshot())

    def test_outbox_rejects_dropped_jobs_missing_receipts_and_duplicate_delivery(self):
        app, controller = self.load('035')
        database = self.root/'messages.sqlite3'
        base = self.start(app.server(0,str(database)))
        snapshot = self.observe(controller,database)
        state = self.root/'controller'
        controller.run('preflight',base,state)
        with self.assertRaises(KeyError):
            app.deliver_one(str(database),1)
        while app.deliver_one(str(database),2):
            pass
        records = json.loads((state/'work-contract.json').read_text())['records']
        controller.records_ok(records,snapshot())
        identity = next(iter(records))
        with sqlite3.connect(database) as db:
            db.execute('UPDATE receipts SET deliveries=2 WHERE id=?',(identity,))
        with self.assertRaisesRegex(controller.Failure,'duplicated'):
            controller.records_ok(records,snapshot())
        with sqlite3.connect(database) as db:
            db.execute('DELETE FROM receipts WHERE id=?',(identity,))
        with self.assertRaisesRegex(controller.Failure,'receipt missing'):
            controller.records_ok(records,snapshot())
        with sqlite3.connect(database) as db:
            db.execute('DELETE FROM messages WHERE id=?',(identity,))
        with self.assertRaisesRegex(controller.Failure,'payload is missing'):
            controller.records_ok(records,snapshot())

    def test_outbox_full_lifecycle_and_repeated_submissions_are_idempotent(self):
        app, controller = self.load('035')
        database = self.root/'messages.sqlite3'
        base = self.start(app.server(0,str(database)))
        self.observe(controller,database)
        state = self.root/'controller'
        controller.run('preflight',base,state)
        stop = threading.Event()
        worker = threading.Thread(target=app.worker,args=(str(database),2,stop),daemon=True)
        worker.start()
        try:
            for phase in ('immediate','service-restart','host-reboot'):
                controller.run(phase,base,state)
        finally:
            stop.set()
            worker.join(3)
        with sqlite3.connect(database) as db:
            self.assertEqual(db.execute('SELECT MAX(deliveries) FROM receipts').fetchone()[0],1)

    def test_reservations_require_both_reconciliation_and_atomic_writes(self):
        app, controller = self.load('036')
        database = self.root/'reservations.sqlite3'
        base = self.start(app.server(0,str(database),False))
        snapshot = self.observe(controller,database)
        state = self.root/'controller'
        controller.run('preflight',base,state)
        records = json.loads((state/'work-contract.json').read_text())['records']
        # Switching write mode alone leaves the accepted historical drift.
        with self.assertRaises(controller.Failure):
            controller.capacity_ok(snapshot(),256)
        # Reconciliation alone is lost again under the next concurrent burst.
        with sqlite3.connect(database) as db:
            db.execute('UPDATE capacity SET available=total-(SELECT SUM(quantity) FROM reservations)')
        controller.capacity_ok(snapshot(),256)
        fresh = controller.generated(8)
        controller.submit(base,'/reservations/',fresh,201,concurrency=8)
        records.update(fresh)
        with self.assertRaises(controller.Failure):
            controller.capacity_ok(snapshot(),256)
        with sqlite3.connect(database) as db:
            db.execute('UPDATE capacity SET available=total-(SELECT SUM(quantity) FROM reservations)')
        repaired = self.start(app.server(0,str(database),True))
        # Persist additional accepted work into the controller contract.
        (state/'work-contract.json').write_text(json.dumps({'records':records,'total':256}))
        for phase in ('immediate','service-restart','host-reboot'):
            controller.run(phase,repaired,state)
        observed = snapshot()
        controller.capacity_ok(observed,256)
        observed['capacity'][0][0] = 512
        with self.assertRaises(controller.Failure):
            controller.capacity_ok(observed,256)
        identity = next(iter(records))
        with sqlite3.connect(database) as db:
            db.execute('DELETE FROM reservations WHERE id=?',(identity,))
        with self.assertRaises(controller.Failure):
            controller.records_ok(records,snapshot())

    def test_new_scenarios_keep_controller_sources_out_of_guest_nix_inputs(self):
        for path in sorted(ROOT.glob('03[456]-*')):
            config = (path/'nixos.nix').read_text()
            self.assertIn('${./app/service.py}',config)
            for source in ('lifecycle.py','oracle.sh','CONTRACT.md','work-contract.json'):
                self.assertNotIn(source,config)
                self.assertNotIn(source,(path/'app/service.py').read_text())
            for marker in ('oracle.sh','phase-failure.json','work-contract.json'):
                self.assertNotIn(marker,(path/'instruction.md').read_text())


if __name__ == '__main__':
    unittest.main()
