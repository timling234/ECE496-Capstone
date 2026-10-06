"""FR-10: allowlisted development jobs and explicit Bluesky test-account tooling.
Protocol references: official Bluesky createSession/createRecord documentation.
No external reference implementation copied.
"""
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from .store_poc import ROOT

TESTS={
 'all':('All Regression Tests','FR-1–11',''),
 'store':('Normalization / Storage','FR-2/3','test_store_poc.py'),
 'filter':('Relevance Filtering','FR-4','test_relevance.py'),
 'duplicates':('Duplicate Detection','FR-5','test_duplicates.py'),
 'editorial':('Editorial Workflow','FR-6/7','test_editorial.py'),
 'web':('Admin / Public Renderer','FR-6/7/9/11','test_web_app.py'),
 'polling':('Provider / Scheduler','FR-1','test_polling.py'),
 'operations':('Operations / Dev Tools','FR-1/7/10','test_operations.py'),
 'entrypoints':('Verification Entry Points','FR-10','test_verification_entrypoints.py'),
}
LIVE={'live-bluesky':('Bluesky Fetch','Live API request'),
      'live-x':('X Fetch','Live API request; may use API credits'),
      'publish-bluesky':('Publish Bluesky Test Post','Creates a real public test post'),
      'e2e-bluesky':('Bluesky Candidate E2E','Publishes a real test post; fetches and verifies pending candidacy')}


def credentials():
    path=ROOT/'.tmp'/'dev_credentials.json'
    local=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return (os.environ.get('ASAP_BSKY_TEST_ACCOUNT') or local.get('bluesky_test_account',''),
            os.environ.get('ASAP_BSKY_APP_PASSWORD') or local.get('bluesky_app_password',''))


def post_json(url, data, token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    with urlopen(Request(url,data=json.dumps(data).encode(),headers=headers),timeout=30) as response:
        return json.load(response)


# FR-10: Explicit development-only posting target, not a retrieval-source inference
# REF-BSKY-POST-01: official session/record protocol (independent implementation)
class BlueskyTestPublisher:
    def __init__(self, transport=post_json):
        self.transport=transport
        self.session=None
        self.expires=0

    def publish(self,text):
        account,password=credentials()
        if not account or not password:raise ValueError('Test account credentials not configured locally')
        if not account.endswith('.bsky.social') or '@' in account:raise ValueError('An explicit Bluesky test handle is required')
        if not text.strip() or len(text)>300:raise ValueError('Test text must contain 1–300 characters')
        if not self.session or self.expires<time.time() or self.session['handle'].lower()!=account.lower():
            session=self.transport('https://bsky.social/xrpc/com.atproto.server.createSession',{'identifier':account,'password':password})
            if session.get('handle','').lower()!=account.lower() or not session.get('did','').startswith('did:'):
                raise ValueError('Authenticated identity does not match the configured test account')
            self.session=session;self.expires=time.time()+300
        created=datetime.now(timezone.utc).isoformat()
        result=self.transport('https://bsky.social/xrpc/com.atproto.repo.createRecord',
            {'repo':self.session['did'],'collection':'app.bsky.feed.post',
             'record':{'$type':'app.bsky.feed.post','text':text.strip(),'createdAt':created}},self.session['accessJwt'])
        uri=result.get('uri','')
        if not uri.startswith('at://'+self.session['did']+'/app.bsky.feed.post/'):
            raise ValueError('Unexpected test post identity')
        return {'uri':uri,'timestamp':created,'url':'https://bsky.app/profile/'+account+'/post/'+uri.rsplit('/',1)[-1]}


# FR-10: Allowlisted executable tests with persisted/redacted results
class DevTools:
    def __init__(self,runtime,enabled=False,publisher=None,timeout=180):
        self.runtime=runtime;self.db=runtime.db;self.enabled=enabled
        self.publisher=publisher or BlueskyTestPublisher();self.timeout=timeout
        self.lock=threading.Lock();self.active=False;self.thread=None
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS dev_runs (id TEXT PRIMARY KEY,test_id TEXT,status TEXT,started_at REAL,duration REAL,output TEXT)')
            conn.execute("UPDATE dev_runs SET status='INTERRUPTED',output='Application restarted before this task completed' WHERE status='RUNNING'")
            conn.commit()

    def redact(self,output):
        secrets=[os.environ.get(k,'') for k in os.environ if any(t in k.upper() for t in ('PASSWORD','SECRET','TOKEN'))]
        try:secrets.append(credentials()[1])
        except Exception:pass
        try:
            from .store_poc import X_TOKEN
            if X_TOKEN.exists():secrets.append(X_TOKEN.read_text(encoding='utf-8-sig').strip())
        except OSError:pass
        try:
            for source in self.runtime.sources():
                token_path=getattr(source.provider,'token_file',None)
                if token_path and token_path.exists():secrets.append(token_path.read_text(encoding='utf-8-sig').strip())
        except Exception:pass
        for secret in secrets:
            if secret:output=output.replace(secret,'[REDACTED]')
        return ('[Output truncated to last 16000 characters]\n'+output[-16000:]) if len(output)>16000 else output

    def history(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return [dict(zip(('id','test_id','status','started_at','duration','output'),row))
                for row in conn.execute('SELECT * FROM dev_runs ORDER BY started_at DESC LIMIT 30')]

    def submit(self,test_id,text=''):
        if not self.enabled:raise ValueError('Development tools are disabled')
        if test_id not in TESTS and test_id not in LIVE:raise ValueError('Unknown allowlisted test ID')
        if test_id in ('publish-bluesky','e2e-bluesky'):
            account,password=credentials()
            if not account or not password:raise ValueError('Configure the explicit test account and app password locally first')
            if test_id=='publish-bluesky' and (not text.strip() or len(text)>300):raise ValueError('Test text must contain 1–300 characters')
            if test_id=='e2e-bluesky' and not any(s.provider.platform=='bluesky' and s.provider.account==account for s in self.runtime.sources()):
                raise ValueError('E2E requires the configured retrieval source to match the explicit test account')
        with self.lock:
            if self.active:raise ValueError('Another development task is running; wait for completion')
            self.active=True
        identity=str(uuid.uuid4())
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('INSERT INTO dev_runs VALUES (?,?,?, ?,0,?)',(identity,test_id,'RUNNING',time.time(),''));conn.commit()
        self.thread=threading.Thread(target=self._run,args=(identity,test_id,text),name='asap-development',daemon=True)
        self.thread.start();return identity

    def _run(self,identity,test_id,text):
        start=time.monotonic();status='PASS';output=''
        try:
            if test_id in TESTS:
                pattern=TESTS[test_id][2]
                command=([sys.executable,str(ROOT/'run_tests.py')] if not pattern else
                    [sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p',pattern,'-v'])
                # No shell or browser-supplied command/path; credentials removed from child env.
                env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ('PASSWORD','TOKEN','SECRET'))}
                env['ASAP_DEV_TOOLS']='0';env['PYTHONIOENCODING']='utf-8'
                result=subprocess.run(command,cwd=ROOT,env=env,shell=False,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=self.timeout)
                output=result.stdout+result.stderr
                if result.returncode:status='FAIL'
            elif test_id.startswith('live-'):
                output=json.dumps(self.runtime.fetch_now(test_id.removeprefix('live-')))
                if json.loads(output)['status']!='ok':status='FAIL'
            else:
                if test_id=='e2e-bluesky':text='ASAP E2E TEST '+datetime.now(timezone.utc).isoformat()+' '+str(uuid.uuid4())
                result=self.publisher.publish(text)
                output=json.dumps(result)
                if test_id=='e2e-bluesky':
                    deadline=time.monotonic()+60;found=False
                    while time.monotonic()<deadline:
                        outcome=self.runtime.fetch_now('bluesky')
                        with closing(sqlite3.connect(self.db)) as conn:
                            row=conn.execute("SELECT p.text,r.status FROM posts p JOIN relevance r USING(platform,post_id) WHERE p.platform='bluesky' AND p.post_id=?",(result['uri'],)).fetchone()
                        if row==(text,'candidate'):found=True;break
                        if outcome.get('status')=='error':break
                        time.sleep(2)
                    output+='\n'+('PASS: unique post stored as review candidate; no automatic approval.' if found else 'FAIL: candidate not visible within 60 seconds; indexing may be delayed.')
                    if not found:status='FAIL'
        except subprocess.TimeoutExpired as error:
            status='TIMEOUT';output='Regression timeout after '+str(self.timeout)+' seconds. '
            partial=error.stdout or b''
            output+=partial.decode('utf-8',errors='replace') if isinstance(partial,bytes) else partial
        except Exception as error:
            # Provider exception messages and session bodies can contain secrets.
            status='FAIL';output='Task failed ('+type(error).__name__+'). Check local configuration/provider status.'
        finally:
            with closing(sqlite3.connect(self.db,timeout=15)) as conn:
                conn.execute('UPDATE dev_runs SET status=?,duration=?,output=? WHERE id=?',
                    (status,time.monotonic()-start,self.redact(output),identity));conn.commit()
            with self.lock:self.active=False
