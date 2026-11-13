"""Narrow publication rules, separate from fallible model recommendations."""
import re


def explicit_test_post(post):
    # A declaration in the heading, not the word 'test' in research prose.
    heading=post['text'].lstrip().split('\n',1)[0]
    return bool(re.search(r'^(?:ASAP\s+)?MOCK\s+POST\b.*\bFOR\s+TEST(?:ING)?\s+PURPOSES?\s+ONLY\b',heading,re.I) or re.fullmatch(r'(?:THIS (?:POST|MESSAGE) IS )?FOR TEST(?:ING)? PURPOSES? ONLY[.!]?',heading,re.I))


def recommendation(post):
    if explicit_test_post(post):
        return dict(recommendation='reject',reason='Publishing rule: this post explicitly declares itself mock/test-purpose-only content. It must not enter the public news feed. This is a deterministic policy check, not model inference.')
    return None
