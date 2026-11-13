"""Authorized reference snapshots and fictional render samples. Never inserted into a workspace or published."""
def sample_posts(base):
    texts=[
        'ASAP TEST POST — Paper announcement\n\nOur fictional paper “Reliable News Pipelines for Research Communities” has been accepted at the Demo Systems Workshop.\n\nThis sample mirrors the length and paragraph structure of a research announcement. It makes no claim about a real paper, conference, author or result.\n\nWe compare two illustrative pipeline designs and discuss how editors can review posts, choose a duplicate representative, and withdraw updates. All examples and values are invented for interface testing.\n\nThanks to the ASAP test team. Expand this card to check the complete text and then select Hide to collapse it.',
        'ASAP TEST POST — Presentation update\n\nThe test team has finished its fictional systems presentation. This dedicated test poster is used to check image proportions, card spacing and mobile rendering.\n\nThe event, speaker and presentation are fictional. No MSRG photos or personal profiles are reproduced.',
        'ASAP TEST POST — Seminar preview\n\nJoin our fictional seminar about dependable aggregation services.\n\nAgenda:\n• Collect sample updates\n• Review duplicates\n• Publish an approved feed\n• Verify the website embed\n\nThe chart uses synthetic values only and is not a research result. This is a demonstration of multi-paragraph content with an image.',
        'ASAP TEST POST — Community notice\n\nA short, image-free update for comparison.\n\nThis card is fictional and appears only in the Mock Website sample preview.'
    ]
    images=[None,'demo-poster.svg','demo-chart.svg',None]
    fictional=[dict(platform='linkedin' if i%2==0 else 'bluesky',post_id='sample-'+str(i+1),account_id='ASAP Test Lab',text=text,created_at='2026-11-11T12:00:00Z',media=[dict(url=base+'/assets/'+images[i],alt='Dedicated ASAP test artwork; fictional content')] if images[i] else [],links=[],post_url='',metadata={'source_label':'ASAP Test Lab · sample'}) for i,text in enumerate(texts)]

    import json
    from pathlib import Path
    reference=json.loads((Path(__file__).resolve().parents[1]/'config/reference_news.json').read_text())
    for post in reference:
        for media in post['media']:media['url']=base+media['url']
        md=post['metadata']
        if md.get('source_avatar'):md['source_avatar']=base+md['source_avatar']
        if md['attribution'].get('avatar'):md['attribution']['avatar']=base+md['attribution']['avatar']
    return reference+fictional
