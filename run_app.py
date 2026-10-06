"""FR-7/FR-9: simple local launch, existing SQLite content, no live fetch."""
from contextlib import closing
import argparse
import getpass
import os
import sqlite3
from pathlib import Path
from src.store_poc import ROOT, store, process_stored
from src.web_editorial import initialize
from src.web_app import make_server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'.tmp'/'store_poc.sqlite3')
    parser.add_argument('--port',type=int,default=5000)
    args=parser.parse_args()
    password=os.environ.get('ASAP_ADMIN_PASSWORD')
    if not password:
        password=getpass.getpass('Admin password for this run (hidden; not saved): ')
        if password:os.environ['ASAP_ADMIN_PASSWORD']=password
    if not password:parser.error('An admin password is required')
    args.db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(args.db)) as conn:
        store(conn,[]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
    server=make_server(args.db,password,port=args.port)
    print(f'Admin:       http://localhost:{args.port}/admin')
    print(f'Public Feed: http://localhost:{args.port}/feed')
    print('Local-only server. Existing SQLite posts; no API requests. Ctrl+C to stop.')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
