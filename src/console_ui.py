"""FR-7/FR-10: compact operations console, no external design code."""
import json
from datetime import datetime, timezone
from .dev_tools import TESTS, LIVE, credentials

STYLE="""
body{max-width:none;margin:0;padding:0;font:14px system-ui;background:#edf0f3;color:#253240}
h1{font-size:21px;margin:0}h2{font-size:17px;margin:0 0 12px}h3{font-size:15px}header{background:#192b3d;color:white;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}
.layout{display:grid;grid-template-columns:205px 1fr;min-height:calc(100vh - 58px)}aside{background:#23394d;padding:16px 0}aside a{display:block;color:#dce5ed;text-decoration:none;padding:11px 20px}aside a.active{background:#315875;border-left:3px solid #80bded;padding-left:17px}main{padding:20px;min-width:0}a{color:#205a8b}article,.panel{border:1px solid #ccd5df;border-radius:4px;background:white;padding:14px;margin:0 0 14px}article p{margin:8px 0}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;background:#f2f5f7;color:#4c5d6d}th,td{padding:9px;border-bottom:1px solid #dde3e9;vertical-align:top}button{font-size:12px;padding:7px 11px;background:#2d628c;border-radius:3px}form{margin:3px;display:inline-block}input,textarea{font:13px system-ui;padding:6px;max-width:100%;box-sizing:border-box}input[type=number]{width:100px}textarea{width:460px}small{font-size:12px;color:#5b6c7e}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172b3d;color:#d9e5ee;padding:12px;max-height:340px;overflow:auto}.badge{display:inline-block;padding:3px 7px;background:#e1e7ee;border-radius:3px;font-size:12px;font-weight:600}.good{background:#d8eee0;color:#21613d}.bad{background:#f8dfe0;color:#93272d}.warn{background:#fff0cf;color:#865c0c}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}.metric{background:white;border:1px solid #ccd5df;padding:12px}.metric strong{display:block;font-size:23px;margin-top:4px}.notice{padding:10px;background:#fff0cf;border-left:3px solid #b88a29;margin-bottom:14px}.row{display:flex;gap:14px;flex-wrap:wrap}.content{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%;max-height:180px}@media(max-width:850px){.layout{grid-template-columns:1fr}aside{display:flex;flex-wrap:wrap;padding:0}aside a{padding:9px}.metrics{grid-template-columns:repeat(2,1fr)}main{padding:10px}.scroll{overflow:auto}}
"""


def stamp(value):
    return datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if value is not None else 'Never'


def render_console(posts,history,settings,config,session,view,esc,card,runtime=None,devtools=None,notice=''):
    csrf=session['csrf']
    def form(route,fields,label,disabled=False):
        return '<form method="post" action="'+route+'"><input type="hidden" name="csrf" value="'+csrf+'">'+''.join('<input type="hidden" name="'+esc(k)+'" value="'+esc(v)+'">' for k,v in fields.items())+'<button'+(' disabled' if disabled else '')+'>'+esc(label)+'</button></form>'
    def badge(value):
        cls='good' if value in ('Healthy','Running','Connected','PASS') else 'bad' if value in ('Error','FAIL','TIMEOUT') else 'warn' if value in ('Pending Access','Waiting','RUNNING','Fetching','Queued') else ''
        return '<span class="badge '+cls+'">'+esc(value)+'</span>'
    navigation=[('dashboard','Dashboard'),('pending','Review Queue'),('approved','Published'),('rejected','Rejected'),('duplicates','Duplicate Groups'),('sources','Sources'),('testing','Testing / Development'),('settings','Settings')]
    body='<header><h1>ASAP Admin</h1><span>Operations console · '+form('/logout',{},'Sign out')+'</span></header><div class="layout"><aside>'+''.join('<a class="'+('active' if v==view else '')+'" href="/admin?view='+v+'">'+label+'</a>' for v,label in navigation)+'<a href="/feed" target="_blank">Public feed ↗</a><a href="/embed-demo" target="_blank">Embedding preview ↗</a></aside><main>'
    body+='<p><a href="/admin?view='+esc(view)+'">Refresh status / results</a></p>'
    if notice:body+='<div class="notice">'+esc(notice)+'</div>'
    sources=runtime.snapshot() if runtime else [dict(s,status='Pending Access' if s['platform']=='linkedin' else 'Disabled') for s in config['sources']]
    counts={'Pending':sum(p['editorial_status'] in ('pending','needs review') for p in posts),'Approved':sum(p['editorial_status']=='approved' for p in posts),'Rejected':sum(p['editorial_status']=='rejected' for p in posts),'Duplicate Groups':len({p['group'] for p in posts if p['group']})}
    if view=='dashboard':
        body+='<div class="metrics">'+''.join('<div class="metric">'+key+'<strong>'+str(value)+'</strong></div>' for key,value in counts.items())+'</div><section class="panel"><h2>System health</h2><table><tbody>'
        status=[('Web Server','Running'),('Polling Worker','Error' if runtime and runtime.error else 'Running' if runtime and runtime.running else 'Stopped'),('Database','Connected')]+[(s['platform'].upper() if s['platform']=='x' else s['platform'].title(),s['status']) for s in sources]
        body+=''.join('<tr><td>'+esc(k)+'</td><td>'+badge(v)+'</td></tr>' for k,v in status)+'</tbody></table>'
        if runtime and runtime.error:body+='<p class="notice">Worker configuration/error: '+esc(runtime.error)+'</p>'
        body+='<p><a href="/admin?view=sources">Source configuration & live fetch status</a> · <a href="/admin?view=pending">Pending / Needs Review</a></p></section>'
        body+='<section class="panel"><h2>Recent editorial actions</h2><table><tr><th>Action</th><th>Source</th><th>Actor</th><th>Time</th></tr>'+''.join('<tr><td>'+esc(row[0])+'</td><td>'+esc(row[1])+' · '+esc(row[2])+'</td><td>'+esc(row[3])+'</td><td>'+esc(row[4])+'</td></tr>' for row in history)+'</table></section>'
    elif view=='sources':
        body+='<section class="panel"><h2>Live source status</h2><p><small>Fetch Now makes a live request even for a disabled source. Rate-limit cooldowns remain enforced. Times are UTC.</small></p><div class="scroll"><table><tr><th>Provider / account</th><th>Status</th><th>Polling</th><th>Last fetch / success</th><th>Result</th><th>Error / next due</th><th>Actions</th></tr>'
        for s in sources:
            platform=s['platform']; code=s.get('error_code')
            error=(('HTTP '+str(code)+' · ') if code else '')+s.get('error_type','') if s.get('error_type') else '—'
            friendly={401:'Credentials rejected',403:'API access denied',429:'Rate limited; wait until next due'}.get(code,
                {'FileNotFoundError':'Local token file missing','URLError':'Network connection failed','TimeoutError':'Provider request timed out','ValueError':'Invalid provider/configuration response'}.get(s.get('error_type'),''))
            if friendly:error+=' · '+friendly
            actions='' if platform=='linkedin' else form('/fetch',{'platform':platform},'Fetch Now')+form('/source-toggle',{'platform':platform},'Disable' if s.get('enabled') else 'Enable')
            body+='<tr><td><b>'+esc(platform)+'</b><br><small>'+esc(s.get('account','API access pending'))+'</small></td><td>'+badge(s['status'])+'</td><td>'+('Enabled' if s.get('enabled') else 'Disabled')+'<br>'+esc(s.get('interval_seconds') or 1800)+' sec</td><td>'+esc(stamp(s.get('last_attempt_at')))+'<br><small>Success: '+esc(stamp(s.get('last_success_at')))+'</small></td><td>'+str(s.get('fetched_count',0))+' fetched / '+str(s.get('new_count',0))+' new</td><td>'+esc(error)+'<br><small>'+esc(stamp(s.get('next_poll_at')) if s.get('next_poll_at') else '—')+'</small></td><td>'+actions+'</td></tr>'
        body+='</table></div></section><section class="panel"><h2>Source configuration</h2><p><small>Settings apply to the running worker. Default interval: 1800 seconds. Credentials stay local.</small></p><form method="post" action="/sources"><input type="hidden" name="csrf" value="'+csrf+'"><table><tr><th>Provider</th><th>Account</th><th>Interval seconds</th><th>Enabled</th></tr>'
        for s in config['sources']:
            platform=s['platform']
            if platform not in ('x','bluesky'):continue
            body+='<tr><td>'+esc(platform)+'</td><td><input aria-label="'+platform+' account" name="'+platform+'_account" value="'+esc(s.get('account'))+'" required></td><td><input aria-label="'+platform+' interval seconds" type="number" min="1" name="'+platform+'_interval" value="'+str(s.get('interval_seconds') or 1800)+'"></td><td><input aria-label="'+platform+' enabled" type="checkbox" name="'+platform+'_enabled" '+('checked' if s.get('enabled') else '')+'></td></tr>'
        body+='</table><button>Save source settings</button></form></section>'
    elif view=='testing':
        if not devtools or not devtools.enabled:body+='<section class="panel"><h2>Development tools disabled</h2><p>Enable locally with ASAP_DEV_TOOLS=1. Production default is disabled.</p></section>'
        else:
            runs=devtools.history(); latest={}
            for run in runs:latest.setdefault(run['test_id'],run)
            body+='<div class="notice">Development only. Offline regression uses temporary fixtures. Live integration makes actual API requests; publishing creates a real test-account post.</div><section class="panel"><h2>Offline Regression</h2>'+form('/dev-task',{'test_id':'all'},'Run All Regression Tests',devtools.active)+'<table><tr><th>Test group</th><th>FR / component</th><th>Previous result</th><th>Duration</th><th>Last run</th><th>Action</th></tr>'
            for identity,(name,fr,pattern) in TESTS.items():
                run=latest.get(identity,{})
                body+='<tr><td>'+esc(name)+'</td><td>'+esc(fr)+'</td><td>'+badge(run.get('status','Not run'))+'</td><td>'+('%.2fs'%run['duration'] if run else '—')+'</td><td>'+esc(stamp(run.get('started_at')) if run else '—')+'</td><td>'+form('/dev-task',{'test_id':identity},'Run',devtools.active)+'</td></tr>'
            body+='</table></section><section class="panel"><h2>Live Integration</h2>'
            for identity in ('live-bluesky','live-x'):
                body+='<p>'+esc(LIVE[identity][0])+' · <small>'+esc(LIVE[identity][1])+'</small> '+form('/dev-task',{'test_id':identity},'Run live fetch',devtools.active)+'</p>'
            account,password=credentials()
            body+='</section><section class="panel"><h2>Bluesky test post generator</h2><p>Explicit test account: <b>'+esc(account or 'Not configured')+'</b> · '+badge('Ready' if account and password else 'Credentials needed')+'</p><p><small>Publishing is independent of configured retrieval sources. Credentials never enter the browser.</small></p><form method="post" action="/dev-task"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="test_id" value="publish-bluesky"><label>Text<br><textarea name="text" rows="3" maxlength="300" required placeholder="Bluesky test post text"></textarea></label><br><button '+('disabled' if not account or not password or devtools.active else '')+'>Publish Test Post</button></form><p>'+form('/dev-task',{'test_id':'e2e-bluesky'},'Run Bluesky E2E Test',not account or not password or devtools.active)+'<small>Real post → fetch → candidate; never auto-approves.</small></p></section>'
            if not account or not password:body+='<p class="notice">One-time local setup: python run_app.py --configure-bluesky-test. Enter the test handle and app password in the terminal; never paste credentials here.</p>'
            body+='<section class="panel"><h2>X test posting</h2><p>Pending verified user-context write authorization. The current retrieval bearer-token setup does not establish posting permission.</p></section>'
            body+='<section class="panel"><h2>Recent test runs</h2>'
            for run in runs:
                link=''
                try:
                    result=json.loads((run['output'] or '').split('\n',1)[0])
                    url=result.get('url','') if isinstance(result,dict) else ''
                    if url.startswith('https://bsky.app/profile/'):
                        link='<p><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">View Bluesky post</a></p>'
                except (ValueError,TypeError):pass
                body+='<details '+('open' if run==runs[0] else '')+'><summary>'+badge(run['status'])+' '+esc(run['test_id'])+' · '+esc(stamp(run['started_at']))+' · %.2fs'%run['duration']+'</summary><pre>'+esc(run['output'] or 'Task running… refresh to see results.')+'</pre>'+link+'</details>'
            body+='</section>'
    elif view=='settings':
        body+='<section class="panel"><h2>Feed appearance</h2><form method="post" action="/presentation"><input type="hidden" name="csrf" value="'+csrf+'"><label>Link color <input type="color" name="accent" value="'+esc(settings['accent'])+'"></label><label> Font size <input type="number" name="font_size" min="12" max="24" value="'+str(settings['font_size'])+'"></label><label><input type="checkbox" name="show_origin" '+('checked' if settings['show_origin'] else '')+'>Show source origin</label><button>Save appearance</button></form></section>'
    else:
        title={'pending':'Pending / Needs Review','approved':'Published / Approved','rejected':'Rejected','duplicates':'Duplicate Groups'}.get(view,'Review Queue')
        chosen=[p for p in posts if (bool(p['group']) if view=='duplicates' else p['editorial_status']==view if view in ('approved','rejected') else p['editorial_status'] in ('pending','needs review'))]
        chosen.sort(key=lambda p:(p['group'] or '',p['created_at'] or '',p['post_id']),reverse=True)
        body+='<h2>'+title+'</h2><details class="panel"><summary>Create announcement</summary><form method="post" action="/announcement"><input type="hidden" name="csrf" value="'+csrf+'"><textarea name="text" rows="3" maxlength="10000" required placeholder="Announcement text"></textarea><button>Create pending announcement</button></form></details>'+(''.join(card(p,csrf) for p in chosen) or '<section class="panel">No posts in this view.</section>')
    return body+'</main></div>'
