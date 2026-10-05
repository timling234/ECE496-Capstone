"""Verifies FR-4 without choosing real relevance or publication policies."""

import copy
import sqlite3
import unittest

from src.relevance import mark_candidates
from src.store_poc import load_posts, normalize_x, store


class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        store(self.conn, [normalize_x({"id": str(i), "text": "Synthetic post"}, {}) for i in range(2)])
        self.posts = load_posts(self.conn)

    def test_empty_rules_allow_all_without_source_changes(self):
        """Verifies FR-4: all stored posts pass and source rows remain unchanged."""
        before = self.conn.execute("SELECT * FROM posts ORDER BY post_id").fetchall()
        self.assertEqual(mark_candidates(self.conn, self.posts, []), self.posts)
        self.assertEqual(self.conn.execute("SELECT * FROM posts ORDER BY post_id").fetchall(), before)
        self.assertEqual(self.conn.execute("SELECT status FROM relevance").fetchall(), [("candidate",), ("candidate",)])

    def test_candidates_are_not_approved(self):
        """Verifies FR-4: candidate status is independent of publication approval."""
        mark_candidates(self.conn, self.posts)
        self.assertEqual(self.conn.execute("SELECT publication_status FROM posts").fetchall(), [("pending",), ("pending",)])

    def test_rules_evaluate_without_deleting_or_mutating_posts(self):
        """Verifies FR-4: synthetic rules exclude candidates, preserving originals."""
        original = copy.deepcopy(self.posts)
        def synthetic_rule(post):
            accepted = post["post_id"] == "0"
            post["raw"]["text"] = "Attempted mutation"
            return accepted
        candidates = mark_candidates(self.conn, self.posts, [synthetic_rule])
        self.assertEqual([p["post_id"] for p in candidates], ["0"])
        self.assertEqual(self.posts, original)
        self.assertEqual(load_posts(self.conn), original)
        self.assertEqual(self.conn.execute("SELECT status FROM relevance ORDER BY post_id").fetchall(), [("candidate",), ("filtered",)])

    def test_rerun_is_idempotent_and_preserves_publication_state(self):
        """Verifies FR-4: re-evaluation never makes or resets editorial decisions."""
        self.conn.execute("UPDATE posts SET publication_status='approved' WHERE post_id='0'")
        mark_candidates(self.conn, self.posts, [lambda post: False])
        mark_candidates(self.conn, self.posts, [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM relevance").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT publication_status FROM posts WHERE post_id='0'").fetchone()[0], "approved")

    def test_invalid_rule_does_not_write_partial_results(self):
        """Verifies FR-4: rule failures do not silently allow content."""
        mark_candidates(self.conn, self.posts)
        before = self.conn.execute("SELECT * FROM relevance").fetchall()
        with self.assertRaises(TypeError):
            mark_candidates(self.conn, self.posts, [lambda post: None])
        self.assertEqual(self.conn.execute("SELECT * FROM relevance").fetchall(), before)
