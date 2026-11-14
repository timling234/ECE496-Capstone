"""Workspace-local duplicate review policy; deterministic, no model or API calls."""
import hashlib,json
from datetime import datetime,timezone
from .editorial import table_exists

PLATFORMS=('linkedin','bluesky','x')
LABELS={'linkedin':'LinkedIn','bluesky':'Bluesky','x':'X'}


def initialize(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS duplicate_settings(id INTEGER PRIMARY KEY CHECK(id=1),mode TEXT NOT NULL,platform_order TEXT NOT NULL)")
    conn.execute('CREATE TABLE IF NOT EXISTS duplicate_policy_handled(group_id TEXT PRIMARY KEY,signature TEXT NOT NULL)')


def settings(conn):
    initialize(conn)
    row=conn.execute('SELECT mode,platform_order FROM duplicate_settings WHERE id=1').fetchone()
    return dict(mode=row[0] if row else 'human',order=json.loads(row[1]) if row else list(PLATFORMS))


def save(conn,mode,order):
    if mode not in ('human','priority') or len(order)!=len(PLATFORMS) or set(order)!=set(PLATFORMS):raise ValueError('Choose a review mode and rank each platform once')
    initialize(conn)
    conn.execute('INSERT OR REPLACE INTO duplicate_settings VALUES(1,?,?)',(mode,json.dumps(order)))
    reconcile(conn)


def reconcile(conn):
    """Caller owns transaction. Revisit changed groups or settings, not every poll."""
    if not table_exists(conn,'editorial_decisions'):return
    from .web_editorial import items,decide,fingerprint
    cfg=settings(conn);groups={}
    for p in items(conn):
        if p['group'] and not p['metadata'].get('deletion_sync'):groups.setdefault(p['group'],[]).append(p)
    for group,members in groups.items():
        signature=hashlib.sha256(json.dumps([cfg,sorted((p['platform'],p['post_id'],fingerprint(p)) for p in members)],sort_keys=True).encode()).hexdigest()
        old=conn.execute('SELECT signature FROM duplicate_policy_handled WHERE group_id=?',(group,)).fetchone()
        if old and old[0]==signature:continue
        if cfg['mode']=='priority':
            eligible=[p for p in members if p['candidate_status']=='candidate' and not p['publication_blocked'] and not p['source_unavailable']]
            if eligible:
                rank={platform:i for i,platform in enumerate(cfg['order'])}
                winner=min(eligible,key=lambda p:(rank.get(p['platform'],len(rank)),p.get('created_at') or '',p['post_id']))
                decide(conn,winner['platform'],winner['post_id'],'approve',actor='duplicates:priority',transaction=False)
        else:
            # Existing complete human resolutions survive the upgrade.
            approved=[p for p in members if p['editorial_status']=='approved']
            complete=len(approved)==1 and all(p['editorial_status']=='rejected' for p in members if p not in approved)
            if complete:
                actor=conn.execute('SELECT actor FROM editorial_decisions WHERE platform=? AND post_id=?',(approved[0]['platform'],approved[0]['post_id'])).fetchone()
                complete=bool(actor and not actor[0].startswith(('ai:','duplicates:')))
            if not complete:
                now=datetime.now(timezone.utc).isoformat()
                for p in members:
                    if p['editorial_status']!='approved':continue
                    conn.execute('INSERT OR REPLACE INTO editorial_decisions VALUES(?,?,?,?,?,?)',(p['platform'],p['post_id'],'needs review',fingerprint(p),'duplicates:human',now))
                    conn.execute('INSERT OR REPLACE INTO editorial_reasons VALUES(?,?,?)',(p['platform'],p['post_id'],'Possible duplicates require human review'))
                    conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES(?,?,?,?,?)',(p['platform'],p['post_id'],'duplicate_review','duplicates:human',now))
        conn.execute('INSERT OR REPLACE INTO duplicate_policy_handled VALUES(?,?)',(group,signature))


def controls(cfg,csrf,esc):
    radios=''.join('<p><label><input type="radio" name="mode" value="'+mode+'" '+('checked' if cfg['mode']==mode else '')+'> '+label+'</label></p>' for mode,label in [('human','Always require human review'),('priority','Approve in the following order')])
    rows=''.join('<li data-duplicate-platform="'+platform+'"><span><span class="duplicate-grip" aria-hidden="true">⠿</span>'+str(i+1)+'. '+LABELS[platform]+'</span><span><button type="button" data-duplicate-move="-1" aria-label="Move '+LABELS[platform]+' up" '+('disabled' if i==0 else '')+'>↑</button><button type="button" data-duplicate-move="1" aria-label="Move '+LABELS[platform]+' down" '+('disabled' if i==len(cfg['order'])-1 else '')+'>↓</button></span></li>' for i,platform in enumerate(cfg['order']))
    return '<section class="panel"><h2>Duplicates</h2><form method="post" action="/duplicate-settings" data-auto-save><input type="hidden" name="csrf" value="'+esc(csrf)+'">'+radios+'<input type="hidden" name="platform_order" value="'+esc(','.join(cfg['order']))+'"><ol class="duplicate-priority" style="list-style:none;padding:0;max-width:380px">'+rows+'</ol><p><small>Priority mode publishes the highest-ranked eligible version and rejects the other duplicates. Human review mode prevents AI from deciding duplicate groups. Changes save automatically.</small></p></form></section>'
