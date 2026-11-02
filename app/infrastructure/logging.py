"""Structured JSON logging with secret redaction at the output boundary."""

import json
import logging
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime

_HANDLER_NAME = "agentra"
_MASK = "***"
_MIN_SECRET_LENGTH = 6

_known_secrets: set[str] = set()

_PATTERNS = [
    # Password in a connection URL: scheme://user:password@host
    (re.compile(r"(://[^:/@\s]+:)[^@\s/]+@"), rf"\1{_MASK}@"),
    # Anthropic API keys
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]+"), _MASK),
    # Bearer tokens
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-~+/]+=*"), rf"\1 {_MASK}"),
    # key=value or "key": "value" pairs with a sensitive key name
    (
        re.compile(
            r"""(?i)((?<![A-Za-z0-9_])["']?(?:password|passwd|pwd|secret|token|api[_-]?key)["']?\s*[:=]\s*["']?)[^\s"',}]+"""
        ),
        rf"\1{_MASK}",
    ),
]

_SENSITIVE_KEY = re.compile(
    r"(?i)^(password|passwd|pwd|secret|client_secret|token|access_token|refresh_token|api_key|apikey|authorization|credentials?)$"
)

# Record attributes that are not user-supplied context; uvicorn adds an ANSI-coloured duplicate message.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "color_message"}


def register_secret(value: str | None) -> None:
    """Mask this exact value in every log line from now on."""
    if value and len(value) >= _MIN_SECRET_LENGTH:
        _known_secrets.add(value)


def redact(text: str) -> str:
    for secret in sorted(_known_secrets, key=len, reverse=True):
        text = text.replace(secret, _MASK)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            if _SENSITIVE_KEY.match(key):
                payload[key] = _MASK
            elif value is None or isinstance(value, bool | int | float):
                payload[key] = value
            else:
                payload[key] = redact(str(value))
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", secrets: Iterable[str | None] = ()) -> None:
    """Install the JSON handler on the root logger. Safe to call more than once."""
    for secret in secrets:
        register_secret(secret)

    root = logging.getLogger()
    root.handlers = [handler for handler in root.handlers if handler.get_name() != _HANDLER_NAME]
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Route uvicorn's own loggers through the redacting handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
