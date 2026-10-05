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
    buckets = defaultdict(set)
    for post in posts:
        text = " ".join(post["text"].split())
        if text:
            buckets[text].add((post["platform"], post["post_id"]))
    return {
        "exact-v1:" + hashlib.sha256(text.encode("utf-8")).hexdigest(): sorted(members)
        for text, members in buckets.items() if len(members) > 1
    }


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
    return groups
