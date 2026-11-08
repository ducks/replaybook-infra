"""Negative controls for the new variants, independent of model inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class ReaderControls(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('reader_check',ROOT/'044-receipt-reader-group/check.py')
        self.check=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.check)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.records=set();self.repaired=False;self.bad=None

    def request(self,base,method,path):
        if self.bad and path==self.bad[0]:return self.bad[1:]
        if path.endswith('/health'):return 200,'ready'
        if path.endswith('/identity'):return 200,'receipt-reader' if path.startswith('/reader/') else 'receipt-writer'
        if path.endswith('/storage-policy'):return 200,'restricted'
        if path.endswith('/history'):return 200,'historical-ledger-entry\n'
        identifier=path.rsplit('/',1)[-1]
        if method=='POST':
            if path.startswith('/reader/'):return 405,'read only'
            self.records.add(identifier);return 201,'stored'
        if path.startswith('/reader/') and not self.repaired:return 503,'storage unavailable'
        return (200,'present') if identifier in self.records else (404,'missing')

    def run_phase(self,name):
        with patch.object(self.check,'request',side_effect=self.request):
            self.check.run_phase('http://fixture',name,self.state)

    def seed(self):
        self.repaired=False;self.bad=None;self.records.clear()
        self.run_phase('preflight');self.repaired=True

    def test_checks_receipts_accepted_before_repair_and_across_restart(self):
        self.seed();self.run_phase('immediate');self.records.clear()
        with self.assertRaises(self.check.CheckFailure):self.run_phase('service_restart')
        self.assertFalse(self.records,'Must reject data loss before generating replacement writes')

    def test_rejects_reader_root_broad_permissions_and_write_enabled_reader(self):
        for endpoint,code,body in [('/reader/identity',200,'root'),('/storage-policy',200,'unsafe'),('/reader/storage-policy',200,'unsafe'),('/reader/history',200,'empty')]:
            with self.subTest(endpoint=endpoint):
                self.seed();self.bad=(endpoint,code,body)
                with self.assertRaises(self.check.CheckFailure):self.run_phase('immediate')
                self.bad=None
        self.seed()
        original=self.request
        def writable(base,method,path):
            if method=='POST' and path.startswith('/reader/'):return 201,'stored'
            return original(base,method,path)
        with patch.object(self.check,'request',side_effect=writable):
            with self.assertRaises(self.check.CheckFailure):self.check.run_phase('http://fixture','immediate',self.state)

    def test_preflight_requires_real_write_success_and_reader_failure(self):
        self.repaired=True
        with self.assertRaises(self.check.CheckFailure):self.run_phase('preflight')

    def test_transient_listener_unavailability_is_retried(self):
        original=self.request
        calls=[]
        def starting(base,method,path):
            if path=='/reader/health':
                calls.append(path)
                if len(calls)==1:return 502,'starting'
            return original(base,method,path)
        with patch.object(self.check,'request',side_effect=starting), patch.object(self.check.time,'sleep'):
            self.check.run_phase('http://fixture','preflight',self.state)
        self.assertGreaterEqual(len(calls),2)

    def test_preflight_rejects_ingestion_failure(self):
        original=self.request
        def broken_writer(base,method,path):
            if method=='POST':return 503,'storage unavailable'
            return original(base,method,path)
        with patch.object(self.check,'request',side_effect=broken_writer):
            with self.assertRaises(self.check.CheckFailure):self.check.run_phase('http://fixture','preflight',self.state)

    def test_durable_recovery_positive_control(self):
        self.seed()
        for phase in ['immediate','service_restart','host_reboot']:self.run_phase(phase)
        self.assertEqual(len(json.loads((self.state/'receipt-controller-state.json').read_text())['accepted']),12)

if __name__=='__main__':unittest.main()
