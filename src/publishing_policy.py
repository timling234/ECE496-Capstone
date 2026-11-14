"""Narrow publication rules, separate from fallible model recommendations."""
import re


def explicit_test_post(post):
    # A declaration in the heading, not the word 'test' in research prose.
    from .embed_review import review_text
    heading=review_text(post).lstrip().split('\n',1)[0]
    return bool(re.search(r'^(?:ASAP\s+)?MOCK\s+POST\b.*\bFOR\s+TEST(?:ING)?\s+PURPOSES?\s+ONLY\b',heading,re.I) or re.fullmatch(r'(?:THIS (?:POST|MESSAGE) IS )?FOR TEST(?:ING)? PURPOSES? ONLY[.!]?',heading,re.I))


def placeholder_test_post(post):
    # Match whole, content-free messages; never a keyword ban on testing research.
    from .embed_review import review_text
    text=review_text(post).strip()
    return bool(re.fullmatch(r'(?:another\s+)?(?:this\s+is\s+(?:a\s+)?)?test(?:ing)?(?:\s*\d+)?(?:\s+(?:post|message))?(?:\s+from\s+(?:bluesky|x|twitter|linkedin))?[.!]?',text,re.I))


def recommendation(post):
    md=post.get("metadata",{})
    if md.get('deletion_sync'):
        if md['deletion_sync']['valid']:
            return dict(recommendation='approve',reason='Publishing rule: the source reported removal and the local target is unchanged. Approve deletion synchronization by default.')
        return dict(recommendation='needs_review',reason='Deletion synchronization conflicts with changed or recovered content. Do not automatically delete it.')
    if md.get("is_repost") and md.get("original_resolution")!="available" and md.get("embed_review",{}).get("status")!="complete":
        return dict(recommendation="needs_review",reason="Original repost text is not available from the API or a verified public embed extraction. Review the preview manually; this is an availability check, not model inference.")
    if explicit_test_post(post):
        return dict(recommendation='reject',reason='Publishing rule: this post explicitly declares itself mock/test-purpose-only content. It must not enter the public news feed. This is a deterministic policy check, not model inference.')
    if placeholder_test_post(post):
        return dict(recommendation='reject',reason='Publishing rule: this is a standalone placeholder/connectivity test message, not a news update. This is a deterministic policy check, not model inference.')
    return None
