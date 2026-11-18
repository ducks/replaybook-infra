"""Controller-owned deployment contracts and independent data observations."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parent
PUBLIC='http://ledgerlens.replaybook.test/api'
FIELDS=['api_unit','worker_unit','database','uploads','token_file','release','install_script','artifact','operator_doc']


class Failure(RuntimeError):pass


def require(condition,message):
    if not condition:raise Failure(message)


def remote(program,args=None):
    port=int(os.environ['REPLAYBOOK_HOST_SSH_PORT'])
    key=os.environ.get('REPLAYBOOK_HOST_SSH_KEY',str(Path.home()/'.ssh/id_ed25519'))
    script='import json,os,pathlib,hashlib,sqlite3,subprocess,tarfile,time\nARGS=json.loads('+repr(json.dumps(args or {}))+')\n'+program
    result=subprocess.run(['ssh','-i',key,'-p',str(port),'-o','BatchMode=yes','-o','ConnectTimeout=5',
        '-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null','-o','LogLevel=ERROR',
        'root@127.0.0.1','python -'],input=script,text=True,capture_output=True,timeout=90)
    if result.returncode:raise Failure('Guest deployment observation failed: '+result.stderr[-1200:])
    return json.loads(result.stdout)


def request(base,path,token,body=None):
    headers={'Host':'ledgerlens.replaybook.test','Authorization':'Bearer '+token}
    req=urllib.request.Request(base+'/api'+path,data=body,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=12) as response:return response.status,response.read()
    except urllib.error.HTTPError as error:
        with error:return error.code,error.read()


def expected(raw):
    try:
        rows=list(csv.reader(io.StringIO(raw.decode())))
        if rows[0]!=['category','amount'] or len(rows)<2:raise ValueError()
        totals={}
        for category,amount in rows[1:]:
            sign=-1 if amount.startswith('-') else 1
            whole,fraction=amount.lstrip('-').split('.')
            if len(fraction)!=2:raise ValueError()
            totals[category]=totals.get(category,0)+sign*(int(whole)*100+int(fraction))
        return 'done',{'rows':len(rows)-1,'totals_cents':dict(sorted(totals.items()))}
    except (ValueError,IndexError):return 'failed',{'error':'invalid_csv'}


def record(bad=False,historical=False,running=False):
    identity=secrets.token_hex(12)
    body='wrong,columns\nno,accounting\n' if bad else 'category,amount\n'+''.join(
        f'{secrets.choice(["food","travel","office"])},{secrets.randbelow(100)}.{secrets.randbelow(100):02d}\n' for _ in range(7))
    status,result=expected(body.encode())
    return identity,{'body':body,'state':status,'result':result,'executions':0 if historical else 1,
                     'initial_state':'done' if historical else 'running' if running else 'queued'}


def inspect():
    return remote('''
p=pathlib.Path('/etc/ledgerlens/deployment.json')
print(json.dumps(json.loads(p.read_text())))
''')


def validate_handoff(meta):
    require(isinstance(meta,dict) and all(isinstance(meta.get(k),str) for k in FIELDS),'Missing deployment handoff fields')
    for key in ['api_unit','worker_unit']:
        require(re.fullmatch(r'[A-Za-z0-9_.@-]+\.service',meta[key]),'Invalid unit name')
    require(meta['api_unit']!=meta['worker_unit'],'API and worker must have independent supervisors')
    for key in FIELDS[2:]:
        value=meta[key]
        require(re.fullmatch(r'/[A-Za-z0-9_./-]+',value) and '..' not in Path(value).parts,'Unsafe deployment path')
    for key in ['database','uploads','token_file']:
        require(not any(Path(meta[key]).is_relative_to(p) for p in ['/tmp','/run','/root','/opt/ledgerlens/repo',meta['release']]),'Production state/credentials must be outside transient paths, source and release')
    require(not Path(meta['release']).is_relative_to('/opt/ledgerlens/repo'),'Deployment must use a release, not the development checkout')


def observe(meta,token):
    return remote('''
m=ARGS['meta']
def unit(name):
 pid=int(subprocess.check_output(['systemctl','show',name,'-p','MainPID','--value'],text=True))
 if pid<=0:raise RuntimeError('service has no live MainPID: '+name)
 return {'pid':pid,'uid':pathlib.Path('/proc',str(pid)).stat().st_uid,
         'cwd':os.path.realpath('/proc/'+str(pid)+'/cwd'),
         'enabled':subprocess.run(['systemctl','is-enabled',name],text=True,capture_output=True).stdout.strip()}
units={k:unit(m[k]) for k in ['api_unit','worker_unit']}
for field in ['database','uploads','token_file']:
 actual=pathlib.Path(m[field]).resolve()
 for forbidden in ['/tmp','/run','/root','/opt/ledgerlens/repo',os.path.realpath(m['release'])]:
  assert not actual.is_relative_to(forbidden),'production path resolves into transient/source/release storage'
assert not pathlib.Path(m['release']).resolve().is_relative_to('/opt/ledgerlens/repo'),'release resolves into development checkout'
secret=pathlib.Path(m['token_file'])
assert secret.read_text().strip()==ARGS['token'],'production credential changed'
assert secret.stat().st_mode & 0o007==0,'credential is world-accessible'
for unit in units.values():
 assert unit['uid']>0,'application process runs as root'
 assert unit['cwd']==os.path.realpath(m['release']),'application is not running from declared release'
 cmdline=pathlib.Path('/proc',str(unit['pid']),'cmdline').read_bytes()
 assert ARGS['token'].encode() not in cmdline,'secret leaked in process arguments'
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
assert sha('/opt/ledgerlens/repo/ledgerlens.py')==ARGS['source_sha'],'application source was modified'
assert sha(m['release']+'/ledgerlens.py')==ARGS['source_sha'],'release is not the provided application'
archive=pathlib.Path(m['artifact']);assert archive.is_file(),'release artifact missing'
source_members=0
with tarfile.open(archive,'r:gz') as package:
 for member in package.getmembers():
  assert not member.name.startswith('/') and '..' not in pathlib.PurePosixPath(member.name).parts,'unsafe archive path'
  assert member.isfile() or member.isdir(),'release archive contains links or devices'
  if member.isfile():
   assert member.size<=1048576,'unexpectedly large release member'
   content=package.extractfile(member).read()
   assert ARGS['token'].encode() not in content,'release artifact includes live credentials'
   assert not content.startswith(b'SQLite format 3'),'release artifact includes a database'
   if pathlib.PurePosixPath(member.name).name=='ledgerlens.py':
    assert hashlib.sha256(content).hexdigest()==ARGS['source_sha'],'packaged source mismatch'
    source_members+=1
assert source_members==1,'artifact must include exactly one copy of the application'
assert len(pathlib.Path(m['operator_doc']).read_text())>=100,'operator handoff missing'
assert os.access(m['install_script'],os.X_OK),'installer is not executable'
db=sqlite3.connect('file:'+m['database']+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
assert db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0]=='2','migration was not applied'
rows=[dict(row) for row in db.execute('SELECT * FROM imports ORDER BY id')]
objects={row['id']:sha(str(pathlib.Path(m['uploads'])/row['object_name'])) for row in rows}
print(json.dumps({'units':units,'rows':rows,'objects':objects}))
''',{'meta':meta,'token':token,'source_sha':hashlib.sha256((ROOT/'repo/ledgerlens.py').read_bytes()).hexdigest()})


def records_ok(state,observation):
    rows={row['id']:row for row in observation['rows']}
    require(set(rows)==set(state['records']),'Historical/new records were lost or unexpected work was inserted')
    for identity,known in state['records'].items():
        row=rows[identity]
        require(row['state']==known['state'],'Work has not reached its correct terminal state: '+identity)
        require(json.loads(row['result'])==known['result'],'Wrong aggregate or error classification: '+identity)
        require(row['executions']==known['executions'],'Work was replayed or silently skipped: '+identity)
        digest=hashlib.sha256(known['body'].encode()).hexdigest()
        require(row['digest']==digest and observation['objects'][identity]==digest,'Original upload changed: '+identity)


def wait_for(check,timeout=35):
    deadline=time.monotonic()+timeout
    while True:
        try:return check()
        except (Failure,OSError) as error:
            if time.monotonic()>=deadline:raise error
            time.sleep(.2)


def control(meta,operation):
    return remote('''
m=ARGS['meta'];operation=ARGS['operation']
if operation=='install':
 subprocess.run([m['install_script']],check=True,stdout=subprocess.DEVNULL,timeout=60)
elif operation=='stop-worker':subprocess.run(['systemctl','stop',m['worker_unit']],check=True)
elif operation=='crash-worker':
 subprocess.run(['systemctl','start',m['worker_unit']],check=True)
 pid=int(subprocess.check_output(['systemctl','show',m['worker_unit'],'-p','MainPID','--value'],text=True))
 assert pid>0
 os.kill(pid,9)
 print(json.dumps({'old_pid':pid}));raise SystemExit()
else:subprocess.run(['systemctl','restart',m['api_unit'],m['worker_unit']],check=True)
print('{}')
''',{'meta':meta,'operation':operation})


def run(phase,base,state_dir):
    state_dir.mkdir(parents=True,exist_ok=True);state_path=state_dir/'deployment-contract.json'
    if phase=='preflight':
        records=dict([record(historical=True),record(),record(running=True),record(bad=True)])
        token=secrets.token_hex(24)
        remote('''
root=pathlib.Path('/srv/ledgerlens-handoff');(root/'uploads').mkdir(parents=True,exist_ok=False)
root.chmod(0o700)
db=sqlite3.connect(root/'ledger.sqlite3')
db.executescript("CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL); INSERT INTO metadata VALUES('schema','1'); CREATE TABLE imports(id TEXT PRIMARY KEY,object_name TEXT NOT NULL,digest TEXT NOT NULL,state TEXT NOT NULL,result TEXT,created_ns INTEGER NOT NULL);")
for identity,record in ARGS['records'].items():
 raw=record['body'].encode();(root/'uploads'/(identity+'.csv')).write_bytes(raw)
 db.execute('INSERT INTO imports VALUES(?,?,?,?,?,?)',(identity,identity+'.csv',hashlib.sha256(raw).hexdigest(),record['initial_state'],json.dumps(record['result']) if record['executions']==0 else None,time.time_ns()))
db.commit();db.close();(root/'token').write_text(ARGS['token']+'\\n');(root/'token').chmod(0o600)
print('{}')
''',{'records':records,'token':token})
        state={'records':records,'token':token};state_path.write_text(json.dumps(state)+'\n')
        status,_=request(base,'/ready',token)
        require(status==503,'Application unexpectedly deployed before the task')
        return
    state=json.loads(state_path.read_text());meta=inspect();validate_handoff(meta)
    def ready():
        status,raw=request(base,'/ready',state['token'])
        require(status==200 and json.loads(raw).get('ready') is True,'Deployment is not ready')
    wait_for(ready)
    wait_for(lambda:records_ok(state,observe(meta,state['token'])))
    status,raw=request(base,'/meta',state['token']);observation=observe(meta,state['token'])
    require(status==200 and json.loads(raw)=={'version':'0.4.0','pid':observation['units']['api_unit']['pid']},'Public endpoint is not the declared application process')
    require(request(base,'/meta','incorrect-token')[0]==401,'Authentication bypass')
    probe=secrets.token_hex(12)
    require(request(base,'/imports/'+probe,'incorrect-token',b'category,amount\nfood,1.00\n')[0]==401,'Unauthenticated upload accepted')
    first=next(iter(state['records']))
    require(request(base,'/imports/'+first+'/source','incorrect-token')[0]==401,'Unauthenticated download accepted')
    # Seed work while the worker is stopped, then require its supervisor to
    # recover automatically from SIGKILL. Never accept a green health response
    # as proof of queue recovery.
    if phase=='immediate':control(meta,'stop-worker')
    fresh=dict([record(),record(),record(bad=True)])
    state['records'].update(fresh);state_path.write_text(json.dumps(state)+'\n')
    for identity,known in fresh.items():
        for _ in range(2):require(request(base,'/imports/'+identity,state['token'],known['body'].encode())[0]==202,'Import/retry was not accepted')
        require(request(base,'/imports/'+identity,state['token'],b'category,amount\nother,0.01\n')[0]==409,'Idempotency conflict was not rejected')
    if phase=='immediate':
        previous=control(meta,'crash-worker')['old_pid']
        wait_for(lambda:require(observe(meta,state['token'])['units']['worker_unit']['pid']!=previous,'Worker did not restart'),timeout=25)
    wait_for(ready)
    wait_for(lambda:records_ok(state,observe(meta,state['token'])))
    for identity,known in state['records'].items():
        status,raw=request(base,'/imports/'+identity,state['token']);body=json.loads(raw)
        require(status==200 and body['state']==known['state'] and body['result']==known['result'],'Public workflow mismatch')
        require(body['source_url']==PUBLIC+'/imports/'+identity+'/source','Application generates broken public links')
        require(request(base,'/imports/'+identity+'/source',state['token'])==(200,known['body'].encode()),'Download differs from the accepted upload')
    if phase=='immediate':control(meta,'install')
    control(meta,'restart')
    wait_for(ready);wait_for(lambda:records_ok(state,observe(meta,state['token'])))
    print(json.dumps({'phase':phase,'passed':True,'preserved_imports':len(state['records'])}))


if __name__=='__main__':
    phase,base,state=sys.argv[1:];directory=Path(state)
    try:run(phase,base,directory)
    except Exception as error:
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'phase-failure.json').write_text(json.dumps({'phase':phase,'category':'deployment_contract_failed','message':str(error)})+'\n')
        print(str(error),file=sys.stderr);raise SystemExit(1)
