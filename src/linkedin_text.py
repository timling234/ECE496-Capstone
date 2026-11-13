"""LinkedIn little-text encoding; render annotations as safe plain text.
Reference: Microsoft LinkedIn little-text-format documentation.
"""
import re
RESERVED=r'\|{}@[]()<>#*_~'


def encode(text):
    return ''.join('\\'+c if c in RESERVED else c for c in text)


def decode(text):
    def hashtag(match):
        parts=match[1].split('|')
        return '#'+parts[-1].lstrip('\\#＃')
    text=re.sub(r'(?<!\\)\{hashtag\|([^{}]+)\}',hashtag,text)
    text=re.sub(r'(?<!\\)@\[([^\]]+)\]\(urn:li:[^)]+\)',lambda m:m[1],text)
    return re.sub(r'\\([\\|{}@\[\]()<>#*_~])',lambda m:m[1],text)
