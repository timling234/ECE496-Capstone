"""Extract data, never executable HTML, for the common feed card."""
import re
from urllib.parse import urlparse
from .embed_review import RepostText


def media_url(value):
    p=urlparse(value or '')
    return value if p.scheme=='https' and (p.hostname or '').endswith('.licdn.com') else ''


class RepostPresentation(RepostText):
    def __init__(self,identities):
        super().__init__(identities)
        self.result={'source':{},'author':{},'media':[],'runs':[]}
        self.entity=None;self.field=None;self.marks={}

    def handle_starttag(self,tag,attrs):
        a=dict(attrs);depth=len(self.stack)
        if a.get('data-test-id')=='main-feed-activity-embed-card__entity-lockup':self.entity=('source',depth)
        if self.article is not None and a.get('data-test-id')=='feed-reshare-content__entity-lockup':self.entity=('author',depth)
        if self.entity:
            target=self.result[self.entity[0]]
            if a.get('data-tracking-control-name','').endswith('actor-name'):
                self.field=('name',depth);target['url']=a.get('href','')
            if tag=='time':
                self.field=('date_label',depth)
                if a.get('datetime'):target['date']=a['datetime']
            image=a.get('data-delayed-background') or a.get('data-delayed-url') or a.get('src') or ''
            if not image:
                match=re.search(r'background-image:\s*url\([\"\']?([^\"\')]+)',a.get('style',''))
                if match:image=match[1]
            if image and (url:=media_url(image)):target['avatar']=url
        elif self.article is not None and tag in ('img','video','source'):
            url=media_url(a.get('data-delayed-url') or a.get('src') or '')
            poster=media_url(a.get('poster') or '')
            if url or poster:
                item={'url':url or poster,'alt':a.get('alt') or 'Post image','type':'video' if tag in ('video','source') and url else 'image'}
                if poster:item['preview_image_url']=poster
                if item not in self.result['media'] and len(self.result['media'])<10:self.result['media'].append(item)
        if tag=='a':self.marks[depth]=a.get('href','')
        super().handle_starttag(tag,attrs)
        if tag=='br' and self.capture is not None:self.result['runs'].append({'text':'\n'})

    def handle_data(self,data):
        if self.entity and self.field:
            target=self.result[self.entity[0]];key=self.field[0]
            target[key]=target.get(key,'')+data
        if self.capture is not None:
            run={'text':data}
            if self.marks:run['href']=self.marks[max(self.marks)]
            if 'strong' in self.stack or 'b' in self.stack:run['bold']=True
            if 'em' in self.stack or 'i' in self.stack:run['italic']=True
            self.result['runs'].append(run)
        super().handle_data(data)

    def handle_endtag(self,tag):
        super().handle_endtag(tag)
        if self.field and len(self.stack)<=self.field[1]:self.field=None
        if self.entity and len(self.stack)<=self.entity[1]:self.entity=None;self.field=None
        self.marks={d:v for d,v in self.marks.items() if d<len(self.stack)}

    def snapshot(self):
        self.result['text']=self.text()
        for entity in ('source','author'):
            for key in ('name','date_label'):
                if key in self.result[entity]:self.result[entity][key]=' '.join(self.result[entity][key].split())
        return self.result
