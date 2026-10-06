"""FR-7/FR-9: simple local launch, existing SQLite content and integrated source polling."""
from contextlib import closing
import argparse
import getpass
import os
import sqlite3
from pathlib import Path
from src.store_poc import ROOT, store, process_stored
from src.web_editorial import initialize
from src.web_app import make_server
from src.app_runtime import AppRuntime


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'.tmp'/'store_poc.sqlite3')
    parser.add_argument('--config',type=Path,help='Optional polling config; default is alongside the database')
    parser.add_argument('--configure-bluesky-test',action='store_true',help='Save explicit test-account credentials locally using hidden input')
    parser.add_argument('--port',type=int,default=5000)
    args=parser.parse_args()
    if args.configure_bluesky_test:
        account=input('Explicit Bluesky TEST account handle: ').strip()
        if not account.endswith('.bsky.social'):parser.error('Use an explicit test-account handle')
        app_password=getpass.getpass('Bluesky app password (hidden; saved only in ignored local config): ')
        if not app_password:parser.error('App password required')
        import json
        path=ROOT/'.tmp'/'dev_credentials.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'bluesky_test_account':account,'bluesky_app_password':app_password}),encoding='utf-8')
        print('Local ignored test credentials saved. Enable ASAP_DEV_TOOLS=1 when running the app.')
        return
    password=os.environ.get('ASAP_ADMIN_PASSWORD')
    if not password:
        password=getpass.getpass('Admin password for this run (hidden; not saved): ')
        if password:os.environ['ASAP_ADMIN_PASSWORD']=password
    if not password:parser.error('An admin password is required')
    args.db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(args.db)) as conn:
        store(conn,[]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
    runtime=AppRuntime(args.db,args.config)
    server=make_server(args.db,password,port=args.port,runtime=runtime,dev_enabled=os.environ.get('ASAP_DEV_TOOLS')=='1')
    runtime.start()
    print(f'Admin:       http://localhost:{server.server_port}/admin')
    print(f'Public Feed: http://localhost:{server.server_port}/feed')
    print('Polling worker started. Enabled sources make live API requests; Admin controls take effect at runtime. Ctrl+C to stop.')
    print('Development tools: '+('enabled' if server.devtools.enabled else 'disabled'))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:runtime.stop();server.server_close()

if __name__=='__main__':main()
