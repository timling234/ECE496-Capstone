"""FR-6/FR-7/FR-9: browser editorial state separate from source provenance."""
import hashlib
import json
from datetime import datetime, timezone
from .store_poc import load_posts
from .editorial import table_exists


def initialize(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS editorial_decisions (
      platform TEXT NOT NULL, post_id TEXT NOT NULL, status TEXT NOT NULL,
      fingerprint TEXT NOT NULL, actor TEXT NOT NULL, decided_at TEXT NOT NULL,
      PRIMARY KEY(platform,post_id));
    CREATE TABLE IF NOT EXISTS feed_settings (id INTEGER PRIMARY KEY CHECK(id=1), accent TEXT NOT NULL, font_size INTEGER NOT NULL, show_origin INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS manual_versions (id INTEGER PRIMARY KEY, post_id TEXT NOT NULL, text TEXT NOT NULL, actor TEXT NOT NULL, saved_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS feed_order (platform TEXT NOT NULL, post_id TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(platform,post_id));
    CREATE TABLE IF NOT EXISTS editorial_actions (
      id INTEGER PRIMARY KEY, platform TEXT, post_id TEXT, action TEXT NOT NULL,
      actor TEXT NOT NULL, acted_at TEXT NOT NULL);
    """)


def fingerprint(post):
    return hashlib.sha256(json.dumps({k:post[k] for k in
        ('text','created_at','post_url','links','media')},sort_keys=True).encode()).hexdigest()


def items(conn):
    posts=load_posts(conn)
    relevance={(a,b):s for a,b,s in conn.execute('SELECT * FROM relevance')}
    groups={(a,b):g for a,b,g in conn.execute('SELECT * FROM duplicate_candidates')}
    decisions={(r[0],r[1]):r for r in conn.execute('SELECT * FROM editorial_decisions')}
    ordering={(a,b):(p,n) for a,b,p,n in conn.execute('SELECT * FROM feed_order')}
    for p in posts:
        p['pinned'],p['position']=ordering.get((p['platform'],p['post_id']),(0,0))
        key=(p['platform'],p['post_id']); d=decisions.get(key)
        p['candidate_status']=relevance.get(key,'ingested')
        p['group']=groups.get(key)
        p['editorial_status']=d[2] if d else 'pending'
        if d and d[2]=='approved' and d[3]!=fingerprint(p):
            p['editorial_status']='needs review'
        # Earlier service approvals remain visible; provenance fields are not approval authority.
        if not d and table_exists(conn,'group_approvals') and p['group']:
            old=conn.execute('SELECT platform,post_id FROM group_approvals WHERE group_id=?',(p['group'],)).fetchone()
            if old==key: p['editorial_status']='approved'
    return posts


def decide(conn, platform, post_id, action, actor='admin'):
    """FR-6/FR-7: atomic selection, rejection, withdrawal and action history."""
    if action not in ('approve','reject','withdraw','pin','unpin'): raise ValueError('Unknown action')
    conn.execute('BEGIN IMMEDIATE')
    try:
        posts=items(conn); p=next((p for p in posts if (p['platform'],p['post_id'])==(platform,post_id)),None)
        if p is None: raise ValueError('Post not found')
        if action=='approve' and p['candidate_status']!='candidate': raise ValueError('Only candidates can be approved')
        now=datetime.now(timezone.utc).isoformat()
        if action in ('pin','unpin'):
            conn.execute('INSERT OR REPLACE INTO feed_order VALUES (?,?,?,?)',(platform,post_id,int(action=='pin'),p['position']))
            conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',(platform,post_id,action,actor,now))
            conn.commit(); return
        changes=[(p,{'approve':'approved','reject':'rejected','withdraw':'pending'}[action],action)]
        if action=='approve' and p['group']:
            changes += [(other,'pending','representative replaced') for other in posts
                if other['group']==p['group'] and other is not p and other['editorial_status']=='approved']
        for target,status,event in changes:
            conn.execute('INSERT OR REPLACE INTO editorial_decisions VALUES (?,?,?,?,?,?)',
                (target['platform'],target['post_id'],status,fingerprint(target),actor,now))
            conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',
                (target['platform'],target['post_id'],event,actor,now))
        conn.commit()
    except Exception:
        conn.rollback(); raise


def publishable(conn):
    """FR-9: approved current candidates, at most one representative per group."""
    result=[]; seen=set()
    for p in sorted(items(conn),key=lambda p:(p['pinned'],int(p['position']>0),-p['position'],p['created_at'] or '',p['platform'],p['post_id']),reverse=True):
        if p['editorial_status']!='approved' or p['candidate_status']!='candidate': continue
        if p['group'] and p['group'] in seen: continue
        if p['group']: seen.add(p['group'])
        result.append(p)
    return result


# FR-11: Manual announcements enter the same candidate/editorial pipeline.
def create_announcement(conn, text, actor='admin'):
    import uuid
    from .store_poc import store, process_stored
    if not text.strip() or len(text)>10000: raise ValueError('Announcement must contain 1–10000 characters')
    now=datetime.now(timezone.utc).isoformat(); identity=str(uuid.uuid4())
    with conn:
        store(conn,[dict(platform='manual',post_id=identity,account_id=actor,created_at=now,
            text=text.strip(),post_url='',links=[],media=[],metadata={'created_by':actor},raw={'text':text.strip()})])
        process_stored(conn)
        conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',
            ('manual',identity,'created',actor,now))
    return identity


# FR-6: Explicit manual feed order, without automatic source priority.
def set_order(conn, platform, post_id, position, actor='admin'):
    position=int(position)
    if not 0<=position<=100000: raise ValueError('Order must be 0–100000 (0 means newest-first default)')
    p=next((p for p in items(conn) if (p['platform'],p['post_id'])==(platform,post_id)),None)
    if not p: raise ValueError('Post not found')
    with conn:
        conn.execute('INSERT OR REPLACE INTO feed_order VALUES (?,?,?,?)',(platform,post_id,p['pinned'],position))
        conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',
            (platform,post_id,'order '+str(position),actor,datetime.now(timezone.utc).isoformat()))


# FR-11: Editing manual content retains its previous text; requires re-review.
def edit_announcement(conn, post_id, text, actor='admin'):
    if not text.strip() or len(text)>10000: raise ValueError('Announcement must contain 1–10000 characters')
    p=next((p for p in items(conn) if p['platform']=='manual' and p['post_id']==post_id),None)
    if not p: raise ValueError('Manual announcement not found')
    now=datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute('INSERT INTO manual_versions(post_id,text,actor,saved_at) VALUES (?,?,?,?)',(post_id,p['text'],actor,now))
        conn.execute("UPDATE posts SET text=? WHERE platform='manual' AND post_id=?",(text.strip(),post_id))
        from .store_poc import process_stored
        process_stored(conn)
        conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',
            ('manual',post_id,'edited',actor,now))


# FR-9: Presentation settings cannot change eligibility or provenance.
def presentation(conn):
    row=conn.execute('SELECT accent,font_size,show_origin FROM feed_settings WHERE id=1').fetchone()
    return dict(zip(('accent','font_size','show_origin'),row or ('#215e95',16,1)))


def save_presentation(conn, accent, font_size, show_origin):
    import re
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',accent): raise ValueError('Choose a six-digit hex color')
    font_size=int(font_size)
    if not 12<=font_size<=24:raise ValueError('Font size must be 12–24')
    with conn:conn.execute('INSERT OR REPLACE INTO feed_settings VALUES (1,?,?,?)',(accent,font_size,int(bool(show_origin))))
