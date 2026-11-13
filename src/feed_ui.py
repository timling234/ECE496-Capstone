"""FR-9: approved-only horizontal News feed, adapted visually from user screenshot.
REF-MSRG-NEWS: layout reference only; no MSRG/Elfsight implementation copied.
"""

import html
import re
from urllib.parse import urlencode


def appearance_overrides(query):
    result={}
    accent=query.get('accent',[''])[0]
    if re.fullmatch(r'#[0-9a-fA-F]{6}',accent):result['accent']=accent
    try:
        size=int(query.get('font_size',[''])[0])
        if 12<=size<=24:result['font_size']=size
    except (ValueError,TypeError):pass
    origin=query.get('show_origin',[''])[0]
    if origin in ('0','1'):result['show_origin']=int(origin)
    return result


FEED_STYLE = """<style>
body{max-width:none;margin:0;padding:0;background:white}body>h1{display:none}.news-carousel{position:relative;padding:0 0 30px;font-family:Arial,system-ui,sans-serif}.news-page{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;align-items:start;padding:0 0 4px}.news-card{min-width:0;background:#f7f7f7;border:0!important;border-radius:8px!important;padding:16px!important;box-sizing:border-box;margin:0!important;overflow:hidden}.news-publisher{display:flex;gap:8px;align-items:center;margin:0 0 12px;min-width:0}.news-identity{min-width:0;flex:1}.news-name{display:block;font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#151515}.news-date{display:block;color:#666;font-size:13px;line-height:1.3;margin-top:2px}.news-avatar{width:30px!important;height:30px!important;max-height:none!important;object-fit:cover;border-radius:50%!important;flex:none;display:grid;place-items:center;background:#eee;color:#999}.news-avatar svg{width:22px;height:22px}.news-platform svg{width:20px;height:20px;display:block}.news-post{background:#eee;border:1px solid #dfdfdf;border-radius:8px;overflow:hidden}.news-media{display:block;aspect-ratio:1/1;overflow:hidden;background:#eee}.news-media img{display:block;width:100%;height:100%;max-height:none;object-fit:cover;border-radius:0}.news-inner{padding:16px}.news-author{display:flex;align-items:center;gap:9px;margin:0 0 12px;min-width:0}.news-author .news-avatar{width:32px!important;height:32px!important}.news-card .content{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.35;margin:0;color:#222}.news-card .content.collapsed{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;max-height:4.05em;overflow:hidden}.news-card [data-read-more]{display:block;border:0;background:none;padding:0;margin:0;color:#1683ff;font:inherit;line-height:1.35;cursor:pointer;text-decoration:none}.news-card [data-read-more][hidden]{display:none}.news-tag{color:#1683ff}.news-actions{display:flex;align-items:center;gap:16px;padding-top:12px;color:#666;font-size:13px}.news-actions a,.news-actions button{display:inline-flex;align-items:center;gap:5px;color:inherit;background:none;border:0;padding:0;text-decoration:none;font:inherit;cursor:pointer}.news-actions svg{width:18px;height:18px}.news-actions .news-share{margin-left:auto}.news-arrow{position:absolute;top:calc(50% - 28px);z-index:2;border:0;border-radius:50%;background:#888e;color:white;box-shadow:0 2px 8px #0003;width:34px;height:34px;display:grid;place-items:center;padding:0;cursor:pointer}.news-arrow svg{width:18px;height:18px}.news-prev{left:-16px}.news-next{right:-16px}.news-dots{position:relative;display:flex;gap:5px;justify-content:center;align-items:center;min-height:14px;margin-top:14px}.news-dots button{padding:0;border:0;width:6px;height:6px;background:#999;border-radius:50%;cursor:pointer}.news-dots button[aria-current=page]{background:#111}.news-carousel [hidden]{display:none!important}.news-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.news-carousel button:focus-visible,.news-carousel a:focus-visible{outline:2px solid #215e95;outline-offset:3px}.demo-banner{padding:10px;border:1px solid #b8cbe3;background:#edf4fc;font:13px system-ui;color:#244568;margin-bottom:12px}@media(max-width:900px){.news-page{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.news-page{grid-template-columns:1fr}.news-card{padding:14px!important}}
</style>"""


def icon(name):
    shapes={'heart':'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>',
            'comment':'<path d="M21 11.5a9 9 0 0 1-9 9 9 9 0 0 1-4-.9L3 21l1.4-4.7A9 9 0 1 1 21 11.5z"/>',
            'share':'<path d="M14 3l7 6-7 6V11C8 11 4 14 3 20c0-10 4-14 11-14V3z"/>',
            'next':'<path d="m9 4 8 8-8 8"/>','prev':'<path d="m15 4-8 8 8 8"/>',
            'person':'<circle cx="12" cy="7" r="4" fill="currentColor" stroke="none"/><path d="M4 22v-4a8 8 0 0 1 16 0v4" fill="currentColor" stroke="none"/>'}
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true">'+shapes[name]+'</svg>'


def platform_icon(platform):
    if platform=='linkedin':return '<svg viewBox="0 0 24 24" aria-label="LinkedIn"><rect width="24" height="24" rx="2" fill="#0967c2"/><text x="3" y="19" font-family="Arial" font-size="21" font-weight="bold" fill="white">in</text></svg>'
    if platform=='x':return '<svg viewBox="0 0 24 24" aria-label="X"><path d="M4 3h5l12 18h-5L4 3zm0 18L20 3" fill="none" stroke="currentColor" stroke-width="2"/></svg>'
    return '<svg viewBox="0 0 24 24" aria-label="Bluesky"><path d="M12 11C7 2 1 1 2 8c0 4 4 5 8 5-7 0-7 7-3 8 3 1 4-3 5-6 1 3 2 7 5 6 4-1 4-8-3-8 4 0 8-1 8-5 1-7-5-6-10 3z" fill="#1683ff"/></svg>'


def feed_body(posts,settings,esc,safe_url):
    from datetime import datetime
    def date(value):
        try:
            d=datetime.fromisoformat(value.replace('Z','+00:00'));return d.strftime('%B')+' '+str(d.day)
        except (ValueError,TypeError,AttributeError):return 'Date unavailable'
    def avatar(url):
        url=safe_url(url)
        return '<img class="news-avatar" loading="lazy" referrerpolicy="no-referrer" src="'+esc(url)+'" alt="">' if url else '<span class="news-avatar">'+icon('person')+'</span>'
    cards=[]
    for p in posts:
        md=p.get('metadata',{});raw=p.get('raw',{})
        native=(raw.get('post') or {}).get('author') or {}
        label=md.get('source_label') or native.get('displayName') or p['account_id'] or 'Announcement'
        is_repost=bool(md.get('is_repost'))
        attribution=(md.get('attribution') or {}) if is_repost else {}
        publisher_label=label+' reposted' if is_repost else label
        publisher_date=md.get('reposted_at') or p['created_at'] if is_repost else p['created_at']
        original=safe_url(p['post_url'])
        body='<article class="news-card" data-platform="'+esc(p['platform'])+'" data-post-id="'+esc(p['post_id'])+'"><div class="news-publisher">'+avatar(md.get('source_avatar') or native.get('avatar'))+'<div class="news-identity"><span class="news-name" title="'+esc(publisher_label)+'">'+esc(publisher_label)+'</span><time class="news-date">'+esc(date(publisher_date))+'</time></div>'+('<span class="news-platform">'+platform_icon(p['platform'])+'</span>' if settings['show_origin'] else '')+'</div><section class="news-post">'
        for media in p['media'][:1]:
            url=safe_url(media.get('fullsize') or media.get('url') or media.get('preview_image_url'))
            if url:body+='<a class="news-media" href="'+esc(original or url)+'" target="_blank" rel="noopener noreferrer"><img loading="lazy" referrerpolicy="no-referrer" src="'+esc(url)+'" alt="'+esc(media.get('alt','Post image'))+'"></a>'
        body+='<div class="news-inner">'
        if attribution.get('name'):
            body+='<div class="news-author" title="Original author of this repost">'+avatar(attribution.get('avatar'))+'<div class="news-identity"><span class="news-name">'+esc(attribution['name'])+'</span><time class="news-date">'+esc(date(attribution.get('date') or p['created_at']))+'</time></div></div>'
        chunks=re.split(r'((?<![\w])#[\w]+)',p['text'])
        text=''.join('<span class="news-tag">'+esc(chunk)+'</span>' if re.fullmatch(r'#[\w]+',chunk) else esc(chunk) for chunk in chunks)
        body+='<p class="content">'+text+'</p><button type="button" data-read-more aria-expanded="false" hidden>Read more</button></div></section>'
        if original:
            body+='<footer class="news-actions"><a title="Like on original platform" aria-label="Like on original platform" href="'+esc(original)+'" target="_blank" rel="noopener noreferrer">'+icon('heart')+'</a><a title="Read comments on original platform" aria-label="Read comments on original platform" href="'+esc(original)+'" target="_blank" rel="noopener noreferrer">'+icon('comment')+'</a><button type="button" class="news-share" data-share="'+esc(original)+'">'+icon('share')+'<span>Share</span></button></footer>'
        others=sorted({source['name'] for source in md.get('repost_sources',[]) if source.get('name') and source['name']!=md.get('source_account_name')})
        if others:body+='<p class="news-other-sources">Also reposted by '+esc(', '.join(others))+'</p>'
        cards.append(body+'</article>')
    pages=['<div class="news-page">'+''.join(cards[i:i+4])+'</div>' for i in range(0,len(cards),4)]
    return FEED_STYLE+'<section class="news-carousel" aria-label="Published news"><div class="news-pages">'+(''.join(pages) or '<p>No published updates yet.</p>')+'</div><button type="button" class="news-arrow news-prev" aria-label="Previous page" hidden>'+icon('prev')+'</button><button type="button" class="news-arrow news-next" aria-label="Next page" hidden>'+icon('next')+'</button><nav class="news-dots" aria-label="News pages"></nav><span class="news-sr" data-page-status aria-live="polite"></span></section><script src="/assets/feed.js?v=carousel-2" defer></script>'


def mock_body(query=None):
    """Public, bounded integration fixture; no host scripts or private data."""
    query=query or {}
    template=query.get('template',['research'])[0]
    theme=query.get('theme',['light'])[0]
    try:height=max(320,min(1000,int(query.get('height',['620'])[0])))
    except (ValueError,TypeError):height=620
    dark=theme=='dark'
    colors=('#151e2b','#edf2fa','#202e41','#33465e') if dark else ('#f5f7fb','#172536','#ffffff','#dce3ee')
    background,text,panel,border=colors
    research=template!='simple'
    overrides=appearance_overrides(query)
    sample=query.get('sample',['0'])[0]=='1'
    feed=('/demo-feed' if sample else '/feed')+('?' + urlencode(overrides) if overrides else '')
    brand='MSRG' if research else 'Community'
    heading='Research, people, and ideas.' if research else 'What’s happening.'
    return ('<style>body{max-width:1200px;margin:0 auto;padding:24px;background:'+background+';color:'+text+';font-family:system-ui}body>h1{display:none}.demo-banner{padding:12px;border:1px solid #b8cbe3;border-radius:8px;background:#edf4fc;color:#244568;font:14px system-ui;margin-bottom:16px}.mock-nav{display:flex;justify-content:space-between;align-items:center;padding:12px 0 24px;border-bottom:1px solid '+border+'}.mock-nav b{font-size:24px}.mock-label{font-size:12px;color:'+text+'}.mock-hero{padding:36px 0}.mock-hero h2{font-size:clamp(26px,5vw,44px);margin:0 0 12px}.mock-news{background:'+panel+';border:1px solid '+border+';border-radius:24px;padding:20px}iframe{display:block;width:100%;height:'+str(height)+'px;border:0;border-radius:8px}.mock-news h2{margin:0 0 16px;font-size:22px}footer{font-size:12px;padding:24px 0}@media(max-width:500px){body{padding:14px}.mock-news{padding:12px}.mock-nav{gap:16px;align-items:start}}</style>'
        +'<div class="demo-banner" role="note"><b>Mock website for testing purpose</b> · Demonstration only · '+('Authorized reference snapshots + fictional samples' if sample else 'Your published public feed')+'</div>'
        +('<nav class="mock-nav" aria-label="Demo navigation"><b>ASAP Demo Research Group</b><span><a href="#demo-news">News</a> · <a href="#demo-research">Research</a></span></nav><section class="mock-hero"><h2>Systems research, in preview.</h2><p>A fictional research group website for integration testing.</p></section><h2 style="font-family:Georgia,serif;font-size:22px;margin:12px 0 16px">News</h2>' if research else '<div class="mock-nav"><b>'+brand+'</b><span class="mock-label">ASAP integration demo</span></div><section class="mock-hero"><h2>'+heading+'</h2><p>The latest updates from our community.</p></section>')+'<section id="demo-news" class="mock-news">'+('' if research else '<h2>News</h2>')+'<iframe title="Approved news integration preview" src="'+html.escape(feed,quote=True)+'" loading="lazy" data-feed-frame data-min-height="'+str(height)+'"></iframe>'+('<p><a href="https://www.linkedin.com/company/middleware-systems-research-group/" target="_blank" rel="noopener noreferrer">Read MSRG news on LinkedIn →</a></p>' if research else '')+'</section>'+('<section id="demo-research" class="mock-hero"><h2>Research themes</h2><p>Data systems · Reliable services · Community platforms</p><p>All descriptions on this page are fictional demonstration content.</p></section>' if research else '')+'<footer>Mock website for testing purpose · Not an official MSRG website.</footer><script src="/assets/mock.js?v=2" defer></script>')
