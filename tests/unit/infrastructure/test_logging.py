import json
import logging
import sys

from app.infrastructure.logging import JsonFormatter, register_secret


def _render(message: str, *args: object, extra: dict[str, object] | None = None, exc_info=None) -> str:
    record = logging.LogRecord("agentra.test", logging.INFO, __file__, 1, message, args, exc_info)
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return JsonFormatter().format(record)


def test_output_is_one_json_object_with_standard_fields() -> None:
    payload = json.loads(_render("project %s created", "P-1", extra={"project_id": "P-1", "attempt": 2}))

    assert payload["msg"] == "project P-1 created"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "agentra.test"
    assert payload["project_id"] == "P-1"
    assert payload["attempt"] == 2
    assert "ts" in payload


def test_password_in_connection_url_is_masked() -> None:
    output = _render("connecting to postgresql+psycopg://agentra:hunter2pass@localhost:5432/agentra_dev")

    assert "hunter2pass" not in output
    assert "agentra:***@localhost" in output


def test_anthropic_key_is_masked() -> None:
    assert "abcDEF123" not in _render("key is sk-ant-api03-abcDEF123")


def test_bearer_token_is_masked() -> None:
    assert "eyJhbGciOi.payload.sig" not in _render("Authorization: Bearer eyJhbGciOi.payload.sig")


def test_sensitive_key_value_pairs_are_masked() -> None:
    output = _render("login failed password=Sup3rS3cret! api_key: 'k-998877'")

    assert "Sup3rS3cret!" not in output
    assert "k-998877" not in output


def test_sensitive_extra_fields_are_masked_but_token_counts_are_kept() -> None:
    payload = json.loads(_render("model call", extra={"password": "p@ssw0rd!", "input_tokens": 1200}))

    assert payload["password"] == "***"
    assert payload["input_tokens"] == 1200


def test_registered_secret_is_masked_anywhere_including_tracebacks() -> None:
    register_secret("Zq7-registered-secret")
    try:
        raise RuntimeError("upstream rejected Zq7-registered-secret")
    except RuntimeError:
        output = _render("call failed with Zq7-registered-secret", exc_info=sys.exc_info())

    assert "Zq7-registered-secret" not in output
    assert "RuntimeError" in output


def test_ordinary_text_is_unchanged() -> None:
    message = "Requirement REQ-F-001 moved to waiting_for_review; 3 tokens left in budget"

    assert json.loads(_render(message))["msg"] == message
