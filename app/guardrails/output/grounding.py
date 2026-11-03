"""Every quoted source passage must really appear in the source the agent was given.

Comparison ignores case, whitespace, Markdown emphasis and typographic quote/dash variants, so a faithful quote
of formatted text passes. An ellipsis splits a quote into parts; each part must appear, in order.
"""

import re

from app.guardrails.findings import Finding

MIN_QUOTE_CHARS = 4
_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
_MARKDOWN = re.compile(r"[*_`#>|]+")
_SPACE = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\.\.\.|…")


def normalise(text: str) -> str:
    text = _MARKDOWN.sub(" ", text.translate(_TRANSLATE))
    text = re.sub(r"(?m)^\s*(?:[-+]|\d+[.)])\s+", " ", text)  # list markers
    return _SPACE.sub(" ", text).strip().lower()


def quote_found(quote: str, source_normalised: str) -> bool:
    parts = [normalise(part) for part in _ELLIPSIS.split(quote)]
    parts = [part for part in parts if part]
    if not parts or sum(len(part) for part in parts) < MIN_QUOTE_CHARS:
        return False
    position = 0
    for part in parts:
        index = source_normalised.find(part, position)
        if index < 0:
            return False
        position = index + len(part)
    return True


def check_quotes(quotes: list[tuple[str, str]], source: str, *, source_name: str) -> list[Finding]:
    """quotes: (path, quote) pairs."""
    source_normalised = normalise(source)
    return [
        Finding("grounding", "block", f"Quoted text does not appear in the {source_name}: \"{quote[:120]}\"", path)
        for path, quote in quotes
        if not quote_found(quote, source_normalised)
    ]
