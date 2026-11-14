"""One current public organization profile shared by all its saved posts."""
from .embed_presentation import RepostPresentation,media_url
import re


def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS source_profiles (platform TEXT NOT NULL, account_id TEXT NOT NULL, name TEXT NOT NULL, avatar TEXT NOT NULL, checked_at REAL NOT NULL, PRIMARY KEY(platform,account_id))')


def parse(html):
    parser=RepostPresentation(set());parser.feed(html);parser.close()
    profile=parser.result['source']
    if not profile.get('name'):raise ValueError('Public organization profile unavailable')
    avatar=media_url(profile.get('avatar',''))
    # LinkedIn's generic static organization icon is not an actual Page logo.
    if avatar.startswith('https://static.licdn.com/'):avatar=''
    return dict(name=' '.join(profile['name'].split()),avatar=avatar)


def refresh(conn,platform,account,posts,now,*,force=False,reader=None):
    if platform!='linkedin':return
    initialize(conn)
    row=conn.execute('SELECT checked_at FROM source_profiles WHERE platform=? AND account_id=?',(platform,account)).fetchone()
    if row and not force and row[0]>now-3600:return
    post=next((p for p in posts if p.get('platform')==platform and p.get('account_id')==account and re.fullmatch(r'urn:li:(?:share|ugcPost):[0-9]+',p.get('post_id',''))),None)
    if not post:return
    if reader is None:
        from .embed_review import read_public
        reader=read_public
    try:profile=parse(reader('https://www.linkedin.com/embed/feed/update/'+post['post_id']))
    except Exception:return  # Profile failure must not fail ingestion or erase last known logo.
    with conn:
        conn.execute('INSERT OR REPLACE INTO source_profiles VALUES (?,?,?,?,?)',(platform,account,profile['name'],profile['avatar'],now))


def attach(conn,posts):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_profiles'").fetchone():return
    profiles={(a,b):dict(name=n,avatar=u) for a,b,n,u in conn.execute('SELECT platform,account_id,name,avatar FROM source_profiles')}
    for post in posts:
        profile=profiles.get((post['platform'],post['account_id']))
        if profile is not None:post['metadata']['source_profile']=profile
