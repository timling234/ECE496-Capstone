"""Actionable notification copy from workspace-local records; no network reads."""
import json,os
from pathlib import Path
from html import escape
from urllib.parse import urlencode,urlparse
from email.message import EmailMessage
from .editorial import table_exists

LABELS={'x':'X','bluesky':'Bluesky','linkedin':'LinkedIn','manual':'Announcement'}


def context(conn,event,platform,identity):
    from .store_poc import load_posts
    from .source_profile import attach
    posts=load_posts(conn);attach(conn,posts)
    chosen=[p for p in posts if p['platform']==platform and p['post_id']==identity]
    if event=='duplicates' and table_exists(conn,'duplicate_candidates'):
        keys={tuple(row) for row in conn.execute('SELECT platform,post_id FROM duplicate_candidates WHERE group_id=?',(identity,))}
        chosen=[p for p in posts if (p['platform'],p['post_id']) in keys]
    if not chosen and event=='ai_review' and table_exists(conn,'deletion_tasks'):
        task=conn.execute("SELECT snapshot FROM deletion_tasks WHERE id=? AND status='pending'",(identity,)).fetchone()
        if task:
            post=json.loads(task[0]);post['post_id']=identity;post['text']='Deletion synchronization needs review. '+post['text'];attach(conn,[post]);chosen=[post]
    result={'resolved':False,'platform':LABELS.get(platform,platform),'name':'','excerpt':'','reason':'','count':len(chosen)}
    if chosen:
        p=chosen[0];md=p['metadata'];author=(p['raw'].get('post') or {}).get('author',{})
        result.update(platform=LABELS.get(p['platform'],p['platform']),name=(md.get('source_profile') or {}).get('name') or md.get('source_account_name') or author.get('displayName') or author.get('handle') or 'Connected account',excerpt=p['text'][:280],original=p['post_url'],focus_platform=p['platform'],focus_post=p['post_id'])
        if table_exists(conn,'editorial_decisions') and event in ('new_post','ai_review'):
            decision=conn.execute('SELECT status FROM editorial_decisions WHERE platform=? AND post_id=?',(platform,identity)).fetchone()
            if decision and decision[0] in ('approved','rejected'):result['resolved']=True
        if table_exists(conn,'ai_suggestions'):
            row=conn.execute("SELECT reason FROM ai_suggestions WHERE platform=? AND post_id=? AND status='complete' AND recommendation='needs_review' ORDER BY id DESC LIMIT 1",(platform,identity)).fetchone()
            if row:result['reason']=row[0][:500]
    if event=='reauth':
        result['source_key']=identity
        account=identity.split(':',1)[1] if ':' in identity else identity
        if table_exists(conn,'source_profiles'):
            row=conn.execute('SELECT name FROM source_profiles WHERE platform=? AND account_id=?',(platform,account)).fetchone()
            if row:result['name']=row[0]
        path=next((r[2] for r in conn.execute('PRAGMA database_list') if r[1]=='main'),'')
        if path:
            try:
                config=json.loads((Path(path).parent/'polling.local.json').read_text())
                source=next((s for s in config['sources'] if s['platform']==platform and s.get('account')==account),{})
                result['name']=result['name'] or source.get('label') or 'Connected account'
                if source:
                    from .source_auth import authentication
                    evidence=dict(source)
                    if table_exists(conn,'source_poll_state'):
                        state=conn.execute('SELECT error_type,error_code,last_attempt_at FROM source_poll_state WHERE source_key=?',(identity,)).fetchone()
                        if state:evidence.update(zip(('error_type','error_code','last_attempt_at'),state))
                    result['resolved']=authentication(evidence,Path(path).parent)=='Authenticated'
            except (OSError,ValueError,KeyError):pass
    if event!='reauth' and not chosen:result['resolved']=True
    if event=='duplicates':
        result['platform']=' / '.join(dict.fromkeys(LABELS.get(p['platform'],p['platform']) for p in chosen)) or 'Research updates'
        result['name']=''
        result['examples']=[LABELS.get(p['platform'],p['platform'])+': '+' '.join(p['text'].split())[:160] for p in chosen[:3]]
        result['focus_group']=identity
    return result


def message(recipient,platform,identity,event='new_post',details=None):
    details=details or {};label=details.get('platform') or LABELS.get(platform,platform)
    name=' '.join((details.get('name') or '').split())[:100]
    account=label+(' · '+name if name else '')
    base=os.environ.get('ASAP_PUBLIC_URL','https://asap.surf').rstrip('/')
    if urlparse(base).scheme not in ('http','https'):base='https://asap.surf'
    query={'view':'sources' if event=='reauth' else 'pending'}
    if event=='reauth':query['reauth_source']=details.get('source_key',identity)
    else:
        for key in ('focus_platform','focus_post','focus_group'):
            if details.get(key):query[key]=details[key]
    url=base+'/admin?'+urlencode(query)
    if event=='reauth':
        title='Reconnect '+label+(' — '+name if name else '')
        explanation='ASAP needs renewed access to this account to fetch new updates. Your saved posts are kept.'
        action='Reconnect account';instruction='Open Sources, choose Re-authenticate on this account, then sign in and allow access.'
    elif event=='ai_review':
        title='Your review is needed — '+label
        explanation=details.get('reason') or 'AI could not make a clear decision about this post.'
        action='Review this post';instruction='Open the post, review its content and choose Approve or Reject.'
    elif event=='duplicates':
        count=details.get('count',0);title=('Compare '+str(count)+' possible duplicate posts') if count else 'Possible duplicate posts need your review'
        explanation='These updates may describe the same news.';action='Compare posts';instruction='Compare the posts in Review Queue and choose which to publish.'
    else:
        title='New '+label+' post to review';explanation='A new update is ready in your Review Queue.'
        action='Review this post';instruction='Check the post and choose Approve or Reject.'
    paragraphs=[account,explanation]
    if event not in ('reauth','duplicates') and details.get('excerpt'):paragraphs.append(details['excerpt'])
    if event=='duplicates':paragraphs.extend(details.get('examples',[]))
    paragraphs.append(instruction)
    original=details.get('original','');original=original if urlparse(original).scheme in ('http','https') else ''
    settings=base+'/admin?view=settings'
    result=EmailMessage();result['From']=os.environ.get('ASAP_SMTP_FROM','ASAP <noreply@asap.surf>');result['To']=recipient;result['Subject']='ASAP: '+title
    result.set_content(title+'\n\n'+'\n\n'.join(paragraphs)+'\n\n'+action+': '+url+('\nOriginal post: '+original if original and event!='duplicates' else '')+'\n\nNotification settings: '+settings)
    body=''.join('<p style="line-height:1.5;white-space:pre-wrap">'+escape(p)+'</p>' for p in paragraphs)
    result.add_alternative('<html><head><meta charset="utf-8"></head><body style="font:15px Arial;color:#172536"><div style="max-width:600px;margin:auto;padding:24px"><b style="color:#205bc1">ASAP</b><h2>'+escape(title)+'</h2>'+body+'<p><a style="display:inline-block;padding:12px 18px;background:#205bc1;color:white;text-decoration:none;border-radius:6px" href="'+escape(url,quote=True)+'">'+escape(action)+'</a></p>'+('<p><a href="'+escape(original,quote=True)+'">Open original post</a></p>' if original and event!='duplicates' else '')+'<p style="font-size:12px"><a href="'+escape(settings,quote=True)+'">Notification settings</a></p></div></body></html>',subtype='html')
    return result
