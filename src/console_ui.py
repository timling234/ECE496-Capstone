"""FR-7/FR-10: compact operations console, no external design code."""
import json
from datetime import datetime, timezone
from urllib.parse import quote
from .source_config import identity as source_identity, find_source
from .dev_tools import TESTS, LIVE, credentials

STYLE="""
[hidden]{display:none!important}.post-delete{position:absolute;right:10px;top:7px;margin:0}.post-delete button{background:transparent;color:#c62828;font-size:20px;width:32px;height:32px;padding:0}.post-delete button:hover{background:#fce8e8}article:has(.post-delete)>.post-status{margin-right:38px}.post-select{display:block;margin-bottom:8px}.post-bulk-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.post-bulk-toolbar label{margin-right:12px}

.ai-suggestion{background:#f1f6fb;border-left:3px solid #7397c4;padding:10px;margin:12px 0}

.provider-picker{display:flex;gap:12px;margin:16px 0}.source-actions{text-align:right;vertical-align:middle}.source-actions form,.source-delete form{vertical-align:middle;margin:3px}.source-actions button,.source-delete button{height:32px;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center}.source-delete{width:36px;vertical-align:middle;text-align:right}.source-delete button{width:32px;background:transparent;color:#c62828;font-size:20px;padding:0;line-height:1}.source-delete button:hover{background:#fce8e8}.source-delete button:focus-visible{outline:2px solid #c62828;outline-offset:2px}.provider-option{color:#205a8b;font-size:14px;display:flex;align-items:center;gap:9px;padding:12px 18px;border:1px solid #ccd5df;border-radius:6px;text-decoration:none;background:#f8fafc}.provider-option.selected{background:#e4eef8;border:2px solid #2e63a5;padding:11px 17px}.source-editor>form{display:block}.source-editor select{max-width:100%}

.mock-controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.mock-controls label{display:flex;gap:6px;align-items:center}.mock-controls select{padding:6px}.mock-canvas{background:#dfe6ef;padding:16px;border-radius:8px;overflow:auto}.console-toast{position:fixed;z-index:1000;top:16px;left:50%;transform:translateX(-50%);width:min(760px,calc(100% - 32px));box-sizing:border-box;padding:12px 16px;border:1px solid;border-radius:8px;box-shadow:0 6px 24px #0002;backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:space-between;gap:16px}.toast-success{background:rgba(222,245,231,.92);color:#165c33;border-color:#76b58e}.toast-error{background:rgba(255,229,229,.92);color:#962828;border-color:#d98a8a}.console-toast button{background:transparent;color:inherit;font-size:22px;padding:0 4px}
body{max-width:none;margin:0;padding:0;font:14px system-ui;background:#edf0f3;color:#253240}
h1{font-size:21px;margin:0}h2{font-size:17px;margin:0 0 12px}h3{font-size:15px}header{background:#192b3d;color:white;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}
.layout{display:grid;grid-template-columns:205px 1fr;min-height:calc(100vh - 58px)}aside{background:#23394d;padding:16px 0}aside a{display:block;color:#dce5ed;text-decoration:none;padding:11px 20px}aside a.active{background:#315875;border-left:3px solid #80bded;padding-left:17px}main{padding:20px;min-width:0}a{color:#205a8b}article,.panel{border:1px solid #ccd5df;border-radius:4px;background:white;padding:14px;margin:0 0 14px}article p{margin:8px 0}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;background:#f2f5f7;color:#4c5d6d}th,td{padding:9px;border-bottom:1px solid #dde3e9;vertical-align:top}button{font-size:12px;padding:7px 11px;background:#2d628c;border-radius:3px}form{margin:3px;display:inline-block}input,textarea{font:13px system-ui;padding:6px;max-width:100%;box-sizing:border-box}input[type=number]{width:100px}textarea{width:460px}small{font-size:12px;color:#5b6c7e}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172b3d;color:#d9e5ee;padding:12px;max-height:340px;overflow:auto}.badge{display:inline-block;padding:3px 7px;background:#e1e7ee;border-radius:3px;font-size:12px;font-weight:600}.good{background:#d8eee0;color:#21613d}.bad{background:#f8dfe0;color:#93272d}.warn{background:#fff0cf;color:#865c0c}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}.metric{background:white;border:1px solid #ccd5df;padding:12px}.metric strong{display:block;font-size:23px;margin-top:4px}.notice{padding:10px;background:#fff0cf;border-left:3px solid #b88a29;margin-bottom:14px}.row{display:flex;gap:14px;flex-wrap:wrap}.content{white-space:pre-wrap;overflow-wrap:anywhere}.post-status{float:right;margin-left:12px}article{position:relative}.duplicate-group{border:1px solid #d4aa45;border-left:5px solid #d4aa45;background:#fff7df;padding:12px;margin:12px 0 20px}.duplicate-group h3{color:#785414;margin:0 0 12px}.duplicate-group article:last-child{margin-bottom:0}.source-details{font-size:12px;margin-top:8px}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.source-editor{border-left:4px solid #315875}.source-editor label{display:block;margin:12px 0}.source-editor input[type=text]{width:360px}.review-filters{display:flex;gap:15px;align-items:center}.empty-duplicates{background:#e8f3eb;padding:12px;margin:12px 0}.nav-spacer{margin-top:16px}img{max-width:100%;max-height:180px}@media(max-width:850px){.layout{grid-template-columns:1fr}aside{display:flex;flex-wrap:wrap;padding:0}aside a{padding:9px}.metrics{grid-template-columns:repeat(2,1fr)}main{padding:10px}.scroll{overflow:auto}}
"""


def provider_icon(platform):
    if platform=='x':
        shape='<path d="M5 3h4l10 18h-4L5 3zm-2 18L19 3h2L5 21H3z" fill="currentColor"/>'
    elif platform=='linkedin':
        shape='<rect width="24" height="24" rx="4" fill="currentColor"/><text x="4" y="18" font-family="Arial" font-weight="bold" font-size="17" fill="white">in</text>'
    else:
        shape='<path d="M12 11C7 2 1 1 2 8c0 4 4 5 8 5-7 0-7 7-3 8 3 1 4-3 5-6 1 3 2 7 5 6 4-1 4-8-3-8 4 0 8-1 8-5 1-7-5-6-10 3z" fill="currentColor"/>'
    return '<svg viewBox="0 0 24 24" width="25" height="25" aria-hidden="true">'+shape+'</svg>'


def stamp(value):
    return datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if value is not None else 'Never'


def render_console(posts,history,settings,config,session,view,esc,card,runtime=None,devtools=None,notice='',query=None,notification_config=None,notification_state=None,feed_url=None,connection_choices=None,ai_panel=None):
    query=query or {}
    connection_choices=connection_choices or []
    csrf=session['csrf']
    def form(route,fields,label,disabled=False):
        return '<form method="post" action="'+route+'"><input type="hidden" name="csrf" value="'+csrf+'">'+''.join('<input type="hidden" name="'+esc(k)+'" value="'+esc(v)+'">' for k,v in fields.items())+'<button'+(' disabled' if disabled else '')+'>'+esc(label)+'</button></form>'
    def badge(value):
        cls='good' if value in ('Healthy','Running','Connected','PASS','Authenticated') else 'bad' if value in ('Error','FAIL','TIMEOUT','Reconnect required') else 'warn' if value in ('Pending Access','Waiting','RUNNING','Fetching','Queued') else ''
        return '<span class="badge '+cls+'">'+esc('Re-authentication required' if value=='Reconnect required' else value)+'</span>'
    navigation=[('dashboard','Dashboard'),('pending','Review Queue'),('sources','Sources'),('testing','Testing / Development'),('settings','Settings'),('approved','Published'),('rejected','Rejected')]
    feed_navigation=('<a class="'+('active' if view=='feed' else '')+'" href="/admin?view=feed">Public Feed</a><a class="'+('active' if view=='mock' else '')+'" href="/admin?view=mock">Mock Website</a>' if feed_url else '<a href="/feed" target="_blank">Public Feed ↗</a><a href="/embed-demo" target="_blank">Mock Website ↗</a>')
    body='<header><h1>ASAP Admin</h1><span>Operations console · '+form('/logout',{},'Sign out')+'</span></header><div class="layout"><aside>'+''.join('<a class="'+('active' if v==view else '')+'" href="/admin?view='+v+'">'+label+'</a>' for v,label in navigation)+feed_navigation+'</aside><main>'
    if notice:body+='<div class="notice">'+esc(notice)+'</div>'
    sources=runtime.snapshot() if runtime else [dict(s,status=('Disabled' if s.get('connection_id') else 'Not connected') if s['platform']=='linkedin' else 'Disabled') for s in config['sources']]
    counts={'Pending':sum(p['editorial_status'] in ('pending','needs review') for p in posts),'Approved':sum(p['editorial_status']=='approved' for p in posts),'Rejected':sum(p['editorial_status']=='rejected' for p in posts),'Duplicate Groups':len({p['group'] for p in posts if p['group'] and p['editorial_status'] in ('pending','needs review')})}
    if view=='feed' and feed_url:
        snippet='<iframe src="'+feed_url+'" title="ASAP news" style="width:100%;height:620px;border:0"></iframe>'
        body+='<section class="panel"><h2>Public Feed</h2><h3>Embed your feed</h3><p>Copy this code into your website:</p><textarea id="feed-embed-code" readonly aria-label="Feed embed code" rows="3" style="width:100%;max-width:100%;font-family:monospace">'+esc(snippet)+'</textarea><button type="button" data-copy="feed-embed-code">Copy embed code</button></section>'
        body+='<section class="panel"><h2>Iframe preview</h2><iframe src="'+esc(feed_url)+'" title="Your public feed preview" style="width:100%;height:620px;border:0"></iframe></section>'
    elif view=='mock' and feed_url:
        demo_url=feed_url.rsplit('/feed',1)[0]+'/embed-demo'
        snippet='<iframe src="'+feed_url+'" title="ASAP news" loading="lazy" style="display:block;width:100%;height:620px;border:0;border-radius:12px"></iframe>'
        body+='<section class="panel"><h2>Mock Website</h2><p><b>Mock website for testing purpose</b> — a demonstration inspired by the new MSRG website.</p><div class="mock-controls" data-demo-url="'+esc(demo_url)+'" data-feed-url="'+esc(feed_url)+'"><label>Content <select id="mock-content"><option value="sample" selected>Fictional sample posts</option><option value="live">Your published posts</option></select></label><label>Layout <select id="mock-template"><option value="research">MSRG News</option><option value="simple">Community website</option></select></label><label>Viewport <select id="mock-width"><option value="1200">Desktop</option><option value="768">Tablet</option><option value="390">Mobile</option></select></label><label>Theme <select id="mock-theme"><option value="light">Light</option><option value="dark">Dark</option></select></label><label>Feed height <input id="mock-height" type="number" min="320" max="1000" value="620" step="20"> px</label><label>Link color <input id="mock-accent" type="color" value="'+esc(settings['accent'])+'"></label><label>Font size <input id="mock-font" type="number" min="12" max="24" value="'+str(settings['font_size'])+'"> px</label><label><input id="mock-origin" type="checkbox" '+('checked' if settings['show_origin'] else '')+'>Show source origin</label></div><p><small>Samples are for preview only. Embed code always uses your real public feed. Preview changes do not change your posts or feed settings.</small></p><textarea id="mock-code" aria-label="Website integration code" readonly rows="3" style="width:100%;max-width:100%">'+esc(snippet)+'</textarea><button type="button" data-copy="mock-code">Copy embed code</button> <a id="mock-open" href="'+esc(demo_url)+'?sample=1" target="_blank" rel="noopener">Open demo ↗</a></section>'
        body+='<div class="mock-canvas"><div id="mock-viewport" style="width:1200px;max-width:100%;margin:auto"><iframe id="mock-frame" title="Mock website preview" src="'+esc(demo_url)+'?sample=1" style="display:block;width:100%;height:1300px;border:0;border-radius:8px"></iframe></div></div>'
    elif view=='dashboard':
        body+='<div class="metrics">'+''.join('<div class="metric">'+key+'<strong>'+str(value)+'</strong></div>' for key,value in counts.items())+'</div><section class="panel"><h2>System health</h2><table><tbody>'
        status=[('Web Server','Running'),('Polling Worker','Error' if runtime and runtime.error else 'Running' if runtime and runtime.running else 'Stopped'),('Database','Connected')]+[(s['platform'].upper() if s['platform']=='x' else s['platform'].title(),s['status']) for s in sources]
        body+=''.join('<tr><td>'+esc(k)+'</td><td>'+badge(v)+'</td></tr>' for k,v in status)+'</tbody></table>'
        if runtime and runtime.error:body+='<p class="notice">Worker configuration/error: '+esc(runtime.error)+'</p>'
        body+='<p><a href="/admin?view=sources">Source configuration & live fetch status</a> · <a href="/admin?view=pending">Pending / Needs Review</a></p></section>'
        body+='<section class="panel"><h2>Recent editorial actions</h2><table><tr><th>Action</th><th>Source</th><th>Actor</th><th>Time</th></tr>'+''.join('<tr><td>'+esc(row[0])+'</td><td>'+esc(row[1])+' · '+esc(row[2])+'</td><td>'+esc(row[3])+'</td><td>'+esc(row[4])+'</td></tr>' for row in history)+'</table></section>'
    elif view=='sources':
        body+='<section class="panel"><div class="section-heading"><h2>Sources</h2><a class="badge" href="/admin?view=sources&amp;source_form=add">+ Add Source</a></div><p><small>Fetch Now makes a live request even for a disabled source. Rate-limit cooldowns remain enforced. Remove stops retrieval and keeps existing posts. Times are UTC.</small></p><div class="scroll"><table><tr><th>Provider / account</th><th>Authentication / status</th><th>Polling</th><th>Last fetch / success</th><th>Result</th><th>Error / next due</th><th>Actions</th><th aria-label="Remove source"></th></tr>'
        for s in sources:
            platform=s['platform']; key=source_identity(s); code=s.get('error_code')
            error=(('HTTP '+str(code)+' · ') if code else '')+s.get('error_type','') if s.get('error_type') else '—'
            friendly={401:'Credentials rejected',403:'API access denied',429:'Rate limited; wait until next due'}.get(code,
                {'FileNotFoundError':'Local token file missing','URLError':'Network connection failed','TimeoutError':'Provider request timed out','ValueError':'Invalid provider/configuration response'}.get(s.get('error_type'),''))
            if friendly:error+=' · '+friendly
            actions=(form('/fetch',{'source_key':key},'Fetch Now')+form('/source-toggle',{'source_key':key},'Disable' if s.get('enabled') else 'Enable')) if s.get('account') and not s.get('draft') and (platform!='linkedin' or s.get('connection_id')) else ''
            remove='<form method="post" action="/source-remove"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="source_key" value="'+esc(key)+'"><button aria-label="Remove source" title="Remove source">&#10006;&#65038;</button></form>'
            if s.get('authentication')!='Authenticated':
                actions+=form('/'+platform+'/connect',{'source_key':key},'Re-authenticate' if s.get('authentication')=='Reconnect required' else 'Authenticate')
            body+='<tr><td><a aria-label="Edit '+esc(platform)+' '+esc(s.get('account',''))+'" href="/admin?view=sources&amp;edit_source='+quote(key,safe='')+'">✎</a> <b>'+esc(s.get('name') or platform)+'</b><br><small>'+esc(s.get('label') or s.get('account') or 'Not connected')+'</small></td><td>'+badge(s.get('authentication','Public access' if platform=='bluesky' else 'Not authenticated'))+'<br><small>'+esc(s['status'])+'</small></td><td>'+('Enabled' if s.get('enabled') else 'Disabled')+'<br>'+esc(s.get('interval_seconds') or 1800)+' sec</td><td>'+esc(stamp(s.get('last_attempt_at')))+'<br><small>Success: '+esc(stamp(s.get('last_success_at')))+'</small></td><td>'+str(s.get('fetched_count',0))+' fetched / '+str(s.get('new_count',0))+' new<br><small>'+str(s.get('updated_count',0))+' updated · '+str(s.get('unavailable_count',0))+' unavailable · '+str(s.get('unchecked_count',0))+' unchecked</small></td><td>'+esc(error)+'<br><small>'+esc(stamp(s.get('next_poll_at')) if s.get('next_poll_at') else '—')+'</small></td><td class="source-actions">'+actions+'</td><td class="source-delete">'+remove+'</td></tr>'
        body+='</table></div></section>'
        edit_key=query.get('edit_source',[''])[0]
        adding=query.get('source_form',[''])[0]=='add'
        if adding:
            body+='<section class="panel source-editor"><h2>Add Source</h2><p>Choose a platform to create its source, then authenticate from the source row.</p><div class="provider-picker" role="group" aria-label="Provider">'
            for provider,label in [('x','X'),('bluesky','Bluesky'),('linkedin','LinkedIn')]:
                body+='<form method="post" action="/source-add"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="provider" value="'+provider+'"><button class="provider-option" aria-label="Select '+label+'">'+provider_icon(provider)+'<span>'+label+'</span></button></form>'
            body+='</div></section>'
        elif edit_key:
            source=find_source(config,edit_key)
            if source is None:body+='<div class="notice">Source not found.</div>'
            else:
                platform=source['platform'];draft=source.get('draft') or not source.get('account')
                body+='<section class="panel source-editor"><h2>Edit Source</h2><p>'+provider_icon(platform)+' '+esc(platform.title() if platform!='x' else 'X')+'</p><form method="post" action="/source-save"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="provider" value="'+platform+'"><input type="hidden" name="source_key" value="'+esc(edit_key)+'">'
                body+='<label>Source name <input type="text" name="name" maxlength="80" value="'+esc(source.get('name') or platform)+'" required></label>'
                body+='<p>Connected account: <b>'+esc(source.get('label') or source.get('account') or 'Not connected')+'</b></p>'
                if draft:body+='<p>Authenticate this source using its row action before enabling polling.</p>'
                body+='<label>Polling interval <input type="number" name="interval_seconds" min="'+('1800' if platform=='linkedin' else '1')+'" max="31536000" value="'+str(source.get('interval_seconds') or 1800)+'"> seconds</label><label><input type="checkbox" name="enabled" '+('checked' if source.get('enabled') else '')+' '+('disabled' if draft else '')+'>Automatic polling</label>'
                body+='<details><summary>Advanced settings</summary><label>Posts per request <input type="number" name="page_size" min="'+('5' if platform=='x' else '1')+'" max="100" value="'+str(source.get('page_size',5))+'"></label><p><small>Maximum posts returned by one provider request. Larger values read more data. This does not control the number shown on your website. Catch-up fetching may use multiple requests.</small></p></details>'
                body+='<a href="/admin?view=sources">Cancel</a> <button>Save Source</button></form></section>'
    elif view=='testing':
        if not devtools or not devtools.enabled:body+='<section class="panel"><h2>Development tools disabled</h2><p>Enable locally with ASAP_DEV_TOOLS=1. Production default is disabled.</p></section>'
        else:
            runs=devtools.history(); latest={}
            for run in runs:latest.setdefault(run['test_id'],run)
            body+='<div class="notice">Development only. Offline regression uses temporary fixtures. Live integration makes actual API requests; publishing creates a real test-account post.</div><section class="panel"><h2>Offline Regression</h2>'+form('/dev-task',{'test_id':'all'},'Run All Regression Tests',devtools.active)+'<table><tr><th>Test group</th><th>FR / component</th><th>Previous result</th><th>Duration</th><th>Last run</th><th>Action</th></tr>'
            for identity,(name,fr,pattern) in TESTS.items():
                run=latest.get(identity,{})
                body+='<tr><td>'+esc(name)+'</td><td>'+esc(fr)+'</td><td>'+badge(run.get('status','Not run'))+'</td><td>'+('%.2fs'%run['duration'] if run else '—')+'</td><td>'+esc(stamp(run.get('started_at')) if run else '—')+'</td><td>'+form('/dev-task',{'test_id':identity},'Run',devtools.active)+'</td></tr>'
            body+='</table></section><section class="panel"><h2>Local AI judgment</h2><p>Six text cases: original MSRG captions, ordinary updates and obvious test/mistake posts. Shows expected vs actual decisions and reasons. No publishing or social API calls; images/video are not visually analyzed.</p>'+form('/dev-task',{'test_id':'local-ai-judgment'},'Run local AI judgment test',devtools.active)+'</section><section class="panel"><h2>Live Integration</h2>'
            for identity in ('live-bluesky','live-x'):
                body+='<p>'+esc(LIVE[identity][0])+' · <small>'+esc(LIVE[identity][1])+'</small> '+form('/dev-task',{'test_id':identity},'Run live fetch',devtools.active)+'</p>'
            account,password=credentials()
            body+='</section><section class="panel"><h2>Bluesky test post generator</h2><p>Explicit test account: <b>'+esc(account or 'Not configured')+'</b> · '+badge('Ready' if account and password else 'Credentials needed')+'</p><p><small>Publishing is independent of configured retrieval sources. Credentials never enter the browser.</small></p><form method="post" action="/dev-task"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="test_id" value="publish-bluesky"><label>Text<br><textarea name="text" rows="3" maxlength="300" required placeholder="Bluesky test post text"></textarea></label><br><button '+('disabled' if not account or not password or devtools.active else '')+'>Publish Test Post</button></form><p>'+form('/dev-task',{'test_id':'e2e-bluesky'},'Run Bluesky E2E Test',not account or not password or devtools.active)+'<small>Real post → fetch → candidate; never auto-approves.</small></p></section>'
            if not account or not password:body+='<p class="notice">One-time local setup: python run_app.py --configure-bluesky-test. Enter the test handle and app password in the terminal; never paste credentials here.</p>'
            body+='<section class="panel"><h2>LinkedIn test posting</h2><p>Authorize organization posting for the prepared mock-post batch. Authorizing does not publish any post.</p>'+form('/linkedin/connect',{'publish_mock':'1'},'Authorize LinkedIn test posting')+'</section>'
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
                body+='<details '+('open' if run==runs[0] else '')+'><summary>'+badge(run['status'])+' '+esc(run['test_id'])+' · '+esc(stamp(run['started_at']))+' · %.2fs'%run['duration']+'</summary><pre>'+esc(run['output'] or 'Task running…')+'</pre>'+link+'</details>'
            body+='</section>'
    elif view=='settings':
        if ai_panel:
            ai=ai_panel;cfg=ai['config']
            body+='<section class="panel source-editor"><h2>Local AI</h2><p>Models run on Server. Model files are shared; your selected model and review rules apply only to your workspace.</p>'
            if ai['error']:body+='<p class="notice">'+esc(ai['error'])+'</p>'
            body+='<form method="post" action="/llm/settings"><input type="hidden" name="csrf" value="'+csrf+'"><label>Installed model <select name="model" required>'
            for name,size in ai['installed'].items():
                body+='<option value="'+esc(name)+'" '+('selected' if name==cfg['model'] else '')+'>'+esc(name)+' · '+('%.1f GB'%(size/1e9))+'</option>'
            body+='</select></label><p>Applied model: <b>'+esc(cfg['model'])+'</b></p><label>Review policy<textarea name="policy" rows="5" minlength="10" maxlength="4000" required>'+esc(cfg['policy'])+'</textarea></label><label>Posts per batch <input type="number" name="batch_limit" min="1" max="50" value="'+str(cfg['batch_limit'])+'"></label><p>Keep both options off for suggestions only. Approvals publish to your public feed. Automation runs only when you click Run automatic review.</p><label><input type="checkbox" name="auto_approve" '+('checked' if cfg['auto_approve'] else '')+'>Allow automatic approve</label><label><input type="checkbox" name="auto_reject" '+('checked' if cfg['auto_reject'] else '')+'>Allow automatic reject</label><p><small>Duplicate groups are analyzed together. Approving a representative and rejecting alternatives requires both options. Uncertain or changed groups stay for manual review.</small></p><button '+('disabled' if not ai['installed'] else '')+'>Apply model and settings</button></form>'
            body+='<h3>Download a local model</h3><p>Downloads use Server disk space and internet bandwidth. After completion, choose the model above and apply it.</p><form method="post" action="/llm/download"><input type="hidden" name="csrf" value="'+csrf+'"><select name="model" required>'
            body+=''.join('<option value="'+esc(name)+'">'+esc(label)+(' · Installed' if name in ai['installed'] else '')+'</option>' for name,label in ai['catalog'].items())+'</select><button>Download</button></form>'
            for name,status,progress,error in ai['downloads']:body+='<p>'+esc(name)+' · '+esc(status)+' · '+str(progress)+'% '+esc(error or '')+'</p>'
            body+='</section>'
        from .notifications import smtp_ready
        notify=notification_config or dict(enabled=0,channel='email',recipient='')
        state=notification_state or dict(pending=0,sent=0,error='')
        event_labels=[('ai_review','Notify me whenever a post is flagged needs human review by AI'),('reauth','Notify me whenever a re-authentication is needed'),('duplicates','Notify me whenever a post is flagged possible duplicate'),('new_post','Notify me whenever a new post is queued for review')]
        options=''.join('<p><label><input type="checkbox" name="notify_'+event+'" '+('checked' if notify.get(event,event=='new_post') else '')+'>'+label+'</label></p>' for event,label in event_labels)
        body+='<section class="panel"><h2>Notifications</h2><form method="post" action="/notifications"><input type="hidden" name="csrf" value="'+csrf+'"><label><input type="checkbox" name="enabled" '+('checked' if notify['enabled'] else '')+'>Enable notifications</label><p><label>Via <select name="channel"><option value="email">Email</option><option value="sms" disabled>SMS — not available yet</option></select></label></p><p><label>Email address <input type="email" name="recipient" value="'+esc(notify['recipient'])+'" maxlength="254"></label></p>'+options+'<button>Save notifications</button></form><p>Mail transport: '+('Configured' if smtp_ready() else 'SMTP configuration required')+' · Pending: '+str(state['pending'])+' · Sent: '+str(state['sent'])+'</p><p><small>'+('Last delivery error: '+esc(state['error']) if state['error'] else 'SMTP credentials are supplied to the server through environment variables. Existing queued posts are not retroactively notified.')+'</small></p></section>'
        body+='<section class="panel"><h2>Feed appearance</h2><form method="post" action="/presentation"><input type="hidden" name="csrf" value="'+csrf+'"><label>Link color <input type="color" name="accent" value="'+esc(settings['accent'])+'"></label><label> Font size <input type="number" name="font_size" min="12" max="24" value="'+str(settings['font_size'])+'"></label><label><input type="checkbox" name="show_origin" '+('checked' if settings['show_origin'] else '')+'>Show source origin</label><button>Save appearance</button></form></section>'
    else:
        body+='<section class="panel post-bulk-toolbar"><button type="button" data-multi-select aria-pressed="false">Select posts</button><form id="post-bulk" method="post" action="/posts-action" hidden><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="return_view" value="'+esc(view)+'"><label><input type="checkbox" data-select-all> Select all</label> <span data-selection-count>0 selected</span> <button name="action" value="delete">Delete</button> <button name="action" value="approve">Publish</button> <button name="action" value="reject">Reject</button></form></section>'
        if view=='pending':
            if ai_panel:
                cfg=ai_panel['config']
                body+='<section class="panel"><h2>AI review</h2><p>Review pending posts and possible duplicate groups with '+esc(cfg['model'])+'. Suggestions remain available per post.</p>'+form('/llm/batch',{'mode':'advice'},'Suggest for queue',not counts['Pending'])+form('/llm/batch',{'mode':'automatic'},'Run automatic review',not counts['Pending'] or not (cfg['auto_approve'] or cfg['auto_reject']))+' <a href="/admin?view=settings">Local AI settings</a>'
                for batch,status,mode,total,done,applied,error in ai_panel['batches']:
                    body+='<p>Batch '+str(batch)+' · '+esc(mode)+' · '+esc(status)+' · '+str(done)+'/'+str(total)+' reviewed · '+str(applied)+' applied '+esc(error or '')+'</p>'
                    if status=='running':body+=form('/llm/cancel',{'batch_id':batch},'Stop batch')
                body+='</section>'
            chosen_needs='needs_review' in query if 'filters_set' in query else True
            chosen_duplicates='duplicates' in query if 'filters_set' in query else True
            body+='<h2>Review Queue</h2><form class="panel review-filters" method="get" action="/admin"><input type="hidden" name="view" value="pending"><input type="hidden" name="filters_set" value="1"><label><input type="checkbox" name="needs_review" '+('checked' if chosen_needs else '')+'>Needs Review</label><label><input type="checkbox" name="duplicates" '+('checked' if chosen_duplicates else '')+'>Possible Duplicates</label><button>Apply filters</button></form>'
            body+='<details class="panel"><summary>Create announcement</summary><form method="post" action="/announcement"><input type="hidden" name="csrf" value="'+csrf+'"><textarea name="text" rows="3" maxlength="10000" required placeholder="Announcement text"></textarea><button>Create pending announcement</button></form></details>'
            review=[p for p in posts if p['editorial_status'] in ('pending','needs review')]
            groups={p['group'] for p in review if p['group']}
            displayed=set()
            if chosen_duplicates:
                body+='<h3>Possible Duplicates</h3>'
                if not groups:body+='<div class="empty-duplicates">✓ No possible duplicates detected in the review queue.</div>'
                for number,group in enumerate(sorted(groups),1):
                    members=[p for p in posts if p['group']==group]
                    members.sort(key=lambda p:(p['created_at'] or '',p['platform'],p['post_id']),reverse=True)
                    body+='<section class="duplicate-group" data-group="'+esc(group)+'"><h3>⚠ POSSIBLE DUPLICATES — Group #'+str(number)+'</h3>'
                    body+=''.join(card(p,csrf) for p in members)+'</section>'
                    displayed.update((p['platform'],p['post_id']) for p in members)
            if chosen_needs:
                ordinary=[p for p in review if (p['platform'],p['post_id']) not in displayed]
                ordinary.sort(key=lambda p:(p['created_at'] or '',p['platform'],p['post_id']),reverse=True)
                body+='<section class="ordinary-review"><h3>Needs Review</h3>'+(''.join(card(p,csrf) for p in ordinary) or '<p>No posts need review in this section.</p>')+'</section>'
            if not chosen_needs and not chosen_duplicates:body+='<p class="panel">Select at least one review filter.</p>'
        else:
            title='Published' if view=='approved' else 'Rejected'
            chosen=[p for p in posts if p['editorial_status']==view]
            chosen.sort(key=lambda p:(p['created_at'] or '',p['platform'],p['post_id']),reverse=True)
            body+='<h2>'+title+'</h2>'+(''.join(card(p,csrf,return_view=view) for p in chosen) or '<section class="panel">No posts in this view.</section>')
    active=any(s.get('status') in ('Fetching','Queued') for s in sources) or bool(devtools and devtools.active)
    if ai_panel:active=active or any(b[1]=='running' for b in ai_panel['batches']) or any(d[1]=='running' for d in ai_panel['downloads'])
    failed=bool(ai_panel and ((ai_panel['batches'] and ai_panel['batches'][0][1] in ('error','complete_with_errors')) or (ai_panel['downloads'] and ai_panel['downloads'][0][1]=='error')))
    body=body.replace('<main>', '<main data-busy="'+str(bool(active)).lower()+'" data-failed="'+str(failed).lower()+'">',1)
    return body+'</main></div>'
