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


FEED_STYLE = """<style>body{max-width:none;margin:0;padding:12px;background:white}body>h1{display:none}.news-track{display:flex;gap:20px;overflow-x:auto;scroll-snap-type:x mandatory;padding:8px 4px 20px;align-items:flex-start}.news-card{flex:0 0 calc((100% - 60px)/4);min-width:240px;max-width:340px;scroll-snap-align:start;background:#f7f7f7;border:1px solid #eee;border-radius:14px;padding:18px;box-sizing:border-box}.news-card .content{max-height:none;overflow:visible;font-size:inherit}.news-card .content.collapsed{max-height:130px;overflow:hidden}.news-card [data-read-more]{display:block;margin:10px 0 0;border:0;background:transparent;padding:0;color:inherit;font:inherit;cursor:pointer;text-decoration:underline}.news-card [data-read-more][hidden]{display:none}.demo-banner{padding:10px;border:1px solid #b8cbe3;background:#edf4fc;font:13px system-ui;color:#244568}.news-card img{width:100%;height:240px;object-fit:contain;background:#ececec;max-height:240px}.news-head>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.news-head{font-size:13px;display:flex;justify-content:space-between;gap:8px;font-weight:600}.news-date{display:block;margin-top:5px;color:#666}.news-card a{display:inline-block;max-width:100%;overflow-wrap:anywhere;word-break:break-word;white-space:normal;margin-top:12px}.news-help{font-size:13px;color:#666;margin:8px}article.news-card{margin:0}.platform{font-size:12px;text-transform:uppercase}.news-card:focus-within{outline:2px solid #215e95}@media(max-width:600px){.news-card{flex-basis:85vw}}</style>"""


def feed_body(posts,settings,esc,safe_url):
    """FR-9: input is the existing approved-only publishable query."""
    cards=[]
    for p in posts:
        label='MSRG announcement' if p['platform']=='manual' else 'Middleware Systems Research Group'
        if p['platform']=='linkedin':label='LinkedIn Page '+str(p['account_id'])
        label=p.get('metadata',{}).get('source_label') or label
        body='<article class="news-card" data-platform="'+esc(p['platform'])+'" data-post-id="'+esc(p['post_id'])+'"><div class="news-head"><span>'+esc(label)+'</span>'+('<span class="platform">'+esc(p['platform'])+'</span>' if settings['show_origin'] else '')+'</div><time class="news-date">'+esc((p['created_at'] or '')[:10] or 'Date unavailable')+'</time>'
        for media in p['media'][:1]:
            url=safe_url(media.get('fullsize') or media.get('url') or media.get('preview_image_url'))
            if url:body+='<img loading="lazy" referrerpolicy="no-referrer" src="'+esc(url)+'" alt="'+esc(media.get('alt','Post image'))+'">'
        body+='<p class="content">'+esc(p['text'])+'</p><button type="button" data-read-more aria-expanded="false" hidden>Read more</button>'
        url=safe_url(p['post_url'])
        if url:body+='<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">Read original post ↗</a>'
        for link in p['links']:
            url=safe_url(link)
            if url:body+='<p><a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">'+esc(url)+'</a></p>'
        cards.append(body+'</article>')
    return FEED_STYLE+'<div class="news-track" role="region" aria-label="Approved MSRG news" tabindex="0">'+(''.join(cards) or '<p>No published updates yet.</p>')+'</div><p class="news-help">Scroll horizontally to browse more updates.</p><script src="/assets/feed.js?v=stage4" defer></script>'


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
        +'<div class="demo-banner" role="note"><b>Mock website for testing purpose</b> · Demonstration only · '+('Fictional sample posts' if sample else 'Your published public feed')+'</div>'
        +('<nav class="mock-nav" aria-label="Demo navigation"><b>ASAP Demo Research Group</b><span><a href="#demo-news">News</a> · <a href="#demo-research">Research</a></span></nav><section class="mock-hero"><h2>Systems research, in preview.</h2><p>A fictional research group website for integration testing.</p></section><h2 style="font-family:Georgia,serif;font-size:22px;margin:12px 0 16px">News</h2>' if research else '<div class="mock-nav"><b>'+brand+'</b><span class="mock-label">ASAP integration demo</span></div><section class="mock-hero"><h2>'+heading+'</h2><p>The latest updates from our community.</p></section>')+'<section id="demo-news" class="mock-news">'+('' if research else '<h2>News</h2>')+'<iframe title="Approved news integration preview" src="'+html.escape(feed,quote=True)+'" loading="lazy"></iframe>'+('<p><a href="https://www.linkedin.com/company/middleware-systems-research-group/" target="_blank" rel="noopener noreferrer">Read MSRG news on LinkedIn →</a></p>' if research else '')+'</section>'+('<section id="demo-research" class="mock-hero"><h2>Research themes</h2><p>Data systems · Reliable services · Community platforms</p><p>All descriptions on this page are fictional demonstration content.</p></section>' if research else '')+'<footer>Mock website for testing purpose · Not an official MSRG website.</footer>')
