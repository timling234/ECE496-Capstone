"""Single-worker scheduler with explicit intervals and atomic source checkpoints."""

import math
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError

from .providers import Provider
from .store_poc import process_stored, store


# FR-1: Live polling requires explicit enablement and an explicit interval
@dataclass
class PollingSource:
    provider: Provider
    interval_seconds: float | None = None
    enabled: bool = False

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        if self.enabled and (type(self.interval_seconds) not in (int, float)
                             or not math.isfinite(self.interval_seconds) or self.interval_seconds <= 0):
            raise ValueError("Enabled sources require a positive explicit interval")


# FR-1/FR-3: Per-source persistence and failure isolation, independent code
def poll_due(conn, sources, now):
    """Poll enabled, due sources; this coordinator owns its transactions.

    Checkpoint + source rows + derived stages commit together. Failure does not
    advance the checkpoint or prevent another source from being polled. Error
    diagnostics contain only exception type, never secrets or response bodies.
    next_poll_at persists across restarts. This is a single-worker MVP scheduler.
    """
    if conn.in_transaction:
        raise ValueError("Polling requires a connection without pending writes")
    if not math.isfinite(now):
        raise ValueError("now must be finite")
    sources = list(sources)
    if len({s.provider.key for s in sources}) != len(sources):
        raise ValueError("Duplicate configured source")
    with conn:
        store(conn, [])
        conn.execute("""CREATE TABLE IF NOT EXISTS source_poll_state (
            source_key TEXT PRIMARY KEY NOT NULL, platform TEXT NOT NULL,
            account TEXT NOT NULL, checkpoint TEXT,
            last_attempt_at REAL, last_success_at REAL, error_type TEXT,
            next_poll_at REAL NOT NULL DEFAULT 0
        )""")
    outcomes = []
    for source in sources:
        provider = source.provider
        if not source.enabled:
            outcomes.append({"source": provider.key, "status": "disabled"})
            continue
        with conn:
            conn.execute("INSERT OR IGNORE INTO source_poll_state(source_key,platform,account) VALUES (?,?,?)",
                         (provider.key, provider.platform, provider.account))
        checkpoint, due = conn.execute("SELECT checkpoint,next_poll_at FROM source_poll_state WHERE source_key=?", (provider.key,)).fetchone()
        if now < due:
            outcomes.append({"source": provider.key, "status": "not_due"})
            continue
        try:
            batch = provider.fetch(checkpoint)
            if any(post["platform"] != provider.platform for post in batch.posts):
                raise ValueError("Provider returned another platform's records")
            with conn:
                store(conn, batch.posts)
                process_stored(conn)
                conn.execute("""UPDATE source_poll_state SET checkpoint=?,
                    last_attempt_at=?,last_success_at=?,error_type=NULL,next_poll_at=? WHERE source_key=?""",
                             (batch.checkpoint, now, now, now + source.interval_seconds, provider.key))
            outcomes.append({"source": provider.key, "status": "ok", "fetched": len(batch.posts)})
        except Exception as error:
            retry_at = now + source.interval_seconds
            if isinstance(error, HTTPError) and error.code == 429:
                headers = error.headers or {}
                value = headers.get("Retry-After")
                if value:
                    try:
                        retry_at = max(retry_at, now + float(value))
                    except (ValueError, TypeError):
                        try:
                            retry_at = max(retry_at, parsedate_to_datetime(value).timestamp())
                        except (ValueError, TypeError, OverflowError):
                            pass
                try:
                    retry_at = max(retry_at, float(headers.get("x-rate-limit-reset", retry_at)))
                except (ValueError, TypeError):
                    pass
                if not math.isfinite(retry_at):
                    retry_at = now + source.interval_seconds
            with conn:
                conn.execute("UPDATE source_poll_state SET last_attempt_at=?,error_type=?,next_poll_at=? WHERE source_key=?",
                             (now, type(error).__name__, retry_at, provider.key))
            outcomes.append({"source": provider.key, "status": "error", "error_type": type(error).__name__})
    return outcomes
