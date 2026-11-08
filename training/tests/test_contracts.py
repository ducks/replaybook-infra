import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPLAYBOOK = Path(os.environ.get("REPLAYBOOK_DIR", ROOT.parents[1] / "replaybook"))
sys.path.insert(0, str(REPLAYBOOK))
from integrations.host import scenario_phase as phase


class ContractControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_contract(self, scenario, responses, *, seed=False):
        if scenario == "042-receipt-directory-ownership":
            spec=importlib.util.spec_from_file_location("receipt_check",ROOT/scenario/"check.py")
            check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
            try:
                with patch.object(check,"request",side_effect=lambda base,method,path: (lambda response:(response.status,response.body))(responses(method,path))):
                    if seed:check.run_phase("http://fixture","preflight",self.root/"state")
                    else:
                        (self.root/"state").mkdir(exist_ok=True)
                        (self.root/"state/receipt-controller-state.json").write_text(json.dumps({"failed":["controller-test-id"],"accepted":[]}))
                    check.run_phase("http://fixture","immediate",self.root/"state")
            except check.CheckFailure as error:
                text=str(error)
                category="service_identity_changed" if '/identity' in text else "storage_permissions_unsafe" if '/storage-policy' in text else "historical_receipts_lost" if '/history' in text else "accepted_receipts_lost"
                raise phase.PhaseFailure(text,category) from error
            return
        text = (ROOT/scenario/"scenario.toml").read_text()
        text = re.sub(r"timeout_seconds = \d+", "timeout_seconds = 0.005", text)
        text = text.replace('type = "wait_http"', 'type = "wait_http"\ninterval_seconds = 0.001')
        manifest = self.root/"scenario.toml"
        manifest.write_text(text)
        def request(base, step, path):
            return responses(step.get("method","GET"), path)
        with patch.object(phase,"request",side_effect=request):
            if seed: phase.run_phase(manifest,"preflight","http://fixture",self.root/"state")
            phase.run_phase(manifest,"immediate","http://fixture",self.root/"state")

    def test_dns_rejects_partial_fix_that_breaks_unrelated_resolution(self):
        def responses(method,path):
            return phase.Response(200, {"/health":"inventory-ready\n", "/resolve/inventory":"127.0.0.1\n", "/resolve/metrics":"127.0.0.1\n"}[path])
        for scenario in ["041-dns-resolver-drift", "043-dns-host-override"]:
            with self.subTest(scenario=scenario), self.assertRaises(phase.PhaseFailure) as error:
                self.run_contract(scenario, responses)
            self.assertEqual(error.exception.category,"unrelated_dns_broken")

    def test_storage_rejects_root_world_writable_and_lost_history_shortcuts(self):
        for bad_path,bad_body,category in [("/identity","root","service_identity_changed"),("/storage-policy","unsafe","storage_permissions_unsafe"),("/history","empty","historical_receipts_lost")]:
            def responses(method,path):
                values={"/identity":"receipt-writer","/storage-policy":"restricted","/history":"historical-ledger-entry\n"}
                return phase.Response(200, bad_body if path==bad_path else values[path])
            with self.subTest(category=category), self.assertRaises(phase.PhaseFailure) as error:
                self.run_contract("042-receipt-directory-ownership",responses)
            self.assertEqual(error.exception.category,category)

    def test_storage_rejects_acknowledged_but_unreadable_new_receipts(self):
        state={"repaired":False}
        def responses(method,path):
            if path=="/health": return phase.Response(200,"ready")
            if path=="/history": return phase.Response(200,"historical-ledger-entry\n")
            if path=="/identity": state["repaired"]=True; return phase.Response(200,"receipt-writer")
            if path=="/storage-policy": return phase.Response(200,"restricted")
            if method=="POST": return phase.Response(201 if state["repaired"] else 503,"stored" if state["repaired"] else "storage unavailable")
            return phase.Response(404,"missing")
        with self.assertRaises(phase.PhaseFailure) as error:
            self.run_contract("042-receipt-directory-ownership",responses,seed=True)
        self.assertEqual(error.exception.category,"accepted_receipts_lost")

    def test_previous_receipts_are_checked_before_any_new_restart_writes(self):
        spec=importlib.util.spec_from_file_location("receipt_check",ROOT/"042-receipt-directory-ownership/check.py")
        check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
        accepted=set(); repaired=False
        def request(base,method,path):
            if path=='/health':return 200,'ready'
            if path=='/history':return 200,'historical-ledger-entry\n'
            if path=='/identity':return 200,'receipt-writer'
            if path=='/storage-policy':return 200,'restricted'
            if method=='POST':
                if not repaired:return 503,'storage unavailable'
                accepted.add(path);return 201,'stored'
            return (200,'present') if path in accepted else (404,'missing')
        with patch.object(check,'request',side_effect=request):
            check.run_phase('http://fixture','preflight',self.root/'state')
            repaired=True
            check.run_phase('http://fixture','immediate',self.root/'state')
            accepted.clear()
            with self.assertRaises(check.CheckFailure):
                check.run_phase('http://fixture','service_restart',self.root/'state')
            self.assertFalse(accepted, 'Verifier must fail before recreating lost receipts')


class ReceiptApplication(unittest.TestCase):
    def test_kernel_permissions_and_real_file_persistence(self):
        if os.geteuid()==0: self.skipTest("permission denial requires a non-root test process")
        spec=importlib.util.spec_from_file_location("receipts",ROOT/"apps/receipts.py")
        app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
        with tempfile.TemporaryDirectory() as directory:
            app.root=Path(directory)
            incoming=app.root/"incoming";incoming.mkdir(mode=0o750)
            (incoming/"historical").write_text("historical-ledger-entry\n")
            server=app.http.server.ThreadingHTTPServer(("127.0.0.1",0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(thread.join,2)
            self.addCleanup(server.shutdown)
            base=f"http://127.0.0.1:{server.server_port}"
            def request(path,method="GET"):
                try:
                    with urllib.request.urlopen(urllib.request.Request(base+path,method=method),timeout=2) as response:return response.status,response.read().decode()
                except urllib.error.HTTPError as error:
                    with error:return error.code,error.read().decode()
            incoming.chmod(0o550)
            self.assertEqual(request("/receipts/new", "POST")[0],503)
            incoming.chmod(0o750)
            self.assertEqual(request("/receipts/new", "POST"),(201,"stored"))
            self.assertEqual(request("/receipts/new"),(200,"present"))
            self.assertEqual((incoming/"new").read_text(),"new")
            self.assertEqual(request("/history"),(200,"historical-ledger-entry\n"))
            incoming.chmod(0o777)
            self.assertEqual(request("/storage-policy"),(200,"unsafe"))
            self.assertEqual(request("/receipts/../escape", "POST")[0],404)
            incoming.chmod(0o750)

if __name__ == "__main__": unittest.main()
