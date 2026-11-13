"""Bounded native reshare hydration. Never substitute scraped samples for API data."""
from urllib.error import HTTPError
from urllib.parse import quote
import re

POST_URN=re.compile(r'urn:li:(?:share|ugcPost):\d+')


def original_id(post):
    context=post.get('reshareContext') or {}
    value=context.get('root') or context.get('parent')
    return value if isinstance(value,str) and POST_URN.fullmatch(value) else None


def hydrate(provider,elements,token,known_assets=None):
    from .linkedin import normalize
    roots=sorted({root for p in elements if (root:=original_id(p))})[:100]
    originals={};failures={}
    if roots:
        try:
            data=provider.request('https://api.linkedin.com/rest/posts?ids=List('+','.join(quote(i,safe='') for i in roots)+')&viewContext=READER',token=token)
            if not isinstance(data.get('results'),dict):raise ValueError('Invalid original post response')
            for key,value in data['results'].items():
                if key not in roots or value.get('id')!=key:raise ValueError('Original post identity mismatch')
                if value.get('lifecycleState')=='PUBLISHED':originals[key]=value
                else:failures[key]='unavailable'
            for key,error in data.get('errors',{}).items():
                if key in roots:failures[key]='permission_denied' if error.get('status')==403 else 'unavailable' if error.get('status') in (404,410) else 'unverified'
        except HTTPError as error:
            if error.code==401:provider.credentials.invalidate(provider.connection);raise
            if error.code not in (403,404,429):raise
            failures={key:'permission_denied' if error.code==403 else 'unverified' for key in roots}
    image_ids=set()
    for p in list(elements)+list(originals.values()):
        content=p.get('content') or {}
        media=(content.get('multiImage') or {}).get('images',[]) or ([content['media']] if content.get('media') else [])
        article=content.get('article') or {}
        if article.get('thumbnail'):media=media+[{'id':article['thumbnail']}]
        for image in media:
            urn=image.get('id','')
            if isinstance(urn,str) and re.fullmatch(r'urn:li:image:[A-Za-z0-9_-]+',urn):image_ids.add(urn)
    assets=dict(known_assets or {})
    if image_ids and len(image_ids)<=100:
        try:assets.update(provider.request('https://api.linkedin.com/rest/images?ids=List('+','.join(quote(i,safe='') for i in sorted(image_ids))+')',token=token).get('results',{}))
        except HTTPError as error:
            if error.code==401:provider.credentials.invalidate(provider.connection);raise
            if error.code not in (403,404):raise
    return [normalize(p,provider.account,provider.label,assets,originals.get(original_id(p)),failures.get(original_id(p),'unverified')) for p in elements]
