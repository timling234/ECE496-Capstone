import json
from pathlib import Path

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_ID = "2100252721475448832"
TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]

TOKEN_FILE = REPO_ROOT / "asap_test_lab_x_twitter_bearer_token.txt"
STATE_FILE = TEST_DIR / "x_last_seen_id.txt"

def main():
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8-sig").strip()
        last_seen = (
            STATE_FILE.read_text(encoding="utf-8-sig").strip()
            if STATE_FILE.exists() else ""
        )
    except OSError:
        print("Unable to read the token or state file.")
        return 1
    if not token:
        print("Bearer token file is empty.")
        return 1
    if last_seen and not (last_seen.isascii() and last_seen.isdigit()):
        print("Invalid Post ID in x_last_seen_id.txt; state unchanged.")
        return 1

    params = {
        "max_results": 5,
        "tweet.fields": "created_at,attachments,entities",
        "expansions": "attachments.media_keys",
        "media.fields": "type,url,preview_image_url,width,height",
    }
    if last_seen:
        params["since_id"] = last_seen
    print("Retrieving new posts..." if last_seen else "Retrieving recent posts...")

    posts = []
    media = {}
    newest_id = None
    try:
        while True:
            request = Request(
                f"https://api.x.com/2/users/{USER_ID}/tweets?{urlencode(params)}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if payload.get("errors"):
                print("X API returned partial errors; state unchanged.")
                return 1
            page = payload.get("data", [])
            meta = payload.get("meta", {})
            if page and newest_id is None:
                newest_id = meta.get("newest_id") or max(
                    (post["id"] for post in page), key=int
                )
            posts.extend(page)
            for item in payload.get("includes", {}).get("media", []):
                media[item["media_key"]] = item
            # Bootstrap only the latest page; drain all pages on later polls.
            next_token = meta.get("next_token")
            if not last_seen or not next_token:
                break
            params["pagination_token"] = next_token
    except HTTPError as error:
        print(f"Failed to retrieve posts (HTTP {error.code}); state unchanged.")
        return 1
    except (URLError, OSError, ValueError, KeyError, TypeError):
        # Never print exception details, headers, or raw error responses.
        print("Unable to retrieve or parse X posts; state unchanged.")
        return 1

    if not posts:
        print("No new X posts found.")
        return 0

    def display(value):
        # Redact even if returned post content happens to contain the token.
        return json.dumps(value, ensure_ascii=True, indent=2).replace(token, "[REDACTED]")

    for post in posts:
        attachments = post.get("attachments", {})
        print("\n------------------------")
        print("Post ID:", display(post["id"]))
        print("created_at:", display(post.get("created_at")))
        print("text:", display(post.get("text", "")))
        print("entities / URLs:", display(post.get("entities", {})))
        print("attachments:", display(attachments))
        print("media:", display([
            media[key] for key in attachments.get("media_keys", []) if key in media
        ]))

    try:
        # Replace atomically so an interrupted write cannot truncate the cursor.
        temporary = STATE_FILE.with_suffix(".txt.tmp")
        temporary.write_text(str(newest_id) + "\n", encoding="utf-8")
        temporary.replace(STATE_FILE)
    except OSError:
        print("Posts displayed, but unable to save state; the next run may repeat them.")
        return 1
    print("\nSaved newest_id to x_last_seen_id.txt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
