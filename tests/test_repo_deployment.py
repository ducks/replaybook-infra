"""Exercise the verifier against real application state and unseen inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]/'039-repo-to-deployment'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
app=load('ledgerlens',ROOT/'repo/ledgerlens.py')
verifier=load('deployment_controller',ROOT/'controller.py')


class DeploymentContractTests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.db=self.root/'state.sqlite3';self.uploads=self.root/'uploads';self.uploads.mkdir()
  app.migrate(self.db)
 def observation(self):
  with app.database(self.db) as db:rows=[dict(r) for r in db.execute('SELECT * FROM imports')]
  return {'rows':rows,'objects':{r['id']:hashlib.sha256((self.uploads/r['object_name']).read_bytes()).hexdigest() for r in rows}}
 def fixture(self,bad=False):
  identity,record=verifier.record(bad=bad)
  raw=record['body'].encode();(self.uploads/(identity+'.csv')).write_bytes(raw)
  with app.database(self.db) as db:
   db.execute("INSERT INTO imports(id,object_name,digest,state,created_ns) VALUES(?,?,?,'queued',?)",(identity,identity+'.csv',hashlib.sha256(raw).hexdigest(),time.time_ns()))
  app.worker_once(self.db,self.uploads)
  return identity,{'records':{identity:record}}
 def test_independent_aggregates_match_unseen_input(self):
  rng=random.Random(61118)
  for _ in range(40):
   raw=('category,amount\n'+''.join(f'{rng.choice(["a","b","c"])},{rng.randrange(100)}.{rng.randrange(100):02d}\n' for _ in range(9))).encode()
   status,result=verifier.expected(raw)
   self.assertEqual(status,'done');self.assertEqual(app.summarize(raw),result)
 def test_legitimate_history_and_failed_imports_are_accepted(self):
  for bad in [False,True]:
   identity,state=self.fixture(bad)
   # Observe only this test's accumulated contract.
   if bad:state['records'].update(previous['records'])
   verifier.records_ok(state,self.observation());previous=state
 def test_discarding_work_is_rejected(self):
  identity,state=self.fixture()
  with app.database(self.db) as db:db.execute('DELETE FROM imports WHERE id=?',(identity,))
  with self.assertRaisesRegex(verifier.Failure,'lost'):verifier.records_ok(state,self.observation())
 def test_duplicate_processing_and_modified_uploads_are_rejected(self):
  identity,state=self.fixture()
  with app.database(self.db) as db:db.execute("UPDATE imports SET state='queued' WHERE id=?",(identity,))
  app.worker_once(self.db,self.uploads)
  with self.assertRaisesRegex(verifier.Failure,'replayed'):verifier.records_ok(state,self.observation())
  with app.database(self.db) as db:db.execute('UPDATE imports SET executions=1')
  (self.uploads/(identity+'.csv')).write_bytes(b'altered')
  with self.assertRaisesRegex(verifier.Failure,'upload changed'):verifier.records_ok(state,self.observation())
 def test_production_paths_and_independent_service_names(self):
  data={'api_unit':'custom-http.service','worker_unit':'custom-jobs.service','database':'/srv/lens/db','uploads':'/srv/lens/uploads','token_file':'/etc/lens/token','release':'/opt/releases/lens','install_script':'/opt/lens/deploy.sh','artifact':'/opt/lens/release.tar.gz','operator_doc':'/opt/lens/OPERATIONS.md'}
  verifier.validate_handoff(data)
  for value in ['/tmp/db','/run/db','/opt/ledgerlens/repo/db','/opt/releases/lens/db','/root/db']:
   with self.subTest(value=value),self.assertRaises(verifier.Failure):verifier.validate_handoff({**data,'database':value})
 def test_original_source_and_private_verifier_are_separate(self):
  nix=(ROOT/'nixos.nix').read_text()
  for name in ['oracle.sh','controller.py','controls','solution']:self.assertNotIn(name,nix)
  self.assertIn('${./repo}',nix)

if __name__=='__main__':unittest.main()
