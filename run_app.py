"""FR-7/FR-9: simple local launch, existing SQLite content and integrated source polling."""
from contextlib import closing
import ssl
import threading
from http.server import ThreadingHTTPServer
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
    server=make_server(args.db,password,host=args.host,port=args.port,runtime=runtime,dev_enabled=os.environ.get('ASAP_DEV_TOOLS')=='1')
    https_server=None
    if args.https_port:
        if not args.tls_cert or not args.tls_key:parser.error('HTTPS requires --tls-cert and --tls-key')
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.tls_cert,args.tls_key)
        https_server=ThreadingHTTPServer((args.host,args.https_port),server.RequestHandlerClass)
        https_server.socket=context.wrap_socket(https_server.socket,server_side=True)
        threading.Thread(target=https_server.serve_forever,name='asap-https',daemon=True).start()
        print(f'HTTPS Admin: https://localhost:{https_server.server_port}/admin')
    runtime.start()
    print(f'Admin:       http://localhost:{server.server_port}/admin')
    print(f'Public Feed: http://localhost:{server.server_port}/feed')
    print('Polling worker started. Enabled sources make live API requests; Admin controls take effect at runtime. Ctrl+C to stop.')
    print('Development tools: '+('enabled' if server.devtools.enabled else 'disabled'))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        runtime.stop();server.server_close()
        if https_server:https_server.shutdown();https_server.server_close()

if __name__=='__main__':main()
