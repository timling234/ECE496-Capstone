"""Verifies FR-6/FR-7 Option A service without deciding a final administrator UI."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.editorial import SelectionConflict, approve_representative, get_group_approval
from src.manual_demos import demo_posts
from src.store_poc import load_posts, process_stored, store


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        store(self.conn, demo_posts())
        self.candidates, self.groups = process_stored(self.conn)
        self.group_id = next(iter(self.groups))
        self.bsky_id = next(p["post_id"] for p in self.candidates if p["platform"] == "bluesky")
        self.source_snapshot = self.conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall()

    def test_pipeline_never_automatically_approves(self):
        """Verifies FR-4/FR-5/FR-6/FR-7: candidacy/grouping alone creates no approval."""
        self.assertIsNone(get_group_approval(self.conn, self.group_id))
        self.assertEqual(self.conn.execute("SELECT publication_status FROM posts").fetchall(), [("pending",)] * 3)

    def test_explicit_selection_records_one_approval_without_source_changes(self):
        """Verifies FR-6/FR-7: explicit Option A choice has separate actor/time state."""
        relevance = self.conn.execute("SELECT * FROM relevance").fetchall()
        duplicates = self.conn.execute("SELECT * FROM duplicate_candidates").fetchall()
        with self.conn:
            decision = approve_representative(self.conn, self.group_id, "x", "A", "test-admin")
        self.assertEqual((decision["platform"], decision["post_id"], decision["approved_by"]), ("x", "A", "test-admin"))
        self.assertTrue(decision["approved_at"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM group_approvals").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT * FROM posts ORDER BY platform,post_id").fetchall(), self.source_snapshot)
        self.assertEqual(self.conn.execute("SELECT * FROM relevance").fetchall(), relevance)
        self.assertEqual(self.conn.execute("SELECT * FROM duplicate_candidates").fetchall(), duplicates)

    def test_either_provider_can_be_selected(self):
        """Verifies FR-6: the service imposes no automatic platform priority."""
        with self.conn:
            decision = approve_representative(self.conn, self.group_id, "bluesky", self.bsky_id, "test-admin")
        self.assertEqual(decision["platform"], "bluesky")

    def test_second_distinct_representative_is_blocked(self):
        """Verifies FR-6/FR-7: one group cannot have two approved representatives."""
        with self.conn:
            first = approve_representative(self.conn, self.group_id, "x", "A", "test-admin")
        with self.assertRaises(SelectionConflict):
            with self.conn:
                approve_representative(self.conn, self.group_id, "bluesky", self.bsky_id, "other-admin")
        self.assertEqual(get_group_approval(self.conn, self.group_id), first)

    def test_repeated_choice_is_idempotent(self):
        """Verifies FR-6/FR-7: retry preserves the first attributable decision."""
        with self.conn:
            first = approve_representative(self.conn, self.group_id, "x", "A", "test-admin")
            repeated = approve_representative(self.conn, self.group_id, "x", "A", "retry-actor")
        self.assertEqual(repeated, first)

    def test_unknown_or_nonmember_selection_fails(self):
        """Verifies FR-6/FR-7: unrelated or nonexistent posts cannot be approved."""
        for group, platform, post_id in [("unknown", "x", "A"), (self.group_id, "x", "C"), (self.group_id, "x", "missing")]:
            with self.subTest(post_id=post_id), self.assertRaises(ValueError):
                approve_representative(self.conn, group, platform, post_id, "test-admin")
        self.assertIsNone(get_group_approval(self.conn, self.group_id))

    def test_filtered_member_is_ineligible(self):
        """Verifies FR-4/FR-6/FR-7: stale group data cannot bypass review candidacy."""
        self.conn.execute("UPDATE relevance SET status='filtered' WHERE platform='x' AND post_id='A'")
        with self.assertRaises(ValueError):
            approve_representative(self.conn, self.group_id, "x", "A", "test-admin")

    def test_actor_is_required(self):
        """Verifies FR-7: decisions require attribution (not authentication)."""
        with self.assertRaises(ValueError):
            approve_representative(self.conn, self.group_id, "x", "A", " ")

    def test_reimport_and_reprocessing_preserve_decision(self):
        """Verifies FR-3/FR-6/FR-7: processing does not overwrite explicit choice."""
        with self.conn:
            first = approve_representative(self.conn, self.group_id, "x", "A", "test-admin")
            store(self.conn, demo_posts())
            process_stored(self.conn)
        self.assertEqual(get_group_approval(self.conn, self.group_id), first)
        self.assertEqual(len(load_posts(self.conn)), 3)

    def test_decision_persists_after_reopen(self):
        """Verifies FR-3/FR-7: separate approval state survives a database reopen."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "editorial.sqlite3"
            with closing(sqlite3.connect(path)) as conn:
                with conn:
                    store(conn, demo_posts())
                    _, groups = process_stored(conn)
                    group = next(iter(groups))
                    first = approve_representative(conn, group, "x", "A", "test-admin")
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(get_group_approval(conn, group), first)

    def test_caller_rollback_removes_uncommitted_approval(self):
        """Verifies FR-7: caller controls atomic transaction completion."""
        self.conn.commit()
        with self.assertRaises(RuntimeError):
            with self.conn:
                approve_representative(self.conn, self.group_id, "x", "A", "test-admin")
                raise RuntimeError("Synthetic caller failure")
        self.assertIsNone(get_group_approval(self.conn, self.group_id))
