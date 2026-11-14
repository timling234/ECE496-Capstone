"""Platform-scoped embed URLs and chronological public feeds."""
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

PLATFORMS=('x','bluesky','linkedin')
LABELS={'x':'X','bluesky':'Bluesky','linkedin':'LinkedIn'}


def selected(query,key='platforms'):
    if key not in query:return list(PLATFORMS)
    values={part for value in query[key] for part in value.split(',')}
    return [p for p in PLATFORMS if p in values]


def feed_url(base,platforms):
    url=urlsplit(base);params=dict(parse_qsl(url.query));params.pop('platforms',None)
    if list(platforms)!=list(PLATFORMS):params['platforms']=','.join(platforms) or 'none'
    return urlunsplit((url.scheme,url.netloc,url.path,urlencode(params),url.fragment))


def filter_posts(posts,query):
    platforms=selected(query)
    def published(post):
        try:
            date=datetime.fromisoformat((post.get('created_at') or '').replace('Z','+00:00'))
            return date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
        except (ValueError,TypeError):return float('-inf')
    # Explicit platform filters exclude local announcements; the default feed keeps them.
    return sorted((p for p in posts if p['platform'] in platforms or p['platform']=='manual' and platforms==list(PLATFORMS)),key=lambda p:(published(p),p['platform'],p['post_id']),reverse=True)


def preview(base,platforms,layout,esc):
    groups=[(LABELS[p],[p]) for p in platforms] if layout=='separate' else [('All selected platforms',platforms)]
    if not platforms:return '<p>No platforms selected.</p>'
    body=''
    for index,(label,group) in enumerate(groups):
        url=feed_url(base,group);identity='feed-embed-code'+('' if index==0 else '-'+str(index))
        snippet='<iframe src="'+esc(url)+'" title="ASAP news" style="width:100%;height:620px;border:0"></iframe>'
        body+='<section class="panel"><h3>'+esc(label)+'</h3><h4>Embed your feed</h4><p>Copy this code into your website:</p><textarea id="'+identity+'" readonly aria-label="Feed embed code" rows="3" style="width:100%;max-width:100%;font-family:monospace">'+esc(snippet)+'</textarea><button type="button" data-copy="'+identity+'">Copy embed code</button><h4>Iframe preview</h4><iframe src="'+esc(url)+'" title="'+esc(label)+' public feed preview" data-public-feed-frame style="display:block;width:100%;max-width:1120px;height:620px;margin:0 auto;border:0"></iframe></section>'
    return body


def controls(base,query,esc):
    platforms=selected(query,'feed_platforms');layout='separate' if query.get('feed_layout',[''])[0]=='separate' else 'combined'
    choices=''.join('<label><input type="checkbox" name="feed_platform" value="'+p+'" '+('checked' if p in platforms else '')+'> '+LABELS[p]+'</label> ' for p in PLATFORMS)
    choices+='<label>Feed layout <select name="feed_layout"><option value="combined">All platforms in one list</option><option value="separate" '+('selected' if layout=='separate' else '')+'>Separate list per platform</option></select></label>'
    return '<section class="panel"><h2>Public Feed</h2><div class="mock-controls" data-feed-controls>'+choices+'</div></section><div data-feed-preview-list data-feed-url="'+esc(base)+'">'+preview(base,platforms,layout,esc)+'</div>'
