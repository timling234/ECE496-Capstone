"""Duplicate candidates only; no merging, ranking or publication decisions."""

import hashlib
from collections import defaultdict


# FR-5: Duplicate control (reversible initial exact-match strategy)
# REF-HORIZON-04: separate detection stage (concept only; independent code)
def exact_text_groups(posts):
    """Trim/collapse whitespace; preserve case, punctuation and Unicode spelling.

    Empty text is not evidence of a duplicate. Return stable group IDs and
    source identities; do not mutate posts or select representatives.
    """
    posts=list(posts);buckets=defaultdict(set);texts={}
    for post in posts:
        identity=(post['platform'],post['post_id']);text=' '.join(post['text'].split());texts[identity]=text
        if text:buckets[('text',text)].add(identity)
        if post['platform']=='linkedin':
            md=post.get('metadata',{})
            root=md.get('original_post_id') if md.get('is_repost') else post['post_id']
            if root:buckets[('original',root)].add(identity)
    parent={identity:identity for identity in texts}
    def find(identity):
        while parent[identity]!=identity:
            parent[identity]=parent[parent[identity]];identity=parent[identity]
        return identity
    for members in buckets.values():
        ordered=sorted(members)
        for identity in ordered[1:]:parent[find(identity)]=find(ordered[0])
    components=defaultdict(list)
    for identity in parent:components[find(identity)].append(identity)
    result={}
    for members in components.values():
        if len(members)<2:continue
        values={texts[i] for i in members}
        exact=len(values)==1 and next(iter(values))
        value=next(iter(values)) if exact else repr(sorted(members))
        prefix='exact-v1:' if exact else 'repost-v1:'
        result[prefix+hashlib.sha256(value.encode('utf-8')).hexdigest()]=sorted(members)
    return result



# FR-5: Derived duplicate-candidate state, separate from source/editorial data
def mark_duplicate_candidates(conn, candidates, strategy=exact_text_groups):
    """Replace this stage's derived membership using the full candidate set.

    Callers own the transaction. A future strategy can replace exact matching.
    The legacy posts.duplicate_group field is untouched to preserve editorial
    state. No representative is recorded or automatically selected.
    """
    groups = strategy(candidates)
    conn.execute("""CREATE TABLE IF NOT EXISTS duplicate_candidates (
        platform TEXT NOT NULL, post_id TEXT NOT NULL, group_id TEXT NOT NULL,
        PRIMARY KEY(platform, post_id)
    )""")
    conn.execute("DELETE FROM duplicate_candidates")
    conn.executemany("INSERT INTO duplicate_candidates VALUES (?, ?, ?)",
                     [(platform, post_id, group_id) for group_id, members in groups.items()
                      for platform, post_id in members])
    from .notifications import queue_event
    for group in groups:queue_event(conn,'duplicates',group,platform='duplicates',post_id=group)
    return groups
