"""FR-9: approved-only horizontal News feed, adapted visually from user screenshot.
REF-MSRG-NEWS: layout reference only; no MSRG/Elfsight implementation copied.
"""

FEED_STYLE = """<style>body{max-width:none;margin:0;padding:12px;background:white}body>h1{display:none}.news-track{display:flex;gap:20px;overflow-x:auto;scroll-snap-type:x mandatory;padding:8px 4px 20px}.news-card{flex:0 0 clamp(240px,27vw,340px);scroll-snap-align:start;background:#f7f7f7;border:1px solid #eee;border-radius:14px;padding:18px;box-sizing:border-box}.news-card .content{max-height:190px;overflow:auto;font-size:inherit}.news-card img{width:100%;height:240px;object-fit:contain;background:#ececec;max-height:240px}.news-head{display:flex;justify-content:space-between;gap:8px;font-weight:600}.news-date{display:block;margin-top:5px;color:#666}.news-card a{display:inline-block;margin-top:12px}.news-help{font-size:13px;color:#666;margin:8px}article.news-card{margin:0}.platform{font-size:12px;text-transform:uppercase}.news-card:focus-within{outline:2px solid #215e95}@media(max-width:600px){.news-card{flex-basis:85vw}}</style>"""


def feed_body(posts,settings,esc,safe_url):
    """FR-9: input is the existing approved-only publishable query."""
    cards=[]
    for p in posts:
        label='MSRG announcement' if p['platform']=='manual' else 'Middleware Systems Research Group'
        body='<article class="news-card"><div class="news-head"><span>'+label+'</span>'+('<span class="platform">'+esc(p['platform'])+'</span>' if settings['show_origin'] else '')+'</div><time class="news-date">'+esc((p['created_at'] or '')[:10] or 'Date unavailable')+'</time>'
        for media in p['media'][:1]:
            url=safe_url(media.get('fullsize') or media.get('url') or media.get('preview_image_url'))
            if url:body+='<img loading="lazy" referrerpolicy="no-referrer" src="'+esc(url)+'" alt="'+esc(media.get('alt','Post image'))+'">'
        body+='<p class="content">'+esc(p['text'])+'</p>'
        url=safe_url(p['post_url'])
        if url:body+='<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">Read original post ↗</a>'
        for link in p['links']:
            url=safe_url(link)
            if url:body+='<p><a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">'+esc(url)+'</a></p>'
        cards.append(body+'</article>')
    return FEED_STYLE+'<div class="news-track" role="region" aria-label="Approved MSRG news" tabindex="0">'+(''.join(cards) or '<p>No published updates yet.</p>')+'</div><p class="news-help">Scroll horizontally to browse more updates.</p>'


def mock_body():
    return '<style>body{max-width:1440px;background:#f5f7fc;font-family:Georgia,serif}.mock-news{background:white;border:1px solid #e4e6ec;border-radius:24px;padding:24px;box-shadow:0 12px 35px #1725360b}iframe{width:100%;height:620px;border:0;border-radius:12px}body>h1{font-size:25px}.mock-news h2{font-size:22px}</style><p>Middleware Systems Research Group · Local integration preview</p><h2>News</h2><section class="mock-news"><iframe title="Approved MSRG news" src="/feed" loading="lazy"></iframe><a href="https://www.linkedin.com/company/middleware-systems-research-group/" target="_blank" rel="noopener noreferrer">Read MSRG news on LinkedIn →</a></section>'
