"""Workspace preferences and shared, bounded local Ollama model management."""
from contextlib import closing
import json
import sqlite3
import threading
import time
import requests
from .review_ai import POLICY,LEGACY_POLICY,PREVIOUS_POLICY,TEST_DECLARATION_POLICY,PLACEHOLDER_POLICY,LocalModel

CATALOG={'gemma4:e2b-it-qat':'Gemma 4 E2B · lightweight', 'qwen3:4b':'Qwen 3 4B · compact','qwen3:8b':'Qwen 3 8B · balanced'}


def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS ai_settings (id INTEGER PRIMARY KEY CHECK(id=1), model TEXT NOT NULL,policy TEXT NOT NULL,auto_approve INTEGER NOT NULL,auto_reject INTEGER NOT NULL,batch_limit INTEGER NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS ai_queue_preferences (id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS ai_model_downloads (id INTEGER PRIMARY KEY,model TEXT NOT NULL,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,error TEXT,created_at REAL NOT NULL)')


def settings(conn,default_model=''):
    initialize(conn)
    row=conn.execute('SELECT model,policy,auto_approve,auto_reject,batch_limit FROM ai_settings WHERE id=1').fetchone()
    result=dict(zip(('model','policy','auto_approve','auto_reject','batch_limit'),row or (default_model,POLICY,1,1,20)))
    if result['policy'] in (LEGACY_POLICY,PREVIOUS_POLICY,TEST_DECLARATION_POLICY,PLACEHOLDER_POLICY):result['policy']=POLICY
    row=conn.execute('SELECT enabled FROM ai_queue_preferences WHERE id=1').fetchone()
    result['always_review']=bool(row and row[0])
    return result


def save(conn,values,installed):
    model=values.get('model','')
    if model not in installed:raise ValueError('Choose an installed local model. Download it first if needed.')
    policy=values.get('policy','').strip()
    limit=int(values.get('batch_limit') or 20)
    if not 10<=len(policy)<=4000:raise ValueError('Review policy must contain 10–4000 characters')
    if not 1<=limit<=50:raise ValueError('Batch limit must be 1–50 posts')
    with conn:conn.execute('INSERT OR REPLACE INTO ai_settings VALUES (1,?,?,?,?,?)',(model,policy,int(values.get('auto_approve')=='on'),int(values.get('auto_reject')=='on'),limit))


class ModelManager:
    def __init__(self,model=None):
        self.local=model or LocalModel()
        self.lock=threading.Lock();self.download_lock=threading.Lock();self.cache={};self.cached_at=0

    def installed(self,force=False):
        with self.lock:
            if not force and self.cached_at>time.time()-30:return dict(self.cache)
            if not self.local.ready:return {}
            with requests.Session() as session:
                session.trust_env=False
                with session.get(self.local.url+'/api/tags',timeout=(3,5),allow_redirects=False,stream=True) as response:
                    if response.status_code!=200:raise ValueError('Local model service unavailable')
                    raw=bytearray()
                    for chunk in response.iter_content(8192):
                        raw.extend(chunk)
                        if len(raw)>1048576:raise ValueError('Invalid local model list')
                    data=json.loads(raw)
            result={}
            for item in data.get('models',[]):
                name=item.get('name','')
                if isinstance(name,str) and 1<=len(name)<=150 and 'cloud' not in name.lower() and not item.get('remote_model') and not item.get('remote_host'):
                    result[name]=max(0,int(item.get('size',0)))
            self.cache=result;self.cached_at=time.time()
            return dict(result)

    def recover(self,db):
        with closing(sqlite3.connect(db)) as conn:
            initialize(conn)
            conn.execute("UPDATE ai_model_downloads SET status='error',error='Service restarted. Retry the download.' WHERE status='running'");conn.commit()

    def download(self,db,name):
        if name not in CATALOG:raise ValueError('Choose a model from the download list')
        if name in self.installed():return None
        if not self.download_lock.acquire(blocking=False):raise ValueError('A model download is already running on Server')
        try:
            with closing(sqlite3.connect(db)) as conn:
                initialize(conn)
                job=conn.execute("INSERT INTO ai_model_downloads(model,status,created_at) VALUES (?,'running',?)",(name,time.time())).lastrowid;conn.commit()
            threading.Thread(target=self._pull,args=(db,job,name),daemon=True,name='asap-model-download').start()
            return job
        except Exception:
            self.download_lock.release();raise

    def _pull(self,db,job,name):
        try:
            started=time.monotonic();success=False
            with requests.Session() as session:
                session.trust_env=False
                with session.post(self.local.url+'/api/pull',json={'model':name,'stream':True},timeout=(5,60),allow_redirects=False,stream=True) as response:
                    if response.status_code!=200:raise ValueError('Model download failed')
                    last=-1
                    for line in response.iter_lines(chunk_size=1024):
                        if time.monotonic()-started>3600 or len(line)>65536:raise ValueError('Model download limit reached')
                        if not line:continue
                        event=json.loads(line)
                        if event.get('error'):raise ValueError('Model download failed')
                        progress=min(99,max(0,int(100*event.get('completed',0)/max(1,event.get('total',1)))))
                        if event.get('status')=='success':success=True;progress=100
                        if progress!=last:
                            with closing(sqlite3.connect(db,timeout=15)) as conn:
                                conn.execute('UPDATE ai_model_downloads SET progress=? WHERE id=?',(progress,job));conn.commit()
                            last=progress
            if not success or name not in self.installed(force=True):raise ValueError('Downloaded model could not be verified')
            with closing(sqlite3.connect(db,timeout=15)) as conn:
                conn.execute("UPDATE ai_model_downloads SET status='complete',progress=100 WHERE id=?",(job,));conn.commit()
        except Exception:
            with closing(sqlite3.connect(db,timeout=15)) as conn:
                conn.execute("UPDATE ai_model_downloads SET status='error',error='Download did not complete. Check Server storage/network and retry manually.' WHERE id=?",(job,));conn.commit()
        finally:self.download_lock.release()
