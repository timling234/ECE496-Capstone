"""Readable FR demos. Offline paths use synthetic posts and temporary SQLite."""

import json
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

from .duplicates import mark_duplicate_candidates
from .editorial import SelectionConflict, approve_representative, get_group_approval
from .polling import PollingSource, poll_due
from .providers import FetchBatch, Provider
from .relevance import mark_candidates
from .store_poc import (fetch_bluesky, fetch_x, load_posts, main as store_main,
                        normalize_bluesky, normalize_x, process_stored, store)

COMMON_FIELDS = ("platform", "account_id", "post_id", "created_at", "text",
                 "post_url", "links", "media", "metadata", "raw")


def fixtures():
    x = {"id": "A", "created_at": "2026-10-05T10:00:00Z", "text": "New paper published",
         "entities": {"urls": [{"expanded_url": "https://example.org/paper"}]},
         "attachments": {"media_keys": ["image-1"]}}
    media = {"image-1": {"media_key": "image-1", "type": "photo", "url": "https://example.org/photo.jpg"}}
    bsky = {"post": {"uri": "at://did:plc:demo/app.bsky.feed.post/B", "cid": "fixture-cid",
            "author": {"did": "did:plc:demo", "handle": "demo.bsky.social"},
            "record": {"text": "New paper published", "createdAt": "2026-10-05T10:00:00Z",
                       "facets": [{"features": [{"$type": "app.bsky.richtext.facet#link", "uri": "https://example.org/paper"}]}]},
            "embed": {"images": [{"fullsize": "https://example.org/photo.jpg", "alt": "Demo image"}]}}}
    return x, media, bsky


def demo_posts():
    x, media, bsky = fixtures()
    return [normalize_x(x, media), normalize_bluesky(bsky),
            normalize_x({"id": "C", "text": "Different announcement"}, {})]


@contextmanager
def temporary_database():
    with tempfile.TemporaryDirectory(prefix="asap-manual-") as directory:
        yield Path(directory) / "demo.sqlite3"
    print("Temporary demo database removed; real Store database untouched.")


def report(checks):
    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    passed = all(checks.values())
    print(f"RESULT: {'PASS' if passed else 'FAIL'}\n")
    return passed


# FR-1: Fixture ingestion exercises orchestration, not actual provider access
def demo_ingestion_offline():
    print("FR-1 Ingestion - SIMULATED fixture requests; no live API access")
    x, media, bsky = fixtures()
    with temporary_database() as path:
        with patch("src.store_poc.fetch_x", return_value=[(x, media)]), patch("src.store_poc.fetch_bluesky", return_value=[bsky]):
            code = store_main(["--db", str(path)])
        with closing(sqlite3.connect(path)) as conn:
            counts = dict(conn.execute("SELECT platform, COUNT(*) FROM posts GROUP BY platform"))
        print(f"Fixture ingestion stored: X={counts.get('x', 0)}, Bluesky={counts.get('bluesky', 0)}")
        return report({"Simulated pipeline": code == 0 and counts == {"x": 1, "bluesky": 1}})


# FR-2: Common representation demonstrated field by field
def demo_normalization():
    print("FR-2 Normalization - offline fixtures")
    posts = demo_posts()[:2]
    for label, post in zip(("X record -> common fields", "Bluesky record -> common fields"), posts):
        print(label)
        for field in COMMON_FIELDS:
            print(f"  {field}: {json.dumps(post[field], ensure_ascii=True)}")
    return report({"Same common schema": all(set(post) == set(COMMON_FIELDS) for post in posts),
                   "Content/link retained": posts[0]["text"] == posts[1]["text"] and posts[0]["links"] == posts[1]["links"],
                   "Raw provider records retained": all(bool(post["raw"]) for post in posts)})


# FR-3: Restart/readback, repeat-import identity and editorial preservation
def demo_storage():
    print("FR-3 SQLite Storage / Idempotency - offline fixtures")
    posts = demo_posts()
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, posts)
                first = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
                # Fixture setup only: demonstrate preservation, not an admin UI.
                conn.execute("UPDATE posts SET publication_status='approved', priority=7 WHERE platform='x' AND post_id='A'")
        with closing(sqlite3.connect(path)) as conn:
            restored = load_posts(conn)
            with conn:
                store(conn, posts)
            count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            editorial = conn.execute("SELECT publication_status,priority FROM posts WHERE platform='x' AND post_id='A'").fetchone()
        print(f"Rows after first import: {first}; after repeat import: {count}")
        print(f"Existing editorial fixture after repeat import: publication={editorial[0]}, priority={editorial[1]}")
        print("Reopened SQLite source rows:", [(p["platform"], p["post_id"].rsplit('/', 1)[-1]) for p in restored])
        return report({"Readback after reopen": len(restored) == 3,
                       "Original raw objects preserved": all(p["raw"] == next(x["raw"] for x in posts if x["post_id"] == p["post_id"]) for p in restored),
                       "No extra source row": first == count == 3,
                       "Editorial state preserved": editorial == ("approved", 7)})


# FR-4: No rules -> candidates; candidate state is separate from publication
def demo_filtering():
    print("FR-4 Filtering - empty rules -> all posts pass -> review candidates")
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, demo_posts())
                before = conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall()
                candidates = mark_candidates(conn, load_posts(conn), rules=[])
            statuses = conn.execute("SELECT r.platform,r.post_id,r.status,p.publication_status FROM relevance r JOIN posts p USING(platform,post_id)").fetchall()
            print("SQLite states:", [(platform, key.rsplit('/', 1)[-1], state, pub) for platform, key, state, pub in statuses])
            return report({"All stored posts become candidates": len(candidates) == 3 and all(r[2] == "candidate" for r in statuses),
                           "Source posts preserved": conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall() == before,
                           "Candidate != approved; publication pending": all(r[3] == "pending" for r in statuses)})


# FR-5: Read persisted membership without selecting or approving a representative
def demo_duplicates():
    print("FR-5 Duplicate Detection - exact normalized-text candidates")
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, demo_posts())
                before = conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall()
                candidates = mark_candidates(conn, load_posts(conn))
                relevance = conn.execute("SELECT * FROM relevance ORDER BY platform,post_id").fetchall()
                mark_duplicate_candidates(conn, candidates)
        with closing(sqlite3.connect(path)) as conn:
            rows = conn.execute("SELECT p.platform,p.post_id,d.group_id,p.publication_status FROM posts p LEFT JOIN duplicate_candidates d USING(platform,post_id) ORDER BY p.platform,p.post_id").fetchall()
            labels = {group: i + 1 for i, group in enumerate(sorted({r[2] for r in rows if r[2]}))}
            by_label = {key.rsplit('/', 1)[-1]: group for _, key, group, _ in rows}
            for platform, key, group, _ in rows:
                print(f"{'X' if platform == 'x' else 'Bluesky'} post {key.rsplit('/', 1)[-1]} -> {'duplicate group ' + str(labels[group]) if group else 'no duplicate group'}")
            print("Inspection: persisted SQLite membership joined to all source rows; no representative field assigned.")
            return report({"A + B grouped; C ungrouped": bool(by_label["A"]) and by_label["A"] == by_label["B"] and by_label["C"] is None,
                           "Source posts preserved": conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall() == before,
                           "Review candidates preserved": conn.execute("SELECT * FROM relevance ORDER BY platform,post_id").fetchall() == relevance,
                           "Publication still pending": all(r[3] == "pending" for r in rows)})


# FR-3/FR-4/FR-5: Offline replay with existing temporary data
def demo_reprocessing():
    print("Offline reprocessing - saved posts -> filter -> duplicate candidates")
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, demo_posts())
            before = conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall()
        code = store_main(["--reprocess", "--db", str(path)])
        with closing(sqlite3.connect(path)) as conn:
            groups = conn.execute("SELECT COUNT(DISTINCT group_id) FROM duplicate_candidates").fetchone()[0]
            candidates = conn.execute("SELECT COUNT(*) FROM relevance WHERE status='candidate'").fetchone()[0]
            print(f"SQLite readback: {candidates} candidates; {groups} duplicate group")
            return report({"Replay completed": code == 0 and candidates == 3 and groups == 1,
                           "Source/editorial rows unchanged": conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall() == before})


# FR-1: Explicit live path; never used by safe offline demos
def demo_live_ingestion():
    print("FR-1 Ingestion - LIVE API requests. X may consume API credits.")
    print("X: implemented POC; Bluesky: implemented POC; LinkedIn: API approval pending; scheduler: not implemented.")
    print("1. X\n2. Bluesky\n3. Both\n0. Cancel")
    selection = input("Provider: ").strip()
    providers = {"1": ["x"], "2": ["bluesky"], "3": ["x", "bluesky"]}.get(selection)
    if not providers:
        print("Live ingestion cancelled. No requests made.")
        return True
    if input("Make live API requests now? [y/N]: ").strip().lower() != "y":
        print("Live ingestion cancelled. No requests made.")
        return True
    posts, checks = [], {}
    for provider in providers:
        try:
            batch = ([normalize_x(p, m) for p, m in fetch_x(3)] if provider == "x"
                     else [normalize_bluesky(p) for p in fetch_bluesky(3)])
            print(f"{provider}: retrieved {len(batch)} post(s)")
            posts.extend(batch)
            checks[f"{provider} live request"] = True
        except Exception as error:
            # Never print error bodies, headers, token or fetched post contents.
            print(f"{provider}: request failed ({type(error).__name__})")
            checks[f"{provider} live request"] = False
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, posts)
            print(f"Temporary SQLite inspection: {len(load_posts(conn))} source rows; no real Store/cursor changes.")
    return report(checks)


# FR-6/FR-7: Scripted explicit operator choice in an isolated fixture only
def demo_representative_selection():
    print("FR-6/FR-7 Representative Selection - Option A; offline fixtures")
    print("Duplicate group: X A + Bluesky B. Neither is automatically approved.")
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                store(conn, demo_posts())
                _, groups = process_stored(conn)
                group_id = next(iter(groups))
                before = conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall()
                no_automatic_approval = get_group_approval(conn, group_id) is None
                print("Fixture operator explicitly selects X A (no platform priority).")
                decision = approve_representative(conn, group_id, "x", "A", "demo-admin")
            blocked = False
            bsky_id = next(p["post_id"] for p in load_posts(conn) if p["platform"] == "bluesky")
            try:
                with conn:
                    approve_representative(conn, group_id, "bluesky", bsky_id, "demo-admin")
            except SelectionConflict:
                blocked = True
        with closing(sqlite3.connect(path)) as conn:
            saved = get_group_approval(conn, group_id)
            count = conn.execute("SELECT COUNT(*) FROM group_approvals").fetchone()[0]
            print("X post A -> selected representative, editorial approval recorded")
            print("Bluesky post B -> not selected, not automatically rejected")
            print("X post C -> no approval recorded")
            print(f"SQLite group_approvals: representative={saved['platform']} A, actor={saved['approved_by']}, count={count}")
            print("Legacy source publication fields remain pending; no website publishing occurs.")
            return report({"No automatic approval before operator choice": no_automatic_approval,
                           "Exactly one persisted representative": count == 1 and saved == decision,
                           "Second distinct selection blocked": blocked,
                           "Original source rows preserved": conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall() == before})


# FR-1/FR-3/FR-10: Deterministic scheduler demo; no production interval decision
def demo_scheduled_polling():
    print("FR-1 Scheduled Polling - simulated providers and fake clock")
    print("Demo interval: 10 simulated seconds; no live frequency is configured.")
    class FixtureProvider(Provider):
        def __init__(self, platform, batches):
            self.platform, self.account = platform, "fixture"
            self.batches = list(batches)
        def fetch(self, checkpoint):
            result = self.batches.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
    x, media, bsky = fixtures()
    bsky_c = fixtures()[2]
    bsky_c["post"]["uri"] = "at://did:plc:demo/app.bsky.feed.post/C"
    bsky_c["post"]["record"]["text"] = "Different announcement"
    sources = [PollingSource(FixtureProvider("x", [FetchBatch([normalize_x(x, media)], "X1"), RuntimeError("Synthetic failure")]), 10, True),
               PollingSource(FixtureProvider("bluesky", [FetchBatch([normalize_bluesky(bsky)], "B1"), FetchBatch([normalize_bluesky(bsky_c)], "B2")]), 10, True)]
    with temporary_database() as path:
        with closing(sqlite3.connect(path)) as conn:
            first = poll_due(conn, sources, 0)
            waiting = poll_due(conn, sources, 5)
            second = poll_due(conn, sources, 10)
            print("t=0: X and Bluesky stored successfully.")
            print("t=5: neither source is due; no provider calls.")
            print("t=10: X fails; Bluesky still stores its new post.")
        with closing(sqlite3.connect(path)) as conn:
            restarted = poll_due(conn, sources, 15)
            states = dict(conn.execute("SELECT platform,checkpoint FROM source_poll_state"))
            count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            print(f"Reopened SQLite: X checkpoint={states['x']}; Bluesky checkpoint={states['bluesky']}; source rows={count}")
            return report({"First due poll succeeds": all(o["status"] == "ok" for o in first),
                           "Intervals honored": all(o["status"] == "not_due" for o in waiting),
                           "Provider failure isolated": [o["status"] for o in second] == ["error", "ok"],
                           "Failed checkpoint preserved": states == {"x": "X1", "bluesky": "B2"},
                           "Restart remembers due times": all(o["status"] == "not_due" for o in restarted),
                           "Successful source data retained": count == 3})


OFFLINE_DEMOS = (demo_ingestion_offline, demo_normalization, demo_storage,
                 demo_filtering, demo_duplicates, demo_reprocessing, demo_representative_selection, demo_scheduled_polling)


def run_menu():
    actions = {"1": demo_live_ingestion, "2": demo_normalization, "3": demo_storage,
               "4": demo_filtering, "5": demo_duplicates, "7": demo_representative_selection, "8": demo_scheduled_polling}
    failed = False
    while True:
        print("ECE496 Manual Verification\n\n1. FR-1 Ingestion\n2. FR-2 Normalization\n3. FR-3 SQLite Storage / Idempotency\n4. FR-4 Filtering\n5. FR-5 Duplicate Detection\n6. Run all safe offline demos\n7. FR-6/FR-7 Representative Selection\n8. FR-1 Scheduled Polling\n0. Exit")
        try:
            choice = input("Choose: ").strip()
            if choice == "0":
                return int(failed)
            if choice == "6":
                results = [demo() for demo in OFFLINE_DEMOS]
                passed = all(results)
                print(f"ALL SAFE OFFLINE DEMOS: {'PASS' if passed else 'FAIL'}")
                failed |= not passed
            elif choice in actions:
                failed |= not actions[choice]()
            else:
                print("Choose a listed menu option.")
        except EOFError:
            return int(failed)
        except KeyboardInterrupt:
            print("Verification cancelled.")
            return 130
        except Exception as error:
            print(f"Demo failed ({type(error).__name__}); RESULT: FAIL")
            failed = True
