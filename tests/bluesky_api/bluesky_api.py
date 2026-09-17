import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


HANDLE = "asaptestlab.bsky.social"
BASE_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


def main():
    params = {
        "actor": HANDLE,
        "limit": 10,
    }

    url = f"{BASE_URL}?{urlencode(params)}"

    print(f"Retrieving Bluesky posts from @{HANDLE}...")

    try:
        with urlopen(url, timeout=30) as response:
            payload = json.load(response)

    except HTTPError as error:
        print(f"Bluesky API request failed (HTTP {error.code}).")
        return 1

    except (URLError, OSError, ValueError):
        print("Unable to retrieve or parse Bluesky posts.")
        return 1

    feed = payload.get("feed", [])

    if not feed:
        print("No posts found.")
        return 0

    print(f"Retrieved {len(feed)} post(s).")

    for item in feed:
        post = item.get("post", {})
        record = post.get("record", {})

        print("\n------------------------")
        print("URI:", post.get("uri"))
        print("CID:", post.get("cid"))
        print("created_at:", record.get("createdAt"))
        print("text:", record.get("text", ""))

        embed = post.get("embed")
        if embed:
            print(
                "embed:",
                json.dumps(embed, ensure_ascii=False, indent=2)
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())