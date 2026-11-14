"""Upstream removal is a reviewable task, never an immediate local deletion."""
import json
import uuid
from datetime import datetime, timezone


def initialize(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS deletion_tasks (id TEXT PRIMARY KEY,platform TEXT NOT NULL,target_id TEXT NOT NULL,target_fingerprint TEXT NOT NULL,snapshot TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)")


def detected(conn, post):
    from .web_editorial import fingerprint
    initialize(conn)
    if conn.execute("SELECT 1 FROM deletion_tasks WHERE platform=? AND target_id=? AND status IN ('pending','rejected','dismissed')",(post['platform'],post['post_id'])).fetchone():return
    conn.execute("INSERT INTO deletion_tasks VALUES (?,?,?,?,?,'pending',?)",('deletion-sync:'+uuid.uuid4().hex,post['platform'],post['post_id'],fingerprint(post),json.dumps(post),datetime.now(timezone.utc).isoformat()))


def recovered(conn,platform,identity):
    initialize(conn)
    conn.execute("UPDATE deletion_tasks SET status='cancelled' WHERE platform=? AND target_id=? AND status IN ('pending','rejected','dismissed')",(platform,identity))


def items(conn,posts,unavailable):
    from .web_editorial import fingerprint
    initialize(conn)
    current={(p['platform'],p['post_id']):p for p in posts}
    result=[]
    for identity,platform,target,fp,data,status,created in conn.execute("SELECT * FROM deletion_tasks WHERE status IN ('pending','rejected')"):
        original=current.get((platform,target)); saved=json.loads(data)
        valid=bool(original and (platform,target) in unavailable and fingerprint(original)==fp)
        result.append(dict(platform=platform,post_id=identity,account_id=saved['account_id'],created_at=created,fetched_at=created,
            text=('Evidence unchanged. ' if valid else 'Evidence conflict — manual review required. ')+'Deletion sync requested: the source reported this post deleted or unavailable. Approve to delete the local copy; Reject to keep it.\nTarget: '+target+'\n\n'+saved['text'][:1200],
            post_url=saved['post_url'],links=[],media=[],raw={},metadata={'deletion_sync':{'target_id':target,'valid':valid},'source_account_name':saved.get('metadata',{}).get('source_account_name')},
            candidate_status='candidate',group=None,pinned=0,position=0,editorial_status=status,editorial_reason=None,
            publication_blocked=False,source_unavailable=False,original_content_unavailable=False))
    return result


def decide(conn,task,action,actor,now):
    md=task['metadata']['deletion_sync']
    if action=='approve':
        if not md['valid']:raise ValueError('Deletion evidence changed or the post recovered. Fetch again before synchronizing.')
        from .web_editorial import remove_post
        from .store_poc import load_posts,process_stored
        target=next(p for p in load_posts(conn) if p['platform']==task['platform'] and p['post_id']==md['target_id'])
        remove_post(conn,target,actor)
        process_stored(conn)
    if action not in ('approve','reject','withdraw'):raise ValueError('This action does not apply to a deletion task')
    conn.execute('UPDATE deletion_tasks SET status=? WHERE id=?',({'approve':'approved','reject':'rejected','withdraw':'pending'}[action],task['post_id']))
    conn.execute('INSERT INTO editorial_actions(platform,post_id,action,actor,acted_at) VALUES (?,?,?,?,?)',(task['platform'],task['post_id'],'deletion_sync_'+action,actor,now))
