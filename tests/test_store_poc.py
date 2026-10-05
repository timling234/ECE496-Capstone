"""Offline FR-2/FR-3 regression tests; no credentials, APIs, or live state."""

import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from unittest.mock import patch
from pathlib import Path

from src.store_poc import load_posts, main, normalize_bluesky, normalize_x, store


def x_fixture():
    return {
        "id": "101", "created_at": "2026-10-05T10:00:00Z",
        "text": "Research announcement",
        "entities": {"urls": [{"url": "https://t.co/example", "expanded_url": "https://example.org/research"}]},
        "attachments": {"media_keys": ["photo-1", "unavailable"]},
    }, {"photo-1": {"media_key": "photo-1", "type": "photo", "url": "https://example.org/photo.jpg"}}


def bluesky_fixture():
    return {"post": {
        "uri": "at://did:plc:example/app.bsky.feed.post/abc", "cid": "example-cid",
        "author": {"did": "did:plc:example", "handle": "example.bsky.social"},
        "record": {"createdAt": "2026-10-05T10:00:00Z", "text": "Research announcement",
                   "facets": [{"features": [{"$type": "app.bsky.richtext.facet#link", "uri": "https://example.org/research"}]}]},
        "embed": {"$type": "app.bsky.embed.images#view", "images": [{"fullsize": "https://example.org/photo.jpg", "alt": "Research photo"}]},
    }}


class NormalizationTests(unittest.TestCase):
    def test_normalize_x(self):
        """Verifies FR-2: source identity, timestamps, links and media."""
        post, media = x_fixture()
        original = copy.deepcopy(post)
        result = normalize_x(post, media)
        self.assertEqual(result["platform"], "x")
        self.assertEqual(result["post_id"], "101")
        self.assertEqual(result["created_at"], post["created_at"])
        self.assertEqual(result["text"], post["text"])
        self.assertEqual(result["post_url"], "https://x.com/i/web/status/101")
        self.assertEqual(result["links"], ["https://example.org/research"])
        self.assertEqual(result["media"], [media["photo-1"]])
        self.assertEqual(result["raw"], original)
        self.assertEqual(post, original)

    def test_normalize_bluesky(self):
        """Verifies FR-2: native identity, URL, link facets, images and CID."""
        item = bluesky_fixture()
        original = copy.deepcopy(item)
        result = normalize_bluesky(item)
        self.assertEqual(result["account_id"], "did:plc:example")
        self.assertEqual(result["post_id"], item["post"]["uri"])
        self.assertEqual(result["post_url"], "https://bsky.app/profile/example.bsky.social/post/abc")
        self.assertEqual(result["links"], ["https://example.org/research"])
        self.assertEqual(result["media"], item["post"]["embed"]["images"])
        self.assertEqual(result["metadata"]["cid"], "example-cid")
        self.assertEqual(result["raw"], original)
        self.assertEqual(item, original)

    def test_missing_optional_fields(self):
        """Verifies FR-2: minimal source records still normalize."""
        results = [normalize_x({"id": "101"}, {}), normalize_bluesky({"post": {"uri": "at://did:plc:example/app.bsky.feed.post/abc"}})]
        self.assertEqual(set(results[0]), set(results[1]))
        for result in results:
            self.assertEqual(result["text"], "")
            self.assertEqual(result["links"], [])
            self.assertEqual(result["media"], [])
            self.assertIsNone(result["created_at"])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "test.sqlite3"
        self.posts = [normalize_x(*x_fixture()), normalize_bluesky(bluesky_fixture())]

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def test_persists_both_sources_after_reopen(self):
        """Verifies FR-3: common fields, raw objects and metadata survive restart."""
        with self.connect() as conn:
            store(conn, self.posts)
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM posts ORDER BY platform").fetchall()
        self.assertEqual(len(rows), 2)
        for row in rows:
            expected = next(p for p in self.posts if p["platform"] == row["platform"])
            for field in ["post_id", "account_id", "created_at", "text", "post_url"]:
                self.assertEqual(row[field], expected[field])
            for field in ["links", "media", "metadata", "raw"]:
                self.assertEqual(json.loads(row[field + "_json"]), expected[field])
            self.assertEqual(row["publication_status"], "pending")
            self.assertTrue(row["fetched_at"])

    def test_reimport_updates_content_preserving_editorial_fields(self):
        """Verifies FR-3: repeat imports preserve stored decisions and identity."""
        with self.connect() as conn:
            store(conn, self.posts)
            # Exercise reserved columns directly; no administrator policy is defined here.
            conn.execute("UPDATE posts SET publication_status='approved', duplicate_group='group-1', priority=7 WHERE platform='x'")
            updated = copy.deepcopy(self.posts)
            updated[0]["text"] = "Updated source text"
            updated[0]["raw"]["text"] = "Updated source text"
            store(conn, updated)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 2)
            row = conn.execute("SELECT text, raw_json, publication_status, duplicate_group, priority FROM posts WHERE platform='x'").fetchone()
            self.assertEqual(row[0], "Updated source text")
            self.assertEqual(json.loads(row[1])["text"], "Updated source text")
            self.assertEqual(row[2:], ("approved", "group-1", 7))

    def test_native_id_is_namespaced_by_platform(self):
        """Verifies FR-3: identity uniqueness is provider-specific, not semantic dedup."""
        self.posts[1]["post_id"] = self.posts[0]["post_id"]
        with self.connect() as conn:
            store(conn, self.posts)
            store(conn, self.posts)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 2)

    def test_failed_batch_rolls_back(self):
        """Verifies FR-3: a failed transaction does not leave a partial batch."""
        with self.connect() as conn:
            store(conn, [])
        broken = copy.deepcopy(self.posts[1])
        broken["text"] = None
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connect() as conn:
                store(conn, [self.posts[0], broken])
        with self.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)

    def test_load_posts_restores_common_representation_and_state(self):
        """Verifies FR-3: saved originals and normalized data are available offline."""
        with self.connect() as conn:
            store(conn, self.posts)
        with self.connect() as conn:
            loaded = load_posts(conn)
        self.assertEqual(len(loaded), 2)
        for post in loaded:
            expected = next(p for p in self.posts if p["platform"] == post["platform"])
            self.assertEqual({field: post[field] for field in expected}, expected)
            self.assertEqual(post["publication_status"], "pending")

    def test_inspection_is_read_only_and_does_not_fetch(self):
        """Verifies FR-3: inspection has no provider, credential or database-write side effects."""
        with self.connect() as conn:
            store(conn, self.posts)
        before = self.path.read_bytes()
        with patch("sys.argv", ["store_poc.py", "--inspect", "--db", str(self.path)]), patch("src.store_poc.fetch_x") as x, patch("src.store_poc.fetch_bluesky") as bsky, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 0)
        x.assert_not_called()
        bsky.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn("'bluesky': 1", output.getvalue())
        self.assertNotIn("Research announcement", output.getvalue())

    def test_inspection_does_not_create_missing_database(self):
        """Verifies FR-3: a missing database fails clearly without creating state."""
        with patch("sys.argv", ["store_poc.py", "--inspect", "--db", str(self.path)]), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)
        self.assertFalse(self.path.exists())


    def test_ingestion_runs_default_filter_stage(self):
        """Verifies FR-1/FR-3/FR-4: mocked ingestion stores then marks candidates."""
        with patch("sys.argv", ["store_poc.py", "--db", str(self.path)]), patch("src.store_poc.fetch_x", return_value=[x_fixture()]), patch("src.store_poc.fetch_bluesky", return_value=[bluesky_fixture()]), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)
        with self.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM relevance WHERE status='candidate'").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT publication_status FROM posts").fetchall(), [("pending",), ("pending",)])


if __name__ == "__main__":
    unittest.main()
