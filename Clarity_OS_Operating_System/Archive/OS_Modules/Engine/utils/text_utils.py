# text_utils.py
# Simple text normalization / tokenization utilities.

import re

_whitespace_re = re.compile(r"\s+")
_token_re = re.compile(r"\w+|\S")

def normalize_text(text: str) -> str:
    text = text.strip()
    text = _whitespace_re.sub(" ", text)
    return text

def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    return _token_re.findall(text)
