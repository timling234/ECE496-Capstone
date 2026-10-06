"""Current-provider polling adapters; LinkedIn access remains externally pending."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from .store_poc import X_TOKEN, fetch_json, normalize_bluesky, normalize_x


@dataclass
class FetchBatch:
    posts: list
    checkpoint: str | None


# FR-1/FR-10: Provider contract
# REF-HORIZON-01: provider-specific retrieval interface (adapted concept only)
class Provider(ABC):
    platform: str
    account: str

    @property
    def key(self):
        return f"{self.platform}:{self.account}"

    @abstractmethod
    def fetch(self, checkpoint):
        """Return common records and a proposed checkpoint; never persist it."""


class XProvider(Provider):
    platform = "x"

    def __init__(self, account, token_file=X_TOKEN, page_size=5, transport=fetch_json):
        if not isinstance(account, str) or not (account.isascii() and account.isdigit()):
            raise ValueError("X account must be a numeric ID")
        if type(page_size) is not int or not 5 <= page_size <= 100:
            raise ValueError("X page_size must be between 5 and 100")
        self.account, self.token_file = account, Path(token_file)
        self.page_size, self.transport = page_size, transport

    # FR-1: Existing credential-file handling; incremental pagination
    def fetch(self, checkpoint):
        if checkpoint is not None and not (checkpoint.isascii() and checkpoint.isdigit()):
            raise ValueError("Invalid X checkpoint")
        token = self.token_file.read_text(encoding="utf-8-sig").strip()
        if not token:
            raise ValueError("X token file is empty")
        params = {"max_results": self.page_size,
                  "tweet.fields": "created_at,attachments,entities",
                  "expansions": "attachments.media_keys",
                  "media.fields": "type,url,preview_image_url,width,height"}
        if checkpoint:
            params["since_id"] = checkpoint
        posts, visited = [], set()
        while True:
            payload = self.transport(f"https://api.x.com/2/users/{self.account}/tweets?{urlencode(params)}", token)
            if payload.get("errors"):
                raise ValueError("X returned partial errors")
            media = {m["media_key"]: m for m in payload.get("includes", {}).get("media", [])}
            posts.extend(normalize_x(p, media, account_id=self.account) for p in payload.get("data", []))
            following = payload.get("meta", {}).get("next_token")
            # Preserve POC bootstrap behavior: first poll seeds one recent page.
            if not checkpoint or not following:
                break
            if following in visited:
                raise ValueError("Repeated X pagination token")
            visited.add(following)
            params["pagination_token"] = following
        ids = [p["post_id"] for p in posts] + ([checkpoint] if checkpoint else [])
        newest = max(ids, key=int) if ids else checkpoint
        return FetchBatch(posts, newest)


class BlueskyProvider(Provider):
    platform = "bluesky"

    def __init__(self, account, page_size=5, transport=fetch_json):
        if not isinstance(account, str) or not account.strip():
            raise ValueError("Bluesky account is required")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("Bluesky page_size must be between 1 and 100")
        self.account, self.page_size, self.transport = account, page_size, transport

    @staticmethod
    def item_key(item):
        post = item["post"]
        # A later repost of the same original URI is a distinct feed boundary.
        time = item.get("reason", {}).get("indexedAt") or post.get("indexedAt") or post.get("record", {}).get("createdAt")
        return json.dumps([post["uri"], time], separators=(",", ":"))

    # FR-1: Public author-feed pagination until the previous observed boundary
    def fetch(self, checkpoint):
        params = {"actor": self.account, "limit": self.page_size, "includePins": "false"}
        posts, visited, newest = [], set(), None
        while True:
            payload = self.transport("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + urlencode(params))
            if payload.get("error") or not isinstance(payload.get("feed"), list):
                raise ValueError("Invalid Bluesky feed response")
            reached = False
            for item in payload["feed"]:
                if item.get("reason", {}).get("$type") == "app.bsky.feed.defs#reasonPin":
                    continue
                key = self.item_key(item)
                if newest is None:
                    newest = key
                # Refresh the overlapping boundary's current provider snapshot.
                posts.append(normalize_bluesky(item, fallback_handle=self.account))
                if key == checkpoint:
                    reached = True
                    break
            following = payload.get("cursor")
            if not checkpoint or reached or not following:
                break
            if following in visited:
                raise ValueError("Repeated Bluesky pagination cursor")
            visited.add(following)
            params["cursor"] = following
        return FetchBatch(posts, newest or checkpoint)
