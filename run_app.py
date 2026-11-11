"""FR-7/FR-9: simple local launch, existing SQLite content and integrated source polling."""
from contextlib import closing
import argparse
import getpass
import os
import sqlite3
from pathlib import Path
from src.store_poc import ROOT, store, process_stored
from src.web_editorial import initialize
from src.app_runtime import AppRuntime


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'.tmp'/'store_poc.sqlite3')
    parser.add_argument('--config',type=Path,help='Optional polling config; default is alongside the database')
    parser.add_argument('--configure-bluesky-test',action='store_true',help='Save explicit test-account credentials locally using hidden input')
    parser.add_argument('--configure-linkedin',action='store_true',help='Configure LinkedIn application credentials locally using hidden input')
    parser.add_argument('--host',default='127.0.0.1',help='Container: 0.0.0.0; local default: loopback')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--https-port',type=int,help='Optional HTTPS listener sharing the same sessions and runtime')
    parser.add_argument('--tls-cert',type=Path)
    parser.add_argument('--tls-key',type=Path)
    args=parser.parse_args()
    if args.configure_linkedin:
        import json
        from src.linkedin import validate_settings
        values=dict(client_id=input('LinkedIn application Client ID: ').strip(),
                    client_secret=getpass.getpass('LinkedIn Client Secret (hidden): ').strip(),
                    redirect_uri=input('Registered callback URL (e.g. https://localhost:5171/linkedin/callback): ').strip())
        try:validate_settings(values)
        except ValueError as error:parser.error(str(error))
        path=ROOT/'.tmp'/'linkedin-app.json';path.parent.mkdir(parents=True,exist_ok=True)
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w',encoding='utf-8') as stream:
            json.dump(values,stream)
        print('LinkedIn server configuration saved locally. Register the exact callback URL in LinkedIn Developers before connecting.')
        return
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
    from src.portal import create_app
    from waitress import serve
    if args.https_port:
        parser.error('Use the HTTPS reverse proxy for the Flask portal; direct TLS flags are no longer supported.')
    app=create_app(args.db,password,runtime=runtime,start_workers=True,
                   trust_proxy=os.environ.get('ASAP_TRUST_PROXY')=='1')
    runtime.start()
    print(f'ASAP portal: http://{args.host}:{args.port}/')
    print('Flask + Waitress, one process; workspace polling starts only for explicitly enabled sources.')
    try:
        serve(app,host=args.host,port=args.port,threads=8,clear_untrusted_proxy_headers=os.environ.get('ASAP_TRUST_PROXY')!='1',
              max_request_body_size=16384,channel_timeout=30)
    except KeyboardInterrupt:pass
    finally:
        app.extensions['workspaces'].stop()
        runtime.stop()

if __name__=='__main__':main()
