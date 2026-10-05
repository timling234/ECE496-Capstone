"""Generic relevance stage. No keyword, tag or provider policy is built in."""

from copy import deepcopy


# FR-4: Relevance curation (configurable framework, default pass-through)
def mark_candidates(conn, posts, rules=()):
    """Evaluate pure boolean predicates and persist a separate relevance result.

    No rules means allow all. Configured predicates must all pass. Each receives
    an isolated copy so rules cannot mutate source records. Errors abort the
    evaluation before any results are written; callers own the transaction.
    Publication decisions are never made here.
    """
    results = []
    for post in posts:
        passed = True
        for rule in rules:
            result = rule(deepcopy(post))
            if type(result) is not bool:
                raise TypeError("Relevance rules must return a boolean")
            if not result:
                passed = False
                break
        results.append((post["platform"], post["post_id"], "candidate" if passed else "filtered"))
    conn.execute("""CREATE TABLE IF NOT EXISTS relevance (
        platform TEXT NOT NULL, post_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('candidate', 'filtered')),
        PRIMARY KEY(platform, post_id)
    )""")
    conn.executemany("""INSERT INTO relevance VALUES (?, ?, ?)
        ON CONFLICT(platform, post_id) DO UPDATE SET status=excluded.status""", results)
    return [post for post, result in zip(posts, results) if result[2] == "candidate"]
