"""FR-1/FR-10 polling verification: mocked APIs, temporary databases, fake clock."""

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError
from unittest.mock import Mock

import run_polling
from src.polling import PollingSource, poll_due
from src.providers import BlueskyProvider, FetchBatch, Provider, XProvider
from src.store_poc import normalize_x


def bsky_item(key):
    return {"post": {"uri": f"at://did:plc:fixture/app.bsky.feed.post/{key}",
                     "indexedAt": "2026-10-05T10:00:00Z",
                     "record": {"text": f"Fixture {key}", "createdAt": "2026-10-05T10:00:00Z"}}}


class ScriptedProvider(Provider):
    def __init__(self, platform, account, batches):
        self.platform, self.account, self.batches = platform, account, list(batches)
        self.calls = []

    def fetch(self, checkpoint):
        self.calls.append(checkpoint)
        result = self.batches.pop(0) if self.batches else FetchBatch([], checkpoint)
        if isinstance(result, Exception):
            raise result
        return result


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.token = Path(self.directory.name) / "fixture_token.txt"
        self.token.write_text("SYNTHETIC-TOKEN", encoding="utf-8")

    def test_x_bootstrap_keeps_poc_recent_page_and_configured_account(self):
        """Verifies FR-1/FR-2: bootstrap, media and non-hardcoded source identity."""
        transport = Mock(return_value={"data": [{"id": "102", "text": "Fixture", "attachments": {"media_keys": ["m"]}}],
                                       "includes": {"media": [{"media_key": "m", "type": "photo"}]},
                                       "meta": {"next_token": "older"}})
        batch = XProvider("999", self.token, transport=transport).fetch(None)
        self.assertEqual(batch.checkpoint, "102")
        self.assertEqual(batch.posts[0]["account_id"], "999")
        self.assertEqual(batch.posts[0]["media"][0]["media_key"], "m")
        self.assertEqual(transport.call_count, 1)

    def test_x_incremental_poll_fetches_all_pages(self):
        """Verifies FR-1: all pages after since_id contribute before checkpointing."""
        transport = Mock(side_effect=[{"data": [{"id": "103"}], "meta": {"next_token": "page-2"}},
                                     {"data": [{"id": "102"}]}])
        batch = XProvider("999", self.token, transport=transport).fetch("100")
        self.assertEqual([p["post_id"] for p in batch.posts], ["103", "102"])
        self.assertEqual(batch.checkpoint, "103")
        queries = [parse_qs(urlparse(call.args[0]).query) for call in transport.call_args_list]
        self.assertEqual([q["since_id"] for q in queries], [["100"], ["100"]])
        self.assertEqual(queries[1]["pagination_token"], ["page-2"])

    def test_x_empty_poll_keeps_checkpoint(self):
        """Verifies FR-1: empty successful polling does not regress the cursor."""
        batch = XProvider("999", self.token, transport=Mock(return_value={})).fetch("100")
        self.assertEqual((batch.posts, batch.checkpoint), ([], "100"))

    def test_x_partial_error_aborts_entire_batch(self):
        """Verifies FR-1: partial API errors cannot silently advance state."""
        transport = Mock(return_value={"data": [{"id": "103"}], "errors": [{"detail": "SYNTHETIC-PRIVATE"}]})
        with self.assertRaises(ValueError):
            XProvider("999", self.token, transport=transport).fetch("100")

    def test_x_repeated_pagination_token_fails(self):
        """Verifies FR-1: malformed pagination cannot loop indefinitely."""
        transport = Mock(return_value={"data": [{"id": "103"}], "meta": {"next_token": "same"}})
        with self.assertRaises(ValueError):
            XProvider("999", self.token, transport=transport).fetch("100")
        self.assertEqual(transport.call_count, 2)

    def test_bluesky_bootstrap_and_empty_poll(self):
        """Verifies FR-1: recent-page bootstrap, no pinned boundary, empty stability."""
        item = bsky_item("new")
        transport = Mock(return_value={"feed": [item], "cursor": "older"})
        provider = BlueskyProvider("fixture.bsky.social", transport=transport)
        batch = provider.fetch(None)
        self.assertEqual(batch.checkpoint, provider.item_key(item))
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(parse_qs(urlparse(transport.call_args.args[0]).query)["includePins"], ["false"])
        provider.transport = Mock(return_value={"feed": []})
        self.assertEqual(provider.fetch(batch.checkpoint).checkpoint, batch.checkpoint)

    def test_bluesky_paginates_to_previous_boundary(self):
        """Verifies FR-1: catch up across pages and refresh the overlapping record."""
        new, old, older = bsky_item("new"), bsky_item("old"), bsky_item("older")
        transport = Mock(side_effect=[{"feed": [new], "cursor": "page-2"},
                                     {"feed": [old, older], "cursor": "page-3"}])
        provider = BlueskyProvider("fixture.bsky.social", transport=transport)
        batch = provider.fetch(provider.item_key(old))
        self.assertEqual([p["post_id"] for p in batch.posts], [new["post"]["uri"], old["post"]["uri"]])
        self.assertEqual(batch.checkpoint, provider.item_key(new))
        self.assertEqual(parse_qs(urlparse(transport.call_args.args[0]).query)["cursor"], ["page-2"])

    def test_bluesky_deleted_boundary_falls_back_to_available_pages(self):
        """Verifies FR-1: missing old boundary does not discard newer content."""
        transport = Mock(side_effect=[{"feed": [bsky_item("new")], "cursor": "page-2"},
                                     {"feed": [bsky_item("old")]}])
        provider = BlueskyProvider("fixture.bsky.social", transport=transport)
        self.assertEqual(len(provider.fetch(provider.item_key(bsky_item("deleted"))).posts), 2)

    def test_bluesky_invalid_response_and_loop_fail(self):
        """Verifies FR-1: bad responses/looping pagination are surfaced as failure."""
        for payload in [{"error": "BlockedActor"}, {"feed": [bsky_item("new")], "cursor": "same"}]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    BlueskyProvider("fixture.bsky.social", transport=Mock(return_value=payload)).fetch("old-boundary")

    def test_repost_boundary_includes_event_time(self):
        """Verifies FR-1: repost of one URI at a later time is not an old boundary."""
        item = bsky_item("same")
        old_key = BlueskyProvider.item_key(item)
        item["reason"] = {"indexedAt": "2026-10-05T11:00:00Z"}
        self.assertNotEqual(BlueskyProvider.item_key(item), old_key)


class PollingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def test_explicit_positive_interval_required(self):
        """Verifies FR-1: no product polling frequency is silently selected."""
        provider = ScriptedProvider("x", "fixture", [])
        for interval in [None, 0, -1, float("nan"), float("inf"), True]:
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                PollingSource(provider, interval, enabled=True)
        self.assertFalse(PollingSource(provider).enabled)

    def test_disabled_source_never_fetches(self):
        """Verifies FR-1: disabled configuration makes no live request."""
        provider = ScriptedProvider("x", "fixture", [])
        self.assertEqual(poll_due(self.conn, [PollingSource(provider)], 0)[0]["status"], "disabled")
        self.assertEqual(provider.calls, [])

    def test_failure_isolated_and_details_not_persisted(self):
        """Verifies FR-1: failed X does not prevent successful Bluesky storage."""
        x = ScriptedProvider("x", "x-fixture", [RuntimeError("SYNTHETIC-SECRET")])
        post = normalize_x({"id": "1", "text": "Fixture"}, {})
        post["platform"] = "bluesky"
        bsky = ScriptedProvider("bluesky", "b-fixture", [FetchBatch([post], "b1")])
        outcomes = poll_due(self.conn, [PollingSource(x, 10, True), PollingSource(bsky, 10, True)], 0)
        self.assertEqual([o["status"] for o in outcomes], ["error", "ok"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)
        states = self.conn.execute("SELECT checkpoint,error_type FROM source_poll_state ORDER BY platform").fetchall()
        self.assertEqual(states, [("b1", None), (None, "RuntimeError")])
        self.assertNotIn("SYNTHETIC-SECRET", str(outcomes) + str(states))

    def test_due_time_checkpoint_and_retry(self):
        """Verifies FR-1: due times, success checkpoint and failure retry are durable."""
        post = normalize_x({"id": "1", "text": "Fixture"}, {})
        provider = ScriptedProvider("x", "fixture", [FetchBatch([post], "1"), RuntimeError("failure"), FetchBatch([], "1")])
        source = PollingSource(provider, 10, True)
        self.assertEqual(poll_due(self.conn, [source], 0)[0]["status"], "ok")
        self.assertEqual(poll_due(self.conn, [source], 5)[0]["status"], "not_due")
        self.assertEqual(poll_due(self.conn, [source], 10)[0]["status"], "error")
        self.assertEqual(self.conn.execute("SELECT checkpoint,last_success_at,next_poll_at FROM source_poll_state").fetchone(), ("1", 0, 20))
        self.assertEqual(poll_due(self.conn, [source], 20)[0]["status"], "ok")
        self.assertEqual(provider.calls, [None, "1", "1"])

    def test_storage_failure_rolls_back_posts_and_checkpoint(self):
        """Verifies FR-1/FR-3: checkpoint advances only with a committed full batch."""
        good = normalize_x({"id": "1", "text": "Fixture"}, {})
        bad = normalize_x({"id": "2"}, {})
        bad["text"] = None
        provider = ScriptedProvider("x", "fixture", [FetchBatch([good], "1"), FetchBatch([good, bad], "2")])
        source = PollingSource(provider, 10, True)
        poll_due(self.conn, [source], 0)
        self.assertEqual(poll_due(self.conn, [source], 10)[0]["status"], "error")
        self.assertEqual(self.conn.execute("SELECT checkpoint FROM source_poll_state").fetchone()[0], "1")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)

    def test_state_survives_reopen(self):
        """Verifies FR-1/FR-3: restart does not forget cursor or next due time."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "polling.sqlite3"
            provider = ScriptedProvider("x", "fixture", [FetchBatch([], "1")])
            source = PollingSource(provider, 10, True)
            with closing(sqlite3.connect(path)) as conn:
                poll_due(conn, [source], 0)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(poll_due(conn, [source], 5)[0]["status"], "not_due")
                self.assertEqual(poll_due(conn, [source], 10)[0]["status"], "ok")
            self.assertEqual(provider.calls, [None, "1"])

    def test_duplicate_configuration_fails_before_fetch(self):
        """Verifies FR-1: duplicate source keys do not generate duplicate API calls."""
        provider = ScriptedProvider("x", "fixture", [])
        source = PollingSource(provider, 10, True)
        with self.assertRaises(ValueError):
            poll_due(self.conn, [source, source], 0)
        self.assertEqual(provider.calls, [])

    def test_rate_limit_wait_is_persisted(self):
        """Verifies FR-1: HTTP rate-limit headers delay retries across schedules."""
        error = HTTPError("https://example.org", 429, "SYNTHETIC-PRIVATE", {"Retry-After": "60", "x-rate-limit-reset": "100"}, None)
        provider = ScriptedProvider("x", "fixture", [error])
        source = PollingSource(provider, 10, True)
        poll_due(self.conn, [source], 0)
        self.assertEqual(self.conn.execute("SELECT next_poll_at FROM source_poll_state").fetchone()[0], 100)
        self.assertEqual(poll_due(self.conn, [source], 99)[0]["status"], "not_due")

    def test_invalid_rate_limit_header_uses_explicit_interval(self):
        """Verifies FR-1: malformed external retry headers do not break other work."""
        error = HTTPError("https://example.org", 429, "failure", {"Retry-After": "invalid"}, None)
        source = PollingSource(ScriptedProvider("x", "fixture", [error]), 10, True)
        self.assertEqual(poll_due(self.conn, [source], 0)[0]["status"], "error")
        self.assertEqual(self.conn.execute("SELECT next_poll_at FROM source_poll_state").fetchone()[0], 10)


class PollingConfigTests(unittest.TestCase):
    def test_example_and_pending_linkedin_make_no_requests_or_database(self):
        """Verifies FR-1/FR-10: shipped configuration is disabled and leaves state alone."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-created.sqlite3"
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(run_polling.main(["--once", "--db", str(path)]), 0)
            self.assertFalse(path.exists())
            self.assertIn("LinkedIn API access pending", output.getvalue())

    def test_enabled_linkedin_is_not_a_fake_adapter(self):
        """Verifies FR-1: LinkedIn cannot be marked working without external access."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"sources": [{"platform": "linkedin", "enabled": True}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_polling.load_sources(path)

    def test_live_switch_required_before_any_provider_request(self):
        """Verifies FR-1: configuration alone does not authorize CLI live requests."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            db = Path(directory) / "not-created.sqlite3"
            config.write_text(json.dumps({"sources": [{"platform": "bluesky", "account": "fixture.bsky.social", "enabled": True, "interval_seconds": 10}]}), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_polling.main(["--config", str(config), "--db", str(db), "--once"]), 1)
            self.assertFalse(db.exists())
