"""Small X/Bluesky ingestion proof of concept; standard library only."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__:
    from .relevance import mark_candidates
else:
    from relevance import mark_candidates

ROOT = Path(__file__).resolve().parents[1]
X_TOKEN = ROOT / "asap_test_lab_x_twitter_bearer_token.txt"
X_USER_ID = "2100252721475448832"
BSKY_HANDLE = "asaptestlab.bsky.social"


def fetch_json(url, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


# FR-1: Source ingestion (X proof of concept)
def fetch_x(limit):
    if not X_TOKEN.is_file():
        raise RuntimeError("X token file is missing")
    token = X_TOKEN.read_text(encoding="utf-8-sig").strip()
    if not token:
        raise RuntimeError("X token file is empty")
    params = {
        "max_results": max(5, min(limit, 100)),
        "tweet.fields": "created_at,attachments,entities",
        "expansions": "attachments.media_keys",
        "media.fields": "type,url,preview_image_url,width,height",
    }
    payload = fetch_json(f"https://api.x.com/2/users/{X_USER_ID}/tweets?{urlencode(params)}", token)
    if payload.get("errors"):
        raise RuntimeError("X API returned errors")
    media = {m["media_key"]: m for m in payload.get("includes", {}).get("media", [])}
    return [(post, media) for post in payload.get("data", [])[:limit]]


# FR-1: Source ingestion (Bluesky proof of concept)
def fetch_bluesky(limit):
    params = urlencode({"actor": BSKY_HANDLE, "limit": limit})
    payload = fetch_json(f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?{params}")
    return payload.get("feed", [])


# FR-2: Common post representation
# REF-HORIZON-02: provider-independent content model (adapted concept; independent code)
def normalize_x(post, media):
    keys = post.get("attachments", {}).get("media_keys", [])
    return {
        "platform": "x", "account_id": X_USER_ID, "post_id": post["id"],
        "created_at": post.get("created_at"), "text": post.get("text", ""),
        "post_url": f"https://x.com/i/web/status/{post['id']}",
        "links": [u.get("expanded_url") or u.get("url") for u in post.get("entities", {}).get("urls", [])],
        "media": [media[k] for k in keys if k in media],
        "metadata": {"entities": post.get("entities", {}), "attachments": post.get("attachments", {})},
        "raw": post,
    }


# FR-2: Common post representation
# REF-HORIZON-02: provider-independent content model (adapted concept; independent code)
def normalize_bluesky(item):
    post = item["post"]
    record = post.get("record", {})
    author = post.get("author", {})
    uri = post["uri"]
    rkey = uri.rsplit("/", 1)[-1]
    handle = author.get("handle", BSKY_HANDLE)
    facets = record.get("facets", [])
    links = [feature["uri"] for facet in facets for feature in facet.get("features", []) if feature.get("$type") == "app.bsky.richtext.facet#link" and "uri" in feature]
    embed = post.get("embed", {})
    return {
        "platform": "bluesky", "account_id": author.get("did") or handle,
        "post_id": uri, "created_at": record.get("createdAt"),
        "text": record.get("text", ""),
        "post_url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        "links": links, "media": embed.get("images", []),
        "metadata": {"cid": post.get("cid"), "embed": embed, "facets": facets},
        "raw": item,
    }


# FR-3: Persistent provenance and state
def store(conn, posts):
    conn.execute("""CREATE TABLE IF NOT EXISTS posts (
        platform TEXT NOT NULL, post_id TEXT NOT NULL, account_id TEXT NOT NULL,
        created_at TEXT, text TEXT NOT NULL, post_url TEXT NOT NULL,
        links_json TEXT NOT NULL, media_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL, raw_json TEXT NOT NULL,
        publication_status TEXT NOT NULL DEFAULT 'pending',
        duplicate_group TEXT, priority INTEGER,
        fetched_at TEXT NOT NULL,
        PRIMARY KEY (platform, post_id)
    )""")
    now = datetime.now(timezone.utc).isoformat()
    for post in posts:
        conn.execute("""INSERT INTO posts
            (platform, post_id, account_id, created_at, text, post_url,
             links_json, media_json, metadata_json, raw_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, post_id) DO UPDATE SET
            account_id=excluded.account_id, created_at=excluded.created_at,
            text=excluded.text, post_url=excluded.post_url,
            links_json=excluded.links_json, media_json=excluded.media_json,
            metadata_json=excluded.metadata_json, raw_json=excluded.raw_json,
            fetched_at=excluded.fetched_at""", (
                post["platform"], post["post_id"], post["account_id"],
                post["created_at"], post["text"], post["post_url"],
                json.dumps(post["links"]), json.dumps(post["media"]),
                json.dumps(post["metadata"]), json.dumps(post["raw"]), now,
            ))


# FR-3: Persistent provenance and state (read stored common representation)
def load_posts(conn):
    """Read saved records without fetching providers or changing decisions."""
    cursor = conn.execute("SELECT * FROM posts ORDER BY platform, post_id")
    columns = [column[0] for column in cursor.description]
    posts = []
    for values in cursor:
        post = dict(zip(columns, values))
        for field in ("links", "media", "metadata", "raw"):
            post[field] = json.loads(post.pop(field + "_json"))
        posts.append(post)
    return posts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / ".tmp" / "store_poc.sqlite3")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--provider", choices=["x", "bluesky", "both"], default="both")
    parser.add_argument("--inspect", action="store_true", help="Read existing database counts without API calls or writes.")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.inspect:
        try:
            # mode=ro prevents accidentally creating or modifying the database.
            with closing(sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                posts = load_posts(conn)
            counts = {}
            for post in posts:
                counts[post["platform"]] = counts.get(post["platform"], 0) + 1
            print(f"stored post counts: {counts}")
            return 0
        except (OSError, sqlite3.Error, ValueError, TypeError):
            print("Unable to inspect existing Store database.")
            return 1
    posts = []
    for provider in (["x", "bluesky"] if args.provider == "both" else [args.provider]):
        try:
            batch = ([normalize_x(p, m) for p, m in fetch_x(args.limit)] if provider == "x"
                     else [normalize_bluesky(p) for p in fetch_bluesky(args.limit)])
            posts.extend(batch)
            print(f"{provider}: fetched {len(batch)}")
        except Exception as exc:
            # API responses may contain credentials or private data; keep errors terse.
            print(f"{provider}: fetch failed ({type(exc).__name__})")
            return 1
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(args.db)) as conn:
        with conn:
            store(conn, posts)
            # FR-4: Empty MVP rule configuration admits candidates, never approves.
            candidates = mark_candidates(conn, load_posts(conn), rules=())
            counts = conn.execute("SELECT platform, COUNT(*) FROM posts GROUP BY platform").fetchall()
    print(f"stored {len(posts)} fetched posts; database counts: {dict(counts)}")
    print(f"review candidates: {len(candidates)}; publication decisions unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
