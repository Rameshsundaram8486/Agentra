"""Finds secrets and credentials. Used on input (redacted before a model sees it) and on output (blocked)."""

import re

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")),
    ("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{32,}")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("connection_string_password", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^:/@\s]+:[^@\s/]+@", re.IGNORECASE)),
    ("azure_storage_key", re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}", re.IGNORECASE)),
    # A credential-looking value (letters and digits, 8+ characters) assigned to a credential-like name.
    # Plain prose such as "password: must be changed every 90 days" is not matched.
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|client[_ ]secret|api[_ -]?key|secret[_ ]key|access[_ ]token)\b\s*[:=]\s*"
            r"[\"']?(?=[^\s\"']*\d)(?=[^\s\"']*[A-Za-z])[^\s\"']{8,}"
        ),
    ),
]


def find_secrets(text: str) -> list[str]:
    """Kinds of secret found, in pattern order, without the values."""
    return [kind for kind, pattern in _SECRET_PATTERNS if pattern.search(text)]


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Text with each secret replaced by [REDACTED <kind>], and the kinds that were found."""
    found = []
    for kind, pattern in _SECRET_PATTERNS:
        text, count = pattern.subn(f"[REDACTED {kind}]", text)
        if count:
            found.append(kind)
    return text, found
