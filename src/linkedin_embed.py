"""Build official embeds from validated LinkedIn wrapper identities only."""
import re


def embed_url(post):
    if post.get('platform')!='linkedin' or not post.get('metadata',{}).get('is_repost'):
        return ''
    identity=post.get('post_id','')
    if not isinstance(identity,str) or not re.fullmatch(r'urn:li:(?:ugcPost|share):[0-9]+',identity):
        return ''
    return 'https://www.linkedin.com/embed/feed/update/'+identity


def embed_frame(post,esc):
    url=embed_url(post)
    if not url:return ''
    return '<iframe class="linkedin-repost-frame" src="'+esc(url)+'" title="LinkedIn repost" loading="lazy" height="620" style="display:block;width:100%;height:620px;border:0" allowfullscreen></iframe>'
