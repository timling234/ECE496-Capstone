"""FR-1/FR-7: app-owned polling and live operations control; independent code."""
import json
import queue
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from run_polling import load_sources
from .polling import poll_due, PollingSource
from .store_poc import ROOT


class AppRuntime:
    def __init__(self, db, config_path=None, loader=load_sources):
        self.db=Path(db)
        self.config_path=Path(config_path or self.db.parent/'polling.local.json')
        self.loader=loader
        self.stop_event=threading.Event()
        self.wake=threading.Event()
        self.commands=queue.Queue()
        self.lock=threading.RLock()
        self.poll_lock=threading.RLock()
        self.thread=None
        self.error=None
        self.active=None
        self.previous={}
        self.pending=set()
        if not self.config_path.exists():
            config=json.loads((ROOT/'config'/'polling.example.json').read_text())
            for item in config['sources']:
                if item['platform']!='linkedin':item['interval_seconds']=1800
            self.save_config(config,validate=False)
        with closing(sqlite3.connect(self.db)) as conn:
            poll_due(conn,[],time.time())

    def read_config(self):
        with self.lock:return json.loads(self.config_path.read_text(encoding='utf-8-sig'))

    def save_config(self, config, validate=True):
        # Server-written fixed path, no secret contents accepted from browser.
        with self.lock:
            self.config_path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.config_path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(config,indent=2),encoding='utf-8')
            try:
                if validate:self.loader(tmp)
                tmp.replace(self.config_path)
            finally:
                tmp.unlink(missing_ok=True)
        self.wake.set()

    def sources(self):
        with self.lock:return self.loader(self.config_path)

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        self.thread=threading.Thread(target=self._loop,name='asap-polling',daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set();self.wake.set()
        if self.thread:self.thread.join(timeout=35)

    @property
    def running(self):return bool(self.thread and self.thread.is_alive())

    def request_fetch(self, platform):
        if platform not in ('x','bluesky'):raise ValueError('Only configured X/Bluesky sources can be fetched')
        if not any(s.provider.platform==platform for s in self.sources()):raise ValueError('Source not configured')
        with self.lock:
            if platform in self.pending or self.active==platform:return False
            self.pending.add(platform)
        self.commands.put(platform);self.wake.set();return True

    def fetch_now(self, platform):
        # Same serialized pipeline for development E2E; never auto-approves.
        with self.poll_lock:
            source=next((s for s in self.sources() if s.provider.platform==platform),None)
            if source is None:raise ValueError('Source not configured')
            source=PollingSource(source.provider,source.interval_seconds or 1800,True)
            self.active=platform
            try:
                with closing(sqlite3.connect(self.db,timeout=15)) as conn:
                    return poll_due(conn,[source],time.time(),force=True)[0]
            finally:self.active=None

    def tick(self, now=None):
        now=time.time() if now is None else now
        with self.poll_lock:
            sources=self.sources()
            with closing(sqlite3.connect(self.db,timeout=15)) as conn:
                for source in sources:
                    key=source.provider.key; current=(source.enabled,source.interval_seconds)
                    old=self.previous.get(key)
                    if old and old!=current and source.enabled:
                        row=conn.execute('SELECT last_attempt_at,next_poll_at,error_code FROM source_poll_state WHERE source_key=?',(key,)).fetchone()
                        due=0 if not old[0] else (row[0]+source.interval_seconds if row and row[0] is not None else 0)
                        if row and row[2]==429:due=max(due,row[1])
                        with conn:conn.execute('UPDATE source_poll_state SET next_poll_at=? WHERE source_key=?',(due,key))
                    self.previous[key]=current
                if len({source.provider.key for source in sources})!=len(sources):raise ValueError('Duplicate configured source')
                outcomes=[]
                for source in sources:
                    self.active=source.provider.platform if source.enabled else None
                    try:outcomes.extend(poll_due(conn,[source],now))
                    finally:self.active=None
            self.error=None
            return outcomes

    def snapshot(self):
        # Config lock is held only for reading, not waiting for network fetch.
        config=self.read_config()
        with closing(sqlite3.connect(self.db,timeout=15)) as conn:
            cursor=conn.execute('SELECT * FROM source_poll_state')
            columns=[d[0] for d in cursor.description]
            states={row[0]:dict(zip(columns,row)) for row in cursor}
        rows=[]
        for source in config['sources']:
            platform=source['platform'];key=platform+':'+source.get('account','')
            row=dict(source);row.update(states.get(key,{}))
            row['status']=('Pending Access' if platform=='linkedin' else 'Fetching' if self.active==platform
                else 'Queued' if platform in self.pending else 'Error' if row.get('error_type')
                else 'Disabled' if not source.get('enabled') else 'Healthy' if row.get('last_success_at') is not None else 'Waiting')
            rows.append(row)
        return rows

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                while not self.commands.empty():
                    platform=self.commands.get_nowait()
                    try:self.fetch_now(platform)
                    finally:
                        with self.lock:self.pending.discard(platform)
                if not self.stop_event.is_set():self.tick()
            except Exception as error:self.error=type(error).__name__
            self.wake.wait(0.5);self.wake.clear()
