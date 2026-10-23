"""Deterministic FR-5 demo; isolated temporary SQLite, no APIs or credentials."""

import argparse
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .duplicates import mark_duplicate_candidates
from .relevance import mark_candidates
from .store_poc import load_posts, normalize_bluesky, normalize_x, store
from .store_poc import main as store_main


# FR-4/FR-5: Safe offline demonstration and persisted-result inspection
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reprocess", action="store_true", help="Also exercise offline reprocessing on the temporary demo database.")
    args = parser.parse_args()
    posts = [
        normalize_x({"id": "A", "text": "New paper published"}, {}),
        normalize_bluesky({"post": {"uri": "at://did:plc:demo/app.bsky.feed.post/B",
                          "record": {"text": "New paper published"}}}),
        normalize_x({"id": "C", "text": "Different announcement"}, {}),
    ]
    with tempfile.TemporaryDirectory(prefix="asap-fr5-") as directory:
        path = Path(directory) / "demo.sqlite3"
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, posts)
                candidates = mark_candidates(conn, load_posts(conn))
                groups = mark_duplicate_candidates(conn, candidates)
        if args.reprocess:
            if store_main(["--reprocess", "--db", str(path)]) != 0:
                return 1
        with closing(sqlite3.connect(path)) as conn:
            rows = conn.execute("""SELECT p.platform, p.post_id, p.text,
                d.group_id, r.status, p.publication_status FROM posts p
                JOIN relevance r USING(platform, post_id)
                LEFT JOIN duplicate_candidates d USING(platform, post_id)
                ORDER BY p.platform, p.post_id""").fetchall()
            print("SQLite persisted results (isolated temporary database):")
            for platform, post_id, text, group, relevance, publication in rows:
                label = post_id.rsplit("/", 1)[-1]
                print(f"{label} ({platform}): {text!r} | group={group or 'none'} | {relevance} | publication={publication}")
            print(f"posts={len(rows)}; candidates={len(candidates)}; duplicate groups={len(groups)}")
    print("Temporary demo database removed; real Store database untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
