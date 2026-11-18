"""Zero-inference fresh-VM controls for the repository deployment task."""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];TASK=ROOT/'039-repo-to-deployment'
EXPECTED={
 'control/alternative':(1,()),
 'control/noop':(0,("No such file or directory: '/etc/ledgerlens/deployment.json'",)),
 'control/api-only':(0,('Deployment is not ready','service has no live MainPID: ledgerlens-worker.service')),
 'control/discard-history':(0,('Historical/new records',)),
 'control/ephemeral-state':(0,('Production state/credentials',)),
}


def review(output):
 report={'controls':[]}
 for model,(reward,reasons) in EXPECTED.items():
  files=list((output/'matrix/runs').glob('*'+model.replace('/','-')+'-1/result.json'))
  if len(files)!=1:
   report['controls'].append({'model':model,'expectation_met':False,'error':'missing raw result'});continue
  path=files[0];r=json.loads(path.read_text())
  met=r['trial_status']=='evaluated' and r['reward']==reward
  if reward:
   met=met and all(r['verification'].get(k) for k in ['immediate_http','service_restart','host_reboot'])
  else:
   failure=path.parent/'scenario-state/phase-failure.json'
   details=json.loads(failure.read_text()) if failure.exists() else {}
   met=met and details.get('category')=='deployment_contract_failed' and any(reason in details.get('message','') for reason in reasons)
  report['controls'].append({'model':model,'reward':r['reward'],'expectation_met':bool(met),'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 report['passed']=all(item['expectation_met'] for item in report['controls'])
 return report


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--replaybook-dir',type=Path,default=ROOT.parent/'replaybook')
 parser.add_argument('--output',type=Path);parser.add_argument('--base-port',type=int,default=28800)
 parser.add_argument('--review-existing',type=Path,help='Read completed raw evidence without rerunning VMs; preserve the original validation.json.')
 args=parser.parse_args();replaybook=args.replaybook_dir.resolve()
 if args.review_existing:
  output=args.review_existing.resolve();report=review(output);filename='validation-review.json'
 else:
  output=(args.output or replaybook/'jobs'/('repo-deployment-controls-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))).resolve()
  output.mkdir(parents=True,exist_ok=False)
  adapter=output/'adapter.sh'
  adapter.write_text((TASK/'controls/adapter.sh.in').read_text().replace('@ORACLE@',base64.b64encode((TASK/'oracle.sh').read_bytes()).decode()));adapter.chmod(0o700)
  command=[sys.executable,str(replaybook/'integrations/host/run_host_matrix.py'),'--scenario-pack',str(ROOT),
           '--scenario',TASK.name,'--models',*EXPECTED,'--agent-adapter',str(adapter),'--agent-name','deployment-control',
           '--agent-provider','local-control','--attempts','1','--concurrency','1','--agent-timeout-seconds','120',
           '--base-port',str(args.base_port),'--output-dir',str(output/'matrix')]
  print('Controls:',output,flush=True)
  with (output/'controller.log').open('w') as log:completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
  report=review(output);report['matrix_exit_code']=completed.returncode;filename='validation.json'
 (output/filename).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
 return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
