"""Verification usability and FR-1–5 demo regressions; no live credentials/APIs."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run_tests
from src import manual_demos


class TestRunnerTests(unittest.TestCase):
    def test_discovers_nested_tests_without_packages(self):
        """Verifies the root runner discovers automated tests in nested folders."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "nested" / "test_example.py").write_text("import unittest\nclass Example(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n", encoding="utf-8")
            with redirect_stderr(io.StringIO()) as output:
                self.assertEqual(run_tests.main(root), 0)
            self.assertIn("Ran 1 test", output.getvalue())
            self.assertIn("OK", output.getvalue())

    def test_failed_test_returns_nonzero(self):
        """Verifies a failing test produces a failed root-runner exit status."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_failure.py").write_text("import unittest\nclass Failure(unittest.TestCase):\n    def test_bad(self):\n        self.fail('synthetic failure')\n", encoding="utf-8")
            with redirect_stderr(io.StringIO()) as output:
                self.assertEqual(run_tests.main(root), 1)
            self.assertIn("FAILED", output.getvalue())

    def test_import_error_is_not_skipped(self):
        """Verifies broken test imports fail verification rather than disappear."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_broken.py").write_text("raise RuntimeError('synthetic import failure')\n", encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(run_tests.main(root), 1)


class ManualDemoTests(unittest.TestCase):
    def test_all_safe_offline_demos(self):
        """Verifies FR-1 simulated and FR-2–5/replay demonstrations without APIs."""
        with patch("src.manual_demos.fetch_x", side_effect=AssertionError("No live X")), patch("src.manual_demos.fetch_bluesky", side_effect=AssertionError("No live Bluesky")), patch("src.store_poc.X_TOKEN") as token, redirect_stdout(io.StringIO()) as output:
            token.read_text.side_effect = AssertionError("No credentials")
            self.assertTrue(all([demo() for demo in manual_demos.OFFLINE_DEMOS]))
            token.read_text.assert_not_called()
        text = output.getvalue()
        self.assertEqual(text.count("RESULT: PASS"), 8)
        self.assertIn("X post A -> duplicate group 1", text)
        self.assertIn("Bluesky post B -> duplicate group 1", text)
        self.assertIn("X post C -> no duplicate group", text)
        self.assertIn("Rows after first import: 3; after repeat import: 3", text)
        self.assertIn("Candidate != approved; publication pending: PASS", text)

    def test_menu_runs_offline_selection_and_exits(self):
        """Verifies the primary menu provides all offline FR paths together."""
        with patch("builtins.input", side_effect=["6", "0"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(manual_demos.run_menu(), 0)
        self.assertIn("ALL SAFE OFFLINE DEMOS: PASS", output.getvalue())

    def test_individual_offline_menu_paths(self):
        """Verifies FR-2/FR-3/FR-4/FR-5 menu choices are independently runnable."""
        with patch("builtins.input", side_effect=["2", "3", "4", "5", "7", "8", "0"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(manual_demos.run_menu(), 0)
        self.assertEqual(output.getvalue().count("RESULT: PASS"), 6)

    def test_live_cancel_makes_no_requests(self):
        """Verifies FR-1 live requests require affirmative confirmation."""
        with patch("builtins.input", side_effect=["3", "n"]), patch("src.manual_demos.fetch_x") as x, patch("src.manual_demos.fetch_bluesky") as bsky, redirect_stdout(io.StringIO()):
            self.assertTrue(manual_demos.demo_live_ingestion())
        x.assert_not_called()
        bsky.assert_not_called()

    def test_live_menu_success_with_mocked_providers(self):
        """Verifies FR-1 live-path controls and summary without exposing contents."""
        x, media, bsky = manual_demos.fixtures()
        x["text"] = "SYNTHETIC-SENSITIVE-CONTENT"
        with patch("builtins.input", side_effect=["3", "y"]), patch("src.manual_demos.fetch_x", return_value=[(x, media)]) as x_fetch, patch("src.manual_demos.fetch_bluesky", return_value=[bsky]) as bsky_fetch, redirect_stdout(io.StringIO()) as output:
            self.assertTrue(manual_demos.demo_live_ingestion())
        x_fetch.assert_called_once_with(3)
        bsky_fetch.assert_called_once_with(3)
        self.assertNotIn("SYNTHETIC-SENSITIVE-CONTENT", output.getvalue())
        self.assertIn("2 source rows", output.getvalue())

    def test_live_failure_does_not_print_response_details(self):
        """Verifies FR-1 failures remain clear without leaking response bodies."""
        with patch("builtins.input", side_effect=["1", "y"]), patch("src.manual_demos.fetch_x", side_effect=RuntimeError("SYNTHETIC-SECRET")), redirect_stdout(io.StringIO()) as output:
            self.assertFalse(manual_demos.demo_live_ingestion())
        self.assertIn("request failed (RuntimeError)", output.getvalue())
        self.assertNotIn("SYNTHETIC-SECRET", output.getvalue())
