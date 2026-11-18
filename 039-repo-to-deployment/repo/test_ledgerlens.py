import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import ledgerlens as app

class ApplicationTests(unittest.TestCase):
    def test_exact_cents_and_validation(self):
        self.assertEqual(app.summarize(b'category,amount\ntravel,1.10\ntravel,-0.20\nfood,2.01\n'),{'rows':3,'totals_cents':{'food':201,'travel':90}})
        for raw in [b'wrong,columns\na,1\n',b'category,amount\na,NaN\n']:
            with self.assertRaises(ValueError):app.summarize(raw)
    def test_migration_worker_and_no_duplicate_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'db.sqlite3';uploads=root/'uploads';uploads.mkdir()
            app.migrate(path);app.migrate(path)
            raw=b'category,amount\nfood,2.34\n';(uploads/'one.csv').write_bytes(raw)
            with app.database(path) as db:
                db.execute("INSERT INTO imports(id,object_name,digest,state,created_ns) VALUES('one','one.csv',?,'queued',?)",(hashlib.sha256(raw).hexdigest(),time.time_ns()))
            self.assertTrue(app.worker_once(path,uploads));self.assertFalse(app.worker_once(path,uploads))
            with app.database(path) as db:
                row=db.execute('SELECT state,result,executions FROM imports').fetchone()
            self.assertEqual(row['state'],'done');self.assertEqual(row['executions'],1)
            self.assertEqual(json.loads(row['result'])['totals_cents'],{'food':234})

if __name__=='__main__':unittest.main()
