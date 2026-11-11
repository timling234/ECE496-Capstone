"""One server-selected directory per account: independent Store, config and grants."""
from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
import threading
from run_polling import load_sources
from .app_runtime import AppRuntime
from .linkedin import Credentials, OAuth
from .store_poc import store, process_stored
from .web_editorial import initialize


@dataclass
class Workspace:
    db: Path
    runtime: object
    oauth: object


class Workspaces:
    def __init__(self, root, accounts, default, start_workers=False):
        self.root = Path(root)
        self.accounts = accounts
        self.default = default
        self.start_workers = start_workers
        self.lock = threading.RLock()
        self.active = {}

    def get(self, uid):
        if not re.fullmatch('[0-9a-f]{32}', uid) or not self.accounts.user(uid):
            raise ValueError('Unknown workspace')
        with self.lock:
            if uid in self.active:
                return self.active[uid]
            directory = self.root / uid
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            db = directory / 'asap.sqlite3'
            with closing(sqlite3.connect(db)) as conn:
                store(conn, []); process_stored(conn); conn.commit(); initialize(conn); conn.commit()
            config = directory / 'polling.local.json'
            if not config.exists():
                config.write_text(json.dumps({'sources': [{'platform': 'linkedin', 'enabled': False}]}))
            def loader(path):
                # Never borrow the original administrator's X token file.
                data = json.loads(path.read_text())
                for item in data['sources']:
                    if item['platform'] == 'x' and not item.get('draft') and not item.get('connection_id') and item.get('token_file') != str(directory / 'x-token.txt'):
                        # Browser forms do not accept filesystem paths. Reject instead of
                        # silently defaulting to a credential in the repository root.
                        raise ValueError('X requires a dedicated workspace token configured by the server administrator.')
                return load_sources(path)
            runtime = AppRuntime(db, config, loader=loader)
            workspace = Workspace(db, runtime, OAuth(Credentials(directory / 'linkedin_credentials')))
            self.active[uid] = workspace
            if self.start_workers:
                runtime.start()
            return workspace

    def restore(self):
        for uid in self.accounts.ids():
            self.get(uid)

    def stop(self):
        for workspace in list(self.active.values()):
            workspace.runtime.stop()
