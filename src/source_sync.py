"""Bounded availability checks. Timeline absence alone never means deletion."""
import json
import hashlib
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from .store_poc import normalize_x, normalize_bluesky


def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS source_post_checks (source_key TEXT NOT NULL,platform TEXT NOT NULL,post_id TEXT NOT NULL,checked_at REAL NOT NULL DEFAULT 0,unavailable INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source_key,platform,post_id))')


def lookup(provider, posts):
    """One batch endpoint call; no retries and no missing-list inference."""
    ids=[p['post_id'] for p in posts]
    if provider.platform=='linkedin':
        token=provider.credentials.access_token(provider.connection)
        data=provider.request('https://api.linkedin.com/rest/posts?ids=List('+','.join(quote(i,safe='') for i in ids)+')',token=token)
        if not isinstance(data.get('results'),dict):raise ValueError('Invalid batch response')
        from .linkedin import normalize
        existing={m['asset_id']:dict(downloadUrl=m.get('url') or m.get('fullsize')) for p in posts for m in p['media'] if m.get('asset_id')}
        found=[];unavailable=[]
        for key,payload in data['results'].items():
            if key not in ids or payload.get('author')!='urn:li:organization:'+provider.account:raise ValueError('Invalid batch identity')
            if payload.get('lifecycleState')=='PUBLISHED':found.append(normalize(payload,provider.account,provider.label,existing))
            elif payload.get('lifecycleState') in ('DRAFT','DELETED','ARCHIVED'):unavailable.append(key)
        for key,error in data.get('errors',{}).items():
            if key in ids and error.get('status') in (404,410):unavailable.append(key)
        return found,unavailable
    if provider.platform=='x':
        token=provider.token_getter() if provider.token_getter else provider.token_file.read_text(encoding='utf-8-sig').strip()
        params={'ids':','.join(ids),'tweet.fields':'created_at,attachments,entities,author_id,edit_history_tweet_ids','expansions':'attachments.media_keys','media.fields':'type,url,preview_image_url,width,height'}
        data=provider.transport('https://api.x.com/2/tweets?'+urlencode(params),token)
        if 'data' not in data and 'errors' not in data:raise ValueError('Invalid batch response')
        media={m['media_key']:m for m in data.get('includes',{}).get('media',[])}
        found=[]
        for item in data.get('data',[]):
            if item['id'] not in ids or item.get('author_id')!=provider.account:raise ValueError('Invalid batch identity')
            found.append(normalize_x(item,media,account_id=provider.account))
        unavailable=[str(e.get('resource_id')) for e in data.get('errors',[]) if e.get('type')=='https://api.twitter.com/2/problems/resource-not-found' and str(e.get('resource_id')) in ids]
        return found,unavailable
    if provider.platform=='bluesky':
        data=provider.transport('https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?'+urlencode([('uris',i) for i in ids]))
        if data.get('error') or not isinstance(data.get('posts'),list):raise ValueError('Invalid batch response')
        found=[]
        for post in data['posts']:
            if post['uri'] not in ids:raise ValueError('Invalid batch identity')
            found.append(normalize_bluesky({'post':post},fallback_handle=provider.account))
        # The successful hydrated lookup can also omit moderated/non-public posts.
        return found,[i for i in ids if i not in {p['post_id'] for p in found}]
    return [],[]


def reconcile(conn,provider,batch,now):
    from .store_poc import load_posts
    from .web_editorial import fingerprint
    initialize(conn)
    known=load_posts(conn)
    previous={(p['platform'],p['post_id']):p for p in known}
    # An explicit source association also covers reposts with another author DID.
    linked={r[0]:r[1] for r in conn.execute('SELECT post_id,checked_at FROM source_post_checks WHERE source_key=?',(provider.key,))}
    owned=[p for p in known if p['platform']==provider.platform and (p['account_id']==provider.account or p['post_id'] in linked or provider.platform=='bluesky' and p['post_url'].startswith('https://bsky.app/profile/'+provider.account+'/post/'))]
    fresh={p['post_id']:p for p in batch.posts}
    missing=sorted((p for p in owned if p['post_id'] not in fresh),key=lambda p:(linked.get(p['post_id'],0),p['post_id']))
    cap=25 if provider.platform=='bluesky' else 100
    found=[];unavailable=[];error=None
    if missing and getattr(provider,'supports_post_lookup',False):
        try:found,unavailable=lookup(provider,missing[:cap])
        except (HTTPError,ValueError,OSError,KeyError,TypeError) as exc:error=('HTTP '+str(exc.code)) if isinstance(exc,HTTPError) else type(exc).__name__
    fresh.update({p['post_id']:p for p in found})
    # Preserve valid older approvals across the stable-media fingerprint upgrade.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='editorial_decisions'").fetchone():
        for identity,p in fresh.items():
            old=previous.get((p['platform'],identity))
            if old:
                legacy=hashlib.sha256(json.dumps({k:old[k] for k in ('text','created_at','post_url','links','media')},sort_keys=True).encode()).hexdigest()
                conn.execute("UPDATE editorial_decisions SET fingerprint=? WHERE platform=? AND post_id=? AND fingerprint=? AND status='approved'",(fingerprint(old),p['platform'],identity,legacy))
    changed=[i for i,p in fresh.items() if (p['platform'],i) in previous and fingerprint(p)!=fingerprint(previous[(p['platform'],i)])]
    # A rotating, bounded check reports what was not verified rather than claiming
    # full synchronization. Cooldowns, polling settings and source scopes stay intact.
    checked=set(fresh)|set(unavailable)
    newly_unavailable=[]
    if changed and conn.execute("SELECT 1 FROM sqlite_master WHERE name='editorial_decisions'").fetchone():
        conn.executemany("UPDATE editorial_decisions SET status='needs review' WHERE platform=? AND post_id=? AND status='approved'",[(provider.platform,i) for i in changed])
    for identity in checked:
        old=conn.execute('SELECT unavailable FROM source_post_checks WHERE source_key=? AND platform=? AND post_id=?',(provider.key,provider.platform,identity)).fetchone()
        gone=identity in unavailable
        if gone and (not old or not old[0]):newly_unavailable.append(identity)
        conn.execute('INSERT OR REPLACE INTO source_post_checks VALUES (?,?,?,?,?)',(provider.key,provider.platform,identity,now,int(gone)))
        if gone and conn.execute("SELECT 1 FROM sqlite_master WHERE name='editorial_decisions'").fetchone():
            conn.execute("UPDATE editorial_decisions SET status='needs review' WHERE platform=? AND post_id=? AND status='approved'",(provider.platform,identity))
    return list(fresh.values()),dict(updated=len(changed),unavailable=len(newly_unavailable),checked=len(checked),unchecked=len({p['post_id'] for p in owned}-checked),verification_error=error)
