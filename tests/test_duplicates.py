"""Offline FR-5 verification; synthetic policy cases only."""

import copy
import sqlite3
import unittest

from src.duplicates import exact_text_groups, mark_duplicate_candidates
from src.relevance import mark_candidates
from src.store_poc import load_posts, normalize_x, store


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.posts = [normalize_x({"id": key, "text": text}, {}) for key, text in
                      [("A", "New paper published"), ("B", " New  paper\npublished "), ("C", "Different announcement")]]
        self.posts[1]["platform"] = "bluesky"
        store(self.conn, self.posts)

    def test_cross_platform_exact_match_and_nonmatch(self):
        """Verifies FR-5: whitespace-normalized matches group across providers."""
        original = copy.deepcopy(self.posts)
        groups = exact_text_groups(self.posts)
        self.assertEqual(list(groups.values()), [[("bluesky", "B"), ("x", "A")]])
        self.assertEqual(self.posts, original)
        self.assertEqual(exact_text_groups(list(reversed(self.posts))), groups)

    def test_empty_case_and_punctuation_are_conservative(self):
        """Verifies FR-5: blank text, case and punctuation do not over-group."""
        posts = [{"platform": "x", "post_id": str(i), "text": text} for i, text in
                 enumerate(["", "  ", "Paper", "paper", "Paper!"])]
        self.assertEqual(exact_text_groups(posts), {})

    def test_source_and_editorial_state_unchanged(self):
        """Verifies FR-5: all raw/source rows survive; no approval or representative."""
        before = self.conn.execute("SELECT * FROM posts ORDER BY platform, post_id").fetchall()
        candidates = mark_candidates(self.conn, load_posts(self.conn))
        groups = mark_duplicate_candidates(self.conn, candidates)
        self.assertEqual(len(groups), 1)
        self.assertEqual(self.conn.execute("SELECT * FROM posts ORDER BY platform, post_id").fetchall(), before)
        self.assertEqual(self.conn.execute("SELECT publication_status,duplicate_group,priority FROM posts").fetchall(), [("pending", None, None)] * 3)

    def test_reprocessing_removes_stale_derived_groups_only(self):
        """Verifies FR-5: full candidate re-evaluation is idempotent and reversible."""
        mark_duplicate_candidates(self.conn, self.posts)
        mark_duplicate_candidates(self.conn, self.posts)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM duplicate_candidates").fetchone()[0], 2)
        mark_duplicate_candidates(self.conn, [self.posts[0], self.posts[2]])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM duplicate_candidates").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 3)

    def test_filtered_posts_are_not_grouped(self):
        """Verifies FR-4/FR-5: detection consumes only relevance candidates."""
        candidates = mark_candidates(self.conn, self.posts, [lambda post: post["post_id"] != "B"])
        self.assertEqual(mark_duplicate_candidates(self.conn, candidates), {})

    def test_strategy_is_replaceable(self):
        """Verifies FR-5: strategy boundary exists without adding a fuzzy policy."""
        self.assertEqual(mark_duplicate_candidates(self.conn, self.posts, strategy=lambda posts: {}), {})
