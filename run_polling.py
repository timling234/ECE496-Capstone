"""Run explicit-config scheduled polling. Example sources are disabled."""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from src.polling import PollingSource, poll_due
from src.providers import BlueskyProvider, XProvider
from src.store_poc import ROOT, X_TOKEN


# FR-1/FR-10: File configuration and executable scheduler; no default frequency
def load_sources(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    sources = []
    for item in config["sources"]:
        platform = item["platform"]
        enabled = item.get("enabled", False)
        if platform == "linkedin":
            if enabled:
                raise ValueError("LinkedIn API access pending; cannot enable it")
            continue
        if platform == "x":
            token_path = Path(item.get("token_file", str(X_TOKEN)))
            if not token_path.is_absolute():
                token_path = ROOT / token_path
            provider = XProvider(item["account"], token_file=token_path, page_size=item.get("page_size", 5))
        elif platform == "bluesky":
            provider = BlueskyProvider(item["account"], page_size=item.get("page_size", 5))
        else:
            raise ValueError("Unsupported provider")
        sources.append(PollingSource(provider, item.get("interval_seconds"), enabled))
    return sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "polling.example.json")
    parser.add_argument("--db", type=Path, default=ROOT / ".tmp" / "store_poc.sqlite3")
    parser.add_argument("--once", action="store_true", help="Process due sources once instead of running continuously.")
    parser.add_argument("--live", action="store_true", help="Explicitly permit live API requests (X may consume API credits).")
    args = parser.parse_args(argv)
    try:
        sources = load_sources(args.config)
        if not any(source.enabled for source in sources):
            print("No enabled sources. LinkedIn API access pending. No API requests or Store changes.")
            return 0
        if not args.live:
            print("Live sources configured: add --live to permit API requests. No requests made.")
            return 1
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(args.db)) as conn:
            while True:
                outcomes = poll_due(conn, sources, time.time())
                for outcome in outcomes:
                    if outcome["status"] != "not_due":
                        print(json.dumps(outcome))
                if args.once:
                    return 1 if any(o["status"] == "error" for o in outcomes) else 0
                time.sleep(1)
    except KeyboardInterrupt:
        print("Polling stopped.")
        return 0
    except Exception as error:
        print(f"Unable to run configured polling ({type(error).__name__}).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
