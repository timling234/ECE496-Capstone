"""Bounded, anonymous public-embed text evidence, separate from API provenance."""
from contextlib import closing
from html.parser import HTMLParser
import hashlib
import json
import sqlite3
import time
import requests
from .linkedin_embed import embed_url


class RepostText(HTMLParser):
    def __init__(self,identities):
        super().__init__(convert_charrefs=True)
        self.identities=identities;self.stack=[];self.article=None;self.capture=None;self.parts=[];self.closed=False;self.matches=0;self.invalid=False

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='article' and attrs.get('data-test-id')=='feed-reshare-content' and attrs.get('data-attributed-urn') in self.identities:
            self.article=len(self.stack);self.matches+=1
        if self.article is not None and attrs.get('data-test-id')=='feed-reshare-content__commentary':
            if self.capture is not None or self.closed:self.invalid=True
            if 'line-clamp' in attrs.get('class','') or attrs.get('data-truncated')=='true':self.invalid=True
            self.capture=len(self.stack)
        if self.capture is not None:
            if tag=='br':self.parts.append('\n')
            if tag in ('script','style') or attrs.get('aria-hidden')=='true':self.invalid=True
        if tag not in ('br','img','meta','link','input','hr','source','wbr','area','base','embed','param','track','col'):
            self.stack.append(tag)

    def handle_endtag(self,tag):
        if tag not in self.stack:return
        depth=len(self.stack)-1-self.stack[::-1].index(tag)
        if self.capture is not None and depth<=self.capture:
            self.closed=True;self.capture=None
        if self.article is not None and depth<=self.article:self.article=None
        del self.stack[depth:]

    def handle_data(self,data):
        if self.capture is not None:self.parts.append(data)

    def text(self):
        text=''.join(self.parts).strip()
        if self.matches!=1 or not self.closed or self.invalid or not 1<=len(text)<=20000:
            raise ValueError('Original text incomplete or identity mismatch')
        return text


def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS embed_review_cache (post_id TEXT PRIMARY KEY, source_fingerprint TEXT NOT NULL, checked_at REAL NOT NULL, status TEXT NOT NULL, text TEXT NOT NULL, presentation_json TEXT)')
    if 'presentation_json' not in {r[1] for r in conn.execute('PRAGMA table_info(embed_review_cache)')}:conn.execute('ALTER TABLE embed_review_cache ADD COLUMN presentation_json TEXT')


def source_fingerprint(post):
    from .web_editorial import fingerprint
    return fingerprint(post)


def attach(conn,posts):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='embed_review_cache'").fetchone():return
    has_presentation='presentation_json' in {r[1] for r in conn.execute('PRAGMA table_info(embed_review_cache)')}
    cache={row[0]:row[1:] for row in conn.execute('SELECT post_id,source_fingerprint,checked_at,status,text'+(',presentation_json' if has_presentation else ',NULL')+' FROM embed_review_cache')}
    for p in posts:
        row=cache.get(p['post_id']) if embed_url(p) else None
        if row and row[0]==source_fingerprint(p) and row[4]:
            p['metadata']['embed_presentation']=json.loads(row[4])
        if row and row[0]==source_fingerprint(p) and row[1]>time.time()-(21600 if row[2]=='complete' else 1800):
            p['metadata']['embed_review']=dict(status=row[2],text=row[3],source='public_linkedin_embed',checked_at=row[1])


def review_text(post):
    md=post.get('metadata',{})
    evidence=md.get('embed_review',{})
    if md.get('is_repost') and md.get('original_resolution')!='available' and evidence.get('status')=='complete':
        commentary=md.get('repost_commentary','')
        return (commentary+'\n\n' if commentary else '')+evidence['text']
    return post['text']


def read_public(url):
    with requests.Session() as session:
        session.trust_env=False
        with session.get(url,timeout=(4,12),allow_redirects=False,stream=True,headers={'Accept':'text/html'}) as response:
            if response.status_code!=200 or 'text/html' not in response.headers.get('Content-Type',''):
                raise ValueError('Public embed unavailable')
            raw=bytearray()
            for chunk in response.iter_content(16384):
                raw.extend(chunk)
                if len(raw)>1048576:raise ValueError('Public embed too large')
            return raw.decode('utf-8',errors='strict')


def prepare(db,posts,reader=read_public,*,presentation=False,limit=None):
    # Run in the AI background worker, never while holding a database transaction.
    requests_made=0
    for p in posts:
        md=p.get('metadata',{});url=embed_url(p)
        if not url or (md.get('original_resolution')=='available' and not presentation):continue
        if md.get('embed_review') and (not presentation or md.get('embed_presentation') or md['embed_review']['status']!='complete'):continue
        if limit is not None and requests_made>=limit:break
        requests_made+=1
        status='unavailable';text='';snapshot=None
        try:
            from .embed_presentation import RepostPresentation
            parser=RepostPresentation({v for v in (md.get('original_post_id'),md.get('parent_post_id')) if v})
            parser.feed(reader(url));parser.close();snapshot=parser.snapshot();text=snapshot['text'];status='complete'
        except Exception:pass  # No retry/login fallback; keep manual review on failures.
        with closing(sqlite3.connect(db,timeout=15)) as conn:
            initialize(conn)
            conn.execute('INSERT OR REPLACE INTO embed_review_cache (post_id,source_fingerprint,checked_at,status,text,presentation_json) VALUES (?,?,?,?,?,?)',(p['post_id'],source_fingerprint(p),time.time(),status,text,json.dumps(snapshot) if snapshot else None));conn.commit()


def fingerprint(post):
    # AI evidence changes invalidate AI suggestions, not manual editorial decisions.
    evidence=post.get('metadata',{}).get('embed_review',{})
    return hashlib.sha256(json.dumps([source_fingerprint(post),evidence.get('status'),evidence.get('text')],ensure_ascii=False).encode()).hexdigest()
